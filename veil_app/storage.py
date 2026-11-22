"""담당 D: 보안 서버의 로컬 대체 저장소. 원문/변환문/대화/가명표는 저장하지 않는다."""
import hashlib
import hmac
import json
import secrets
import sqlite3
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from .domain import SecurityPolicy


def now():
    return datetime.now(timezone.utc).isoformat()


class LocalRepository:
    def __init__(self, path, check_same_thread=True):
        self.db = sqlite3.connect(str(path), check_same_thread=check_same_thread)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, role TEXT NOT NULL, salt TEXT NOT NULL,
                password_hash TEXT NOT NULL, failures INTEGER NOT NULL DEFAULT 0,
                locked INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS security_log (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, user_id TEXT NOT NULL,
                prompt_id TEXT NOT NULL, risk_level TEXT, action TEXT NOT NULL,
                policy_version INTEGER NOT NULL, counts TEXT NOT NULL, log_level TEXT NOT NULL,
                summary TEXT NOT NULL, reason_provided INTEGER NOT NULL);
        ''')
        for user, role in (("researcher", "RESEARCHER"), ("manager", "MANAGER")):
            if self.db.execute("SELECT 1 FROM users WHERE id=?", (user,)).fetchone():
                continue
            salt = secrets.token_hex(16)
            digest = self._hash("veil1234!", salt)
            self.db.execute("INSERT OR IGNORE INTO users(id,role,salt,password_hash) VALUES(?,?,?,?)", (user, role, salt, digest))
        self.db.execute("INSERT OR IGNORE INTO policy VALUES(1,?)", (json.dumps(asdict(SecurityPolicy()), ensure_ascii=False),))
        self.db.commit()

    @staticmethod
    def _hash(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200000).hex()

    def login(self, user, password):
        row = self.db.execute("SELECT * FROM users WHERE id=?", (user,)).fetchone()
        if row is None:
            raise ValueError("아이디 또는 비밀번호가 일치하지 않습니다.")
        if row["locked"]:
            raise ValueError("계정이 잠겼습니다. 관리자에게 문의하세요. (데모 잠금 해제: README)")
        if not hmac.compare_digest(row["password_hash"], self._hash(password, row["salt"])):
            failures = row["failures"] + 1
            self.db.execute("UPDATE users SET failures=?, locked=? WHERE id=?", (failures, int(failures >= 5), user))
            self.db.commit()
            raise ValueError("계정이 잠겼습니다 (5/5)." if failures >= 5 else "로그인 실패 {}/5".format(failures))
        self.db.execute("UPDATE users SET failures=0 WHERE id=?", (user,))
        self.db.commit()
        return {"id": user, "role": row["role"]}

    def get_policy(self):
        data = json.loads(self.db.execute("SELECT data FROM policy WHERE id=1").fetchone()[0])
        for key in ("keywords", "core_keywords"):
            data[key] = tuple(data[key])
        return SecurityPolicy(**data)

    def save_policy(self, policy):
        policy.validate()
        if policy.version != self.get_policy().version + 1:
            raise ValueError("정책 버전이 변경되었습니다. 다시 열어 수정하세요.")
        self.db.execute("UPDATE policy SET data=? WHERE id=1", (json.dumps(asdict(policy), ensure_ascii=False),))
        self.db.commit()
        self.purge()

    def add_log(self, user, prompt, action, policy, reason=""):
        counts = Counter(i.kind for i in prompt.result.items) if prompt.result else {}
        # 자유 입력 사유에는 원문이 섞일 수 있다. 이번 버전은 입력 여부만 저장.
        summary = ", ".join("{} {}건".format(k, n) for k, n in sorted(counts.items())) if policy.log_level == "DETAILED" else ""
        self.db.execute('''INSERT INTO security_log(created_at,user_id,prompt_id,risk_level,action,
            policy_version,counts,log_level,summary,reason_provided) VALUES(?,?,?,?,?,?,?,?,?,?)''',
            (now(), user, prompt.prompt_id, prompt.result.level if prompt.result else None, action,
             policy.version, json.dumps(counts), policy.log_level, summary, bool(reason.strip())))
        self.db.commit()
        self.purge()

    def logs(self, level="ALL", user="", start="", end=""):
        self.purge()
        sql, params = "SELECT * FROM security_log WHERE 1=1", []
        if level != "ALL":
            sql += " AND risk_level=?"
            params.append(level)
        if user:
            sql += " AND user_id=?"
            params.append(user)
        if start:
            sql += " AND created_at>=?"
            params.append(start)
        if end:
            sql += " AND created_at<?"
            params.append(end)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY id DESC", params)]

    def purge(self):
        policy = self.get_policy()
        if policy.auto_delete:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=policy.retention_days)).isoformat()
            self.db.execute("DELETE FROM security_log WHERE created_at < ?", (cutoff,))
            self.db.commit()

    def close(self):
        self.db.close()
