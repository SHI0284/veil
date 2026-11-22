"""OpenAI Responses adapter. Keys remain in process memory; no prompt logging."""
import json
import http.client
import os
import re
import socket
import urllib.error
import urllib.request


class ProviderError(ConnectionError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class AISettings:
    def __init__(self):
        self._key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    def public(self):
        return {"provider": "OpenAI", "model": self.model,
                "configured": bool(self._key), "is_demo": False}

    def update(self, key, model):
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", model):
            raise ValueError("올바른 모델 이름을 입력하세요.")
        if not isinstance(key, str) or (key and (not key.startswith("sk-") or not key.isascii() or any(c.isspace() for c in key) or len(key) > 512)):
            raise ValueError("OpenAI API 키 형식을 확인하세요.")
        if key:
            self._key = key
        self.model = model


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAIClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport or urllib.request.build_opener(NoRedirect()).open

    def request(self, content):
        if not self.settings._key:
            raise ProviderError("관리자 콘솔의 AI 연결에서 OpenAI API 키를 등록하세요.")
        body = {"model": self.settings.model, "input": content, "store": False,
                "max_output_tokens": 1800,
                "instructions": "한국어로 연구자의 질문에 답하세요. 입력의 [보호정보] 및 대괄호 안 가명은 추측하거나 바꾸지 말고 그대로 유지하세요."}
        req = urllib.request.Request("https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"Authorization": "Bearer " + self.settings._key, "Content-Type": "application/json"})
        try:
            with self.transport(req, timeout=45) as response:
                data = json.loads(response.read(2 * 1024 * 1024))
        except urllib.error.HTTPError as exc:
            messages = {401: "API 키 인증에 실패했어요. 관리자 AI 연결 설정을 확인하세요.",
                        403: "이 API 키에는 요청 권한이 없어요.",
                        429: "OpenAI 사용 한도 또는 요청 한도를 확인하세요.",
                        400: "OpenAI 요청 설정을 확인하세요. 선택한 모델이 Responses API를 지원해야 합니다.",
                        404: "선택한 모델을 사용할 수 없어요. 모델 이름과 접근 권한을 확인하세요."}
            raise ProviderError(messages.get(exc.code, "OpenAI 응답을 확인하지 못했어요."), uncertain=exc.code >= 500) from None
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, ValueError, http.client.HTTPException):
            raise ProviderError("응답을 확인하지 못했어요. 이미 처리됐을 수 있어 자동 재전송하지 않습니다.", uncertain=True) from None
        if not isinstance(data, dict) or data.get("status") != "completed":
            raise ProviderError("AI 응답이 완료되지 않았어요. 출력 한도 또는 공급자 상태를 확인하세요.", uncertain=True)
        parts = []
        output = data.get("output")
        if not isinstance(output, list):
            raise ProviderError("응답 형식을 확인하지 못했어요. 요청은 처리됐을 수 있습니다.", uncertain=True)
        for item in output:
            if isinstance(item, dict) and item.get("type") == "message":
                blocks = item.get("content")
                if not isinstance(blocks, list):
                    raise ProviderError("응답 형식을 확인하지 못했어요. 요청은 처리됐을 수 있습니다.", uncertain=True)
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                        parts.append(block["text"])
                    elif block.get("type") == "refusal" and isinstance(block.get("refusal"), str):
                        parts.append(block["refusal"])
        if not parts:
            raise ProviderError("표시할 텍스트 응답이 없어요. 요청은 처리됐을 수 있습니다.", uncertain=True)
        return "\n".join(parts)
