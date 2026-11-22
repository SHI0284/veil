"""로컬 Flask 어댑터. 기존 PCAgent를 재사용하고 대화는 세션별 메모리에 둔다.
공유 SQLite 연결과 세션 접근은 RLock으로 직렬화한다. 원격 배포용 서버가 아니다.
"""
import secrets
import threading
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, abort, g, jsonify, redirect, render_template, request, session
from werkzeug.exceptions import HTTPException
from .controller import PCAgent
from .storage import LocalRepository
from .gateway import StubAIClient
from .openai_client import AISettings, OpenAIClient, ProviderError


def create_app(database=None, testing=False):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), TESTING=testing,
        TEMPLATES_AUTO_RELOAD=True,
        MAX_CONTENT_LENGTH=512 * 1024, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict", TRUSTED_HOSTS=["127.0.0.1", "localhost"])
    if database is None:
        folder = Path(__file__).resolve().parents[1] / "data"
        folder.mkdir(exist_ok=True)
        database = folder / "veil_demo.sqlite3"
    repo = LocalRepository(database, check_same_thread=False)
    states, lock = {}, threading.RLock()
    ai_settings = AISettings()
    app.extensions["veil_ai_settings"] = ai_settings
    app.extensions.update(veil_repository=repo, veil_states=states, veil_lock=lock)
    last_purge = [0.0]

    @app.before_request
    def prepare():
        lock.acquire()
        g.locked = True
        now = time.monotonic()
        for key, current in list(states.items()):
            if now - current["accessed"] > 3600:
                current["agent"].logout()
                del states[key]
        if now - last_purge[0] > 60:
            repo.purge()
            last_purge[0] = now
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf"]):
                abort(403, "접근 정보가 갱신되었습니다. 페이지를 새로고침하세요.")
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                abort(403, "다른 사이트에서 보낸 요청은 허용하지 않습니다.")
            if not request.is_json or not isinstance(request.get_json(silent=True), dict):
                abort(400, "올바른 JSON 요청이 필요합니다.")

    @app.teardown_request
    def release(error):
        if getattr(g, "locked", False):
            lock.release()

    @app.after_request
    def headers(response):
        response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})
        return response

    def state(role=None):
        current = states.get(session.get("sid"))
        if not current:
            abort(401, "로그인이 필요합니다.")
        current["agent"].require_user(role)
        current["accessed"] = time.monotonic()
        return current

    def string(data, name, default=None):
        value = data.get(name, default)
        if not isinstance(value, str):
            raise ValueError("입력 형식을 확인해 주세요: " + name)
        return value

    def payload(s):
        agent, p = s["agent"], s["agent"].current
        prompt = None
        if p:
            r = p.result
            prompt = {"id": p.prompt_id, "content": p.content, "revision": p.revision,
                "status": p.status, "converted": p.converted,
                "result": {"id": r.result_id, "level": r.level, "score": r.score,
                    "policy_version": r.policy_version,
                    "counts": dict(Counter(i.kind for i in r.items)),
                    "history": any(i.from_history for i in r.items),
                    "core": any(i.category == "CORE_SECRET" for i in r.items)} if r else None}
        return {"user": agent.user, "policy": asdict(repo.get_policy()), "prompt": prompt,
                "messages": s["messages"], "scenario": getattr(agent.gateway.client, "scenario", None),
                "ai": ({"provider": "모의 AI", "model": "stub", "configured": True, "is_demo": True} if testing else ai_settings.public()),
                "history_count": min(4, len(agent.conversation.prompts))}

    def expected(s, data):
        p = s["agent"].current
        if not p or data.get("prompt_id") != p.prompt_id or not p.result or data.get("result_id") != p.result.result_id:
            raise ValueError("다른 탭에서 요청이 바뀌었거나 검사 결과가 만료되었습니다. 다시 검사하세요.")
        if data.get("content") != p.content:
            raise ValueError("입력이 변경되었습니다. 먼저 다시 검사하세요.")

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            code, message = exc.code, exc.description
        elif isinstance(exc, PermissionError):
            code, message = 403, str(exc)
        elif isinstance(exc, ValueError):
            code, message = 400, str(exc)
        elif isinstance(exc, (TimeoutError, ConnectionError)):
            code, message = 503, str(exc)
        else:
            code, message = 500, "작업을 완료하지 못했습니다. 입력은 유지됩니다. 다시 시도해 주세요."
        if request.path.startswith("/api/"):
            if isinstance(exc, ProviderError):
                return jsonify(error=message, state=payload(state())), code
            return jsonify(error=message), code
        return render_template("error.html", message=message), code

    @app.get("/")
    def index():
        s = states.get(session.get("sid"))
        if not s:
            return redirect("/login")
        return redirect("/admin" if s["agent"].user["role"] == "MANAGER" else "/workspace")

    @app.get("/login")
    def login_page():
        return render_template("login.html")

    @app.get("/workspace")
    def workspace():
        if session.get("sid") not in states:
            return redirect("/login")
        state("RESEARCHER")
        return render_template("workspace.html")

    @app.get("/admin")
    def admin():
        if session.get("sid") not in states:
            return redirect("/login")
        state("MANAGER")
        return render_template("admin.html")

    @app.get("/api/session")
    def bootstrap():
        s = states.get(session.get("sid"))
        return jsonify(csrf=session["csrf"], **(payload(state()) if s else {"user": None}))

    @app.post("/api/login")
    def login():
        data = request.get_json()
        agent = PCAgent(repo, StubAIClient() if testing else OpenAIClient(ai_settings))
        agent.login(string(data, "username").strip(), string(data, "password"))
        old = states.pop(session.get("sid"), None)
        if old:
            old["agent"].logout()
        session.clear()
        session.update(sid=secrets.token_urlsafe(32), csrf=secrets.token_urlsafe(32))
        s = {"agent": agent, "messages": [], "preview": None, "accessed": time.monotonic()}
        states[session["sid"]] = s
        return jsonify(csrf=session["csrf"], **payload(s))

    @app.post("/api/logout")
    def logout():
        s = states.pop(session.get("sid"), None)
        if s:
            s["agent"].logout()
        session.clear()
        return jsonify(ok=True)

    @app.post("/api/conversation/new")
    def new_conversation():
        s = state("RESEARCHER")
        s["agent"].new_conversation()
        s.update(messages=[], preview=None)
        return jsonify(payload(s))

    @app.post("/api/analyze")
    def analyze():
        s = state("RESEARCHER")
        if s["agent"].current and s["agent"].current.status == "SEND_UNKNOWN":
            raise ValueError("이전 요청의 처리 여부를 확인할 수 없습니다. 중복 처리 가능성을 확인한 뒤 새 대화를 시작하세요.")
        s["agent"].analyze(string(request.get_json(), "content"))
        s["preview"] = None
        return jsonify(payload(s))

    @app.post("/api/preview")
    def preview():
        s = state("RESEARCHER")
        expected(s, request.get_json())
        token = secrets.token_urlsafe(24)
        s["preview"] = (token, s["agent"].current.prompt_id, s["agent"].preview())
        return jsonify(token=token, before=s["agent"].current.content, after=s["preview"][2].content)

    @app.post("/api/approve")
    def approve():
        s, data = state("RESEARCHER"), request.get_json()
        expected(s, data)
        preview = s["preview"]
        if not preview or data.get("token") != preview[0] or s["agent"].current.prompt_id != preview[1]:
            raise ValueError("미리보기가 만료되었습니다. 다시 열어 주세요.")
        s["agent"].approve(preview[2])
        s["preview"] = None
        return jsonify(payload(s))

    @app.post("/api/send")
    def send():
        s, data = state("RESEARCHER"), request.get_json()
        expected(s, data)
        raw, restored = s["agent"].send(string(data, "content"), string(data, "reason", ""))
        s["messages"].extend([{"role": "user", "content": s["agent"].current.content},
            {"role": "assistant", "content": restored, "restored": raw != restored}])
        return jsonify(payload(s))

    @app.post("/api/cancel")
    def cancel():
        s = state("RESEARCHER")
        expected(s, request.get_json())
        s["agent"].cancel()
        s["preview"] = None
        return jsonify(payload(s))

    @app.post("/api/scenario")
    def scenario():
        s = state("RESEARCHER")
        if not isinstance(s["agent"].gateway.client, StubAIClient):
            raise ValueError("실제 AI 연결에서는 모의 응답을 설정할 수 없습니다.")
        value = request.get_json().get("scenario")
        if value not in ("SUCCESS", "TIMEOUT", "ERROR"):
            raise ValueError("지원하지 않는 시연 상황입니다.")
        s["agent"].gateway.client.scenario = value
        return jsonify(payload(s))

    @app.route("/api/ai-settings", methods=["GET", "POST"])
    def configure_ai():
        state("MANAGER")
        if request.method == "POST":
            data = request.get_json()
            ai_settings.update(string(data, "api_key", ""), string(data, "model"))
        return jsonify(ai=ai_settings.public())

    @app.post("/api/policy")
    def policy():
        s, data = state("MANAGER"), request.get_json()
        if data.get("version") != repo.get_policy().version:
            raise ValueError("정책이 변경되었습니다. 새로고침 후 다시 저장하세요.")
        changes = {k: v for k, v in data.items() if k != "version"}
        allowed = {"keywords", "core_keywords", "caution", "block", "mode", "log_level", "retention_days", "auto_delete"}
        if not changes or not changes.keys() <= allowed:
            raise ValueError("지원하지 않는 정책 항목입니다.")
        for key in ("keywords", "core_keywords"):
            if key in changes:
                if not isinstance(changes[key], list) or any(not isinstance(v, str) for v in changes[key]):
                    raise ValueError("키워드 목록을 확인하세요.")
                changes[key] = tuple(v.strip() for v in changes[key])
        for key in ("caution", "block"):
            if key in changes and type(changes[key]) not in (int, float):
                raise ValueError("임계값은 숫자로 입력하세요.")
        if "auto_delete" in changes and type(changes["auto_delete"]) is not bool:
            raise ValueError("자동 삭제 설정을 확인하세요.")
        s["agent"].save_policy(**changes)
        return jsonify(payload(s))

    @app.get("/api/logs")
    def logs():
        s = state("MANAGER")
        level = request.args.get("level", "ALL")
        if level not in ("ALL", "SAFE", "CAUTION", "BLOCKED"):
            raise ValueError("등급을 확인하세요.")
        filters = {"level": level, "user": request.args.get("user", "")}
        tz = timezone(timedelta(hours=9))
        first, last = request.args.get("start"), request.args.get("end")
        if first or last:
            if not first or not last:
                raise ValueError("조회 시작일과 종료일을 모두 입력하세요.")
            start = datetime.strptime(first, "%Y-%m-%d").replace(tzinfo=tz)
            end = datetime.strptime(last, "%Y-%m-%d").replace(tzinfo=tz)
            if start > end:
                raise ValueError("시작일은 종료일 이후일 수 없습니다.")
            filters.update(start=start.astimezone(timezone.utc).isoformat(), end=(end + timedelta(days=1)).astimezone(timezone.utc).isoformat())
        return jsonify(logs=s["agent"].logs(**filters), policy=asdict(repo.get_policy()))

    return app
