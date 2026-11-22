"""담당 C: 단일 전송 통제 경로와 AI 공급자 교체 지점."""
from .openai_client import ProviderError


class StubAIClient:
    """네트워크 호출 없음. 성공/시간 초과/오류를 재현한다."""
    def __init__(self):
        self.scenario = "SUCCESS"
        self.calls = 0

    def request(self, content):
        self.calls += 1
        if self.scenario == "TIMEOUT":
            raise TimeoutError("모의 응답 시간 초과")
        if self.scenario == "ERROR":
            raise ConnectionError("모의 AI 연결 오류")
        return "[모의 AI 응답 · 외부 전송 없음]\n\n검토할 요청:\n{}\n\n연구 목적, 방법, 일정 순서로 검토해 보세요.".format(content)


class AIGateway:
    def __init__(self, client):
        self.client = client

    def send_prompt(self, content):
        return self.client.request(content)


class TransmissionGuard:
    def send(self, prompt, policy, gateway, reason=""):
        if not prompt.matches(policy) or prompt.status not in ("SAFE", "CAUTION"):
            raise ValueError("전송 불가: 최신 검사를 통과한 프롬프트만 보낼 수 있습니다.")
        if prompt.result.level == "BLOCKED":
            raise ValueError("고위험 프롬프트는 전송할 수 없습니다.")
        if prompt.result.level == "CAUTION" and not 5 <= len(reason.strip()) <= 200:
            raise ValueError("주의 확인 후 전송하려면 사유를 5~200자로 입력하세요.")
        # Real requests are never automatically retried: a lost response may still be billed.
        for attempt in range(3):
            try:
                response = gateway.send_prompt(prompt.content)
                prompt.status = "SENT"
                return response
            except ProviderError as exc:
                if exc.uncertain:
                    prompt.status = "SEND_UNKNOWN"
                raise
            except TimeoutError:
                if attempt == 2:
                    raise TimeoutError("자동 재시도 2회 후 실패했습니다. 입력과 분석 결과를 유지합니다.")
