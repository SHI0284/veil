"""담당 A(본인): GUI에서 호출하는 유즈케이스 조정자."""
from dataclasses import replace
from .analysis import PromptSanitizer, SecurityAnalyzer
from .domain import Conversation, Prompt
from .gateway import AIGateway, StubAIClient, TransmissionGuard


class PCAgent:
    def __init__(self, repository, ai_client=None):
        self.repository = repository
        self.user = None
        self.conversation = Conversation()
        self.current = None
        self.analyzer = SecurityAnalyzer()
        self.sanitizer = PromptSanitizer()
        self.gateway = AIGateway(ai_client or StubAIClient())
        self.guard = TransmissionGuard()

    def login(self, user, password):
        self.user = self.repository.login(user, password)
        self.new_conversation()
        return self.user

    def require_user(self, role=None):
        if not self.user or (role and self.user["role"] != role):
            raise PermissionError("이 작업을 수행할 계정 권한이 없습니다.")

    def logout(self):
        self.new_conversation()
        self.user = None

    def new_conversation(self):
        self.conversation = Conversation()
        self.current = None

    def analyze(self, text):
        self.require_user("RESEARCHER")
        if not text.strip():
            raise ValueError("프롬프트를 입력하세요.")
        policy = self.repository.get_policy()  # 정책 조회 실패 시 분석/전송 안 함
        if self.current and self.current.status not in ("SENT", "CANCELLED"):
            p = self.current
            if p.content != text:
                p.content = text
                p.revision += 1
                p.converted = False
        else:
            p = Prompt(text)
            self.conversation.prompts.append(p)
            self.current = p
        previous = "CONVERTED" if p.converted else "INPUT"
        p.status, p.result = "ANALYZING", None
        try:
            p.result = self.analyzer.analyze(p, policy, self.conversation)
            p.status = p.result.level
        except Exception:
            p.status = previous
            raise
        return p.result

    def preview(self):
        self.require_user("RESEARCHER")
        if not self.current:
            raise ValueError("먼저 보안 검사를 실행하세요.")
        return self.sanitizer.preview(self.current, self.repository.get_policy(), self.conversation)

    def approve(self, preview):
        self.require_user("RESEARCHER")
        p, policy = self.current, self.repository.get_policy()
        if not p or not p.matches(policy) or p.status not in ("CAUTION", "BLOCKED") or (p.revision, policy.version, p.result.result_id) != (preview.revision, preview.policy_version, preview.result_id):
            raise ValueError("미리보기 이후 입력 또는 정책이 바뀌었습니다. 다시 검사하세요.")
        p.content = preview.content
        p.revision += 1
        p.converted, p.result, p.status = True, None, "CONVERTED"
        return self.analyze(p.content)

    def send(self, text, reason=""):
        self.require_user("RESEARCHER")
        p, policy = self.current, self.repository.get_policy()
        if not p or p.content != text:
            raise ValueError("입력이 변경되었습니다. 보안 검사를 다시 실행하세요.")
        response = self.guard.send(p, policy, self.gateway, reason)
        action = "CONVERTED_SENT" if p.converted else "SENT_WITH_WARNING" if p.result.level == "CAUTION" else "SENT"
        self.repository.add_log(self.user["id"], p, action, policy, reason)
        return response, self.conversation.vault.restore(response)

    def cancel(self):
        self.require_user("RESEARCHER")
        if self.current and self.current.status not in ("SENT", "CANCELLED"):
            self.current.status = "CANCELLED"
            self.repository.add_log(self.user["id"], self.current, "CANCELLED", self.repository.get_policy())

    def save_policy(self, **changes):
        self.require_user("MANAGER")
        current = self.repository.get_policy()
        self.repository.save_policy(replace(current, version=current.version + 1, **changes))

    def logs(self, **filters):
        self.require_user("MANAGER")
        return self.repository.logs(**filters)
