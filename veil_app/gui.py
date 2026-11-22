"""담당 A: G01~G08/G13/G14, 관리자 A01~A04의 Tkinter 기초 화면."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, timezone

BG = "#f4f6f0"
WHITE = "#ffffff"
INK = "#242c27"
MUTED = "#6c756b"
GREEN = "#236c50"
BLUE = "#4f6588"


class VeilApp:
    def __init__(self, root, agent):
        self.root, self.agent = root, agent
        root.title("VEIL · 연구를 위한 안전한 AI 사용 · 개발 데모")
        root.geometry("1240x820")
        root.minsize(1080, 740)
        root.configure(bg=BG)
        root.option_add("*Font", ("맑은 고딕", 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", padding=(18, 10))
        style.configure("Treeview", rowheight=30, font=("맑은 고딕", 10))
        style.configure("Treeview.Heading", font=("맑은 고딕", 10, "bold"))
        self.login_view()

    def label(self, parent, text, size=11, color=INK, bold=False, **kw):
        label = tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                         font=("맑은 고딕", size, "bold" if bold else "normal"), justify="left", anchor="w", **kw)
        label.pack(anchor="w", pady=5)
        return label

    def button(self, parent, text, command, primary=False):
        button = tk.Button(parent, text=text, command=lambda: self.run(command),
                           bg=BLUE if primary else WHITE, fg=WHITE if primary else INK,
                           activebackground="#dce7df", relief="flat", bd=0, padx=16, pady=10,
                           cursor="hand2", font=("맑은 고딕", 10, "bold"))
        button.pack(fill="x", pady=5)
        return button

    def text_area(self, parent, height=5, readonly=False, content=""):
        frame = tk.Frame(parent, bg=WHITE)
        frame.pack(fill="both", expand=height > 8, pady=7)
        text = tk.Text(frame, height=height, wrap="word", bg=WHITE, fg=INK, relief="flat",
                       padx=14, pady=12, undo=True, font=("맑은 고딕", 11))
        bar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.insert("1.0", content)
        if readonly:
            text.configure(state="disabled")
        return text

    def run(self, command):
        try:
            return command()
        except (ValueError, PermissionError, TimeoutError, ConnectionError) as exc:
            messagebox.showwarning("VEIL 안내", str(exc), parent=self.root)
        except Exception:
            # 원문 또는 비밀번호가 예외 로그에 섞이지 않도록 출력하지 않는다.
            messagebox.showerror("VEIL 오류", "작업을 완료하지 못했습니다. 입력을 유지했습니다. 저장소와 연결 상태를 확인하세요.", parent=self.root)

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def login_view(self):
        self.clear()
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(expand=True)
        self.label(outer, "VEIL", 42, GREEN, True)
        self.label(outer, "연구를 위한 안전한 AI 사용", 18, bold=True)
        self.label(outer, "PC 에이전트  /  Python 기초 개발 버전", color=MUTED)
        form = tk.Frame(outer, bg=WHITE, padx=32, pady=24)
        form.pack(fill="x", pady=24)
        self.label(form, "아이디")
        self.user_id = tk.Entry(form, width=36, relief="solid", bd=1)
        self.user_id.pack(fill="x", ipady=8)
        self.user_id.insert(0, "researcher")
        self.label(form, "비밀번호")
        self.password = tk.Entry(form, show="●", relief="solid", bd=1)
        self.password.pack(fill="x", ipady=8, pady=(0, 15))
        self.password.bind("<Return>", lambda e: self.run(self.login))
        self.button(form, "로그인", self.login, True)
        self.label(outer, "체험 계정  researcher / manager\n공통 비밀번호  veil1234!", color=MUTED)
        self.label(outer, "로컬 데모 · 외부 AI와 보안 서버는 아직 연결하지 않았어요.", color=MUTED)
        self.password.focus_set()

    def login(self):
        user = self.agent.login(self.user_id.get().strip(), self.password.get())
        self.password.delete(0, "end")
        self.admin_view() if user["role"] == "MANAGER" else self.researcher_view()

    def shell(self):
        self.clear()
        top = tk.Frame(self.root, bg="#e8ede4", padx=24, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="VEIL  /  AI Workspace", bg="#e8ede4", fg=GREEN, font=("맑은 고딕", 13, "bold")).pack(side="left")
        tk.Label(top, text="로컬 개발 데모 · 외부 전송 없음", bg="#e8ede4", fg=MUTED).pack(side="right")
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg="#edf1e8", width=175, padx=18, pady=20)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        self.label(side, "AI Workspace", 13, bold=True)
        self.label(side, self.agent.user["id"], color=MUTED)
        self.button(side, "로그아웃", self.logout)
        self.side = side
        return body

    def logout(self):
        self.agent.logout()
        self.login_view()

    def researcher_view(self):
        body = self.shell()
        self.button(self.side, "+ 새 대화", self.new_chat)
        self.label(self.side, "예제 입력", bold=True)
        for name, value in (
            ("공개 자료", "공개된 논문의 연구 방법을 요약해줘."),
            ("개인정보 · 주의", "김연구의 비공개 연구 계획을 요약하고 010-1234-5678에 보낼 안내문을 작성해줘."),
            ("고민감 · 차단", "보안과제의 핵심기술 개발 일정을 요약해줘."),
        ):
            self.button(self.side, name, lambda t=value: self.fill_input(t))
        self.label(self.side, "모의 AI 상황", bold=True)
        self.scenario = tk.StringVar(value="SUCCESS")
        combo = ttk.Combobox(self.side, textvariable=self.scenario, values=("SUCCESS", "TIMEOUT", "ERROR"), state="readonly", width=12)
        combo.pack(fill="x", pady=8)
        combo.bind("<<ComboboxSelected>>", lambda e: setattr(self.agent.gateway.client, "scenario", self.scenario.get()))
        self.label(self.side, "SUCCESS  정상 응답\nTIMEOUT  재시도 2회\nERROR  즉시 중단", 9, MUTED)
        main = tk.Frame(body, bg=WHITE, padx=24, pady=18)
        main.pack(side="left", fill="both", expand=True)
        self.panel = tk.Frame(body, bg=BG, width=365, padx=22, pady=18)
        self.panel.pack(side="right", fill="y")
        self.panel.pack_propagate(False)
        self.label(main, "연구 문서 검토", 24, bold=True)
        self.label(main, "현재 대화 · 모의 AI  |  대화는 메모리에만 보관", 10, MUTED)
        self.chat = self.text_area(main, height=15, readonly=True,
                                   content="VEIL에 오신 것을 환영해요.\n\n왼쪽 예제로 시작하거나 아래에 프롬프트를 입력하세요.\n보안 검사를 마친 안전한 입력만 모의 AI로 전달합니다.")
        self.label(main, "나의 프롬프트", bold=True)
        self.input = self.text_area(main, height=5)
        self.input.bind("<<Modified>>", self.input_changed)
        self.input.edit_modified(False)
        self.counter = self.label(main, "0자 · 검사를 마칠 때까지 입력은 이 PC에 있어요.", 9, MUTED)
        self.button(main, "로컬 보안 검사 시작", self.analyze, True)
        self.render_panel()

    def input_changed(self, event=None):
        if self.input.edit_modified():
            self.input.edit_modified(False)
            if hasattr(self, "counter") and self.counter.winfo_exists():
                size = len(self.input.get("1.0", "end-1c"))
                self.counter.configure(text="{}자 · {}".format(size, "분석이 오래 걸릴 수 있어요." if size > 2000 else "입력 변경 후에는 다시 검사하세요."))
            if hasattr(self, "send_button") and self.send_button.winfo_exists():
                self.send_button.configure(state="disabled")

    def fill_input(self, value):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", value)

    def new_chat(self):
        self.agent.new_conversation()
        self.researcher_view()

    def append_chat(self, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", "\n\n" + text)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def analyze(self):
        result = self.agent.analyze(self.input.get("1.0", "end-1c"))
        self.render_panel()
        if result.level == "SAFE":
            self.send()

    def send(self):
        reason = self.reason.get() if hasattr(self, "reason") else ""
        response, restored = self.agent.send(self.input.get("1.0", "end-1c"), reason)
        self.append_chat("나\n" + self.agent.current.content + "\n\n" + restored)
        if response != restored:
            self.append_chat("VEIL · 답변의 가명을 이 PC에서 복원했어요. 마스킹한 연락처는 복원하지 않아요.")
        self.fill_input("")
        self.render_panel()

    def render_panel(self):
        for child in self.panel.winfo_children():
            child.destroy()
        self.label(self.panel, "VEIL", 28, bold=True)
        self.label(self.panel, "연구를 위한 안전한 AI 사용", 11, MUTED)
        policy = self.agent.repository.get_policy()
        self.label(self.panel, "정책 v{} · {}".format(policy.version, "빠른 검사" if policy.mode == "FAST" else "가명화 데모 · 규칙 검사"), 10, MUTED)
        p = self.agent.current
        result = p.result if p else None
        status = p.status if p else "INPUT"
        title, color = {
            "INPUT": ("전송 전에 확인할게요", INK),
            "SAFE": ("검사 완료 · 안전", GREEN),
            "CAUTION": ("민감정보를 확인했어요", "#a9651e"),
            "BLOCKED": ("고위험 정보 · 전송 차단", "#b13e38"),
            "SENT": ("답변을 받았어요", GREEN),
            "CANCELLED": ("입력을 취소했어요", MUTED),
        }.get(status, ("보안 검사", INK))
        self.label(self.panel, title, 17, color, True, wraplength=320)
        if result:
            self.label(self.panel, "{}  ·  점수 {:.2f}  ·  입력 v{}".format(result.level, result.score, p.revision), 10, color)
            counts = {}
            for item in result.items:
                name = {"PERSON": "인물", "PHONE": "연락처", "EMAIL": "이메일", "KEYWORD": "보호 키워드", "IDENTIFIER": "식별번호"}[item.kind]
                counts[name] = counts.get(name, 0) + 1
            self.label(self.panel, "\n".join("{}  {}건".format(k, v) for k, v in counts.items()) or "탐지된 민감정보가 없어요.", 11)
            if any(i.from_history for i in result.items):
                self.label(self.panel, "이전 대화에서도 위험 정보를 찾았어요.\n현재 입력만 변환해도 위험이 남을 수 있어요.", 10, "#a9651e", wraplength=320)
        else:
            self.label(self.panel, "현재 입력과 이전 대화 최대 4개를\n함께 검사해요.", 12)
            self.label(self.panel, "이 대화의 보호 상태", 12, bold=True)
            self.label(self.panel, "• 원문과 가명표: PC 메모리\n• 전송 대상: 모의 AI\n• 탐지 방식: 키워드·패턴", 11, MUTED)
        if status in ("CAUTION", "BLOCKED"):
            self.button(self.panel, "변환 미리보기", self.preview, True)
            if status == "CAUTION":
                self.label(self.panel, "경고 확인 후 전송 사유 (5~200자)", 10)
                self.reason = tk.StringVar()
                tk.Entry(self.panel, textvariable=self.reason, relief="solid", bd=1).pack(fill="x", ipady=7, pady=5)
                self.send_button = self.button(self.panel, "주의 확인 후 그대로 전송", self.send)
                self.send_button.configure(state="disabled")
                self.reason.trace_add("write", self.reason_changed)
            else:
                self.label(self.panel, "변환하거나 위험 정보를 수정한 뒤\n다시 검사하세요.", 10, MUTED)
            self.button(self.panel, "입력 취소", self.cancel)
        elif status == "SAFE":
            self.send_button = self.button(self.panel, "검사한 입력 다시 전송", self.send, True)
        self.label(self.panel, "기초 버전 안내\n규칙 탐지만 구현되어 있어요. 문맥 AI 모델과\n실제 외부 AI 연결은 후속 개발 항목이에요.", 9, MUTED, wraplength=320)

    def reason_changed(self, *args):
        p = self.agent.current
        valid = p and p.content == self.input.get("1.0", "end-1c") and 5 <= len(self.reason.get().strip()) <= 200
        self.send_button.configure(state="normal" if valid else "disabled")

    def cancel(self):
        self.agent.cancel()
        self.fill_input("")
        self.render_panel()

    def preview(self):
        if self.agent.current.content != self.input.get("1.0", "end-1c"):
            raise ValueError("입력이 변경되었습니다. 먼저 다시 검사하세요.")
        preview = self.agent.preview()
        dialog = tk.Toplevel(self.root)
        dialog.title("VEIL · 변환 검토")
        dialog.geometry("780x610")
        dialog.configure(bg=BG, padx=24, pady=20)
        dialog.transient(self.root)
        dialog.grab_set()
        self.label(dialog, "변환 내용을 확인해 주세요", 22, bold=True)
        self.label(dialog, "변환 전 · 내 PC에서만 표시", 11, MUTED)
        self.text_area(dialog, 5, True, self.agent.current.content)
        self.label(dialog, "변환 후 · 승인 후 반드시 재검사", 11, GREEN, True)
        self.text_area(dialog, 5, True, preview.content)

        def approve():
            result = self.agent.approve(preview)
            self.fill_input(self.agent.current.content)
            self.input.edit_modified(False)
            dialog.destroy()
            self.render_panel()
            if result.level == "SAFE":
                self.send()

        self.button(dialog, "변환 승인 및 재검사", approve, True)
        self.button(dialog, "승인하지 않고 돌아가기", dialog.destroy)

    def admin_view(self):
        body = self.shell()
        main = tk.Frame(body, bg=BG, padx=24, pady=16)
        main.pack(fill="both", expand=True)
        self.label(main, "연구실 보안 관리", 24, bold=True)
        self.label(main, "관리자 데모 · 계정, 정책, 통계는 이 PC의 SQLite에 저장됩니다.", color=MUTED)
        tabs = ttk.Notebook(main)
        tabs.pack(fill="both", expand=True, pady=14)
        for title, builder in (("보안 현황", self.dashboard), ("보안 정책", self.policy_form), ("로그 보관 설정", self.retention_form), ("보안 기록", self.logs_view)):
            tab = tk.Frame(tabs, bg=WHITE, padx=22, pady=16)
            tabs.add(tab, text=title)
            builder(tab)

    def dashboard(self, parent):
        logs = self.agent.logs()
        self.label(parent, "현재 보관 중인 처리 기록", 18, bold=True)
        self.label(parent, "분석 횟수가 아닌 전송·취소 기록 기준입니다.", color=MUTED)
        cards = tk.Frame(parent, bg=WHITE)
        cards.pack(fill="x", pady=24)
        for title, value in (("전체", len(logs)), ("안전", sum(r["risk_level"] == "SAFE" for r in logs)), ("주의", sum(r["risk_level"] == "CAUTION" for r in logs)), ("차단", sum(r["risk_level"] == "BLOCKED" for r in logs))):
            card = tk.Frame(cards, bg=BG, padx=24, pady=20)
            card.pack(side="left", expand=True, fill="x", padx=5)
            self.label(card, title, 12, MUTED)
            self.label(card, str(value), 32, GREEN, True)
        self.label(parent, "원문 · 변환문 · 대화 · 가명 대응표는 기록에 포함되지 않습니다.", color=MUTED)
        self.button(parent, "현황 새로고침", self.admin_view)

    def entry_row(self, parent, title, value):
        self.label(parent, title, 10, MUTED)
        var = tk.StringVar(value=str(value))
        tk.Entry(parent, textvariable=var, relief="solid", bd=1).pack(fill="x", ipady=6, pady=(0, 5))
        return var

    def policy_form(self, parent):
        p = self.agent.repository.get_policy()
        self.label(parent, "보안 정책 · 적용 중 v{}".format(p.version), 18, bold=True)
        words = self.entry_row(parent, "보호 키워드 (쉼표 구분)", ", ".join(p.keywords))
        core = self.entry_row(parent, "핵심 키워드 · 발견 즉시 차단 (쉼표 구분)", ", ".join(p.core_keywords))
        caution = self.entry_row(parent, "주의 임계값", p.caution)
        block = self.entry_row(parent, "차단 임계값", p.block)
        self.label(parent, "분석·변환 모드", 10, MUTED)
        mode = tk.StringVar(value=p.mode)
        ttk.Combobox(parent, textvariable=mode, values=("FAST", "PRECISE_DEMO"), state="readonly").pack(fill="x", pady=8)
        self.label(parent, "FAST: 규칙 탐지 + 마스킹\nPRECISE_DEMO: 같은 규칙 탐지 + 인물 가명화 체험 (문맥 모델 미구현)", 10, MUTED)

        def save():
            self.agent.save_policy(keywords=tuple(w.strip() for w in words.get().split(",") if w.strip()),
                core_keywords=tuple(w.strip() for w in core.get().split(",") if w.strip()),
                caution=float(caution.get()), block=float(block.get()), mode=mode.get())
            messagebox.showinfo("VEIL", "정책을 저장했어요. 다음 검사부터 적용됩니다.")
            self.admin_view()
        self.button(parent, "정책 저장", save, True)

    def retention_form(self, parent):
        p = self.agent.repository.get_policy()
        self.label(parent, "로그 보관 설정", 18, bold=True)
        self.label(parent, "최소 기록: 유형·건수 / 상세 기록: 유형별 요약 추가", color=MUTED)
        level = tk.StringVar(value=p.log_level)
        ttk.Combobox(parent, textvariable=level, values=("MINIMAL", "DETAILED"), state="readonly").pack(fill="x", pady=14)
        days = self.entry_row(parent, "보관 기간 (1~365일)", p.retention_days)
        auto = tk.BooleanVar(value=p.auto_delete)
        tk.Checkbutton(parent, text="기한이 지난 기록 자동 삭제", variable=auto, bg=WHITE).pack(anchor="w", pady=14)
        self.label(parent, "앱 실행 중 주기적으로, 기록 추가·조회·설정 저장 시 만료 기록을 삭제합니다.", 10, MUTED, wraplength=700)
        self.label(parent, "이번 버전은 전송 사유의 입력 여부만 저장해요.\n자유 입력 사유 원문은 저장하지 않습니다.", 10, MUTED)

        def save():
            self.agent.save_policy(log_level=level.get(), retention_days=int(days.get()), auto_delete=auto.get())
            messagebox.showinfo("VEIL", "로그 보관 정책을 저장했어요.")
            self.admin_view()
        self.button(parent, "보관 정책 저장", save, True)

    def logs_view(self, parent):
        self.label(parent, "보안 기록", 18, bold=True)
        filters = tk.Frame(parent, bg=WHITE)
        filters.pack(fill="x", pady=8)
        today = datetime.now().astimezone().date()
        start = tk.StringVar(value=(today - timedelta(days=30)).isoformat())
        end = tk.StringVar(value=today.isoformat())
        user = tk.StringVar()
        level = tk.StringVar(value="ALL")
        for title, var, width in (("시작일", start, 11), ("종료일", end, 11), ("사용자 ID", user, 12)):
            tk.Label(filters, text=title, bg=WHITE).pack(side="left", padx=4)
            tk.Entry(filters, textvariable=var, width=width).pack(side="left")
        ttk.Combobox(filters, textvariable=level, values=("ALL", "SAFE", "CAUTION", "BLOCKED"), width=10, state="readonly").pack(side="left", padx=8)
        cols = ("time", "user", "risk", "action", "summary")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=12)
        for col, title, width in zip(cols, ("시각", "연구자", "등급", "처리 결과", "탐지 유형·건수"), (165, 100, 90, 165, 230)):
            tree.heading(col, text=title)
            tree.column(col, width=width, minwidth=60)
        tree.pack(fill="both", expand=True, pady=12)
        scroll = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=scroll.set)
        scroll.pack(fill="x")
        self.log_count = self.label(parent, "", color=MUTED)

        def search():
            first = datetime.strptime(start.get(), "%Y-%m-%d").astimezone()
            last = datetime.strptime(end.get(), "%Y-%m-%d").astimezone()
            if first > last:
                raise ValueError("시작일은 종료일 이후일 수 없습니다.")
            rows = self.agent.logs(level=level.get(), user=user.get().strip(),
                start=first.astimezone(timezone.utc).isoformat(),
                end=(last + timedelta(days=1)).astimezone(timezone.utc).isoformat())
            tree.delete(*tree.get_children())
            for row in rows:
                time = datetime.fromisoformat(row["created_at"]).astimezone().strftime("%m-%d %H:%M:%S")
                tree.insert("", "end", values=(time, row["user_id"], row["risk_level"], row["action"], row["summary"] or row["counts"]))
            self.log_count.configure(text="검색 결과 {}건 · 원문 없음".format(len(rows)))
        self.button(parent, "조회", search, True)
        search()
