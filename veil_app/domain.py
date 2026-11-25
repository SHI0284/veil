"""공유 데이터 모델. GUI/DB 라이브러리에 의존하지 않는다."""
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import uuid4


@dataclass(frozen=True)
class SecurityPolicy:
    version: int = 1
    keywords: tuple = ("비공개", "미공개", "김연구")
    core_keywords: tuple = ("보안과제", "핵심기술", "기밀")
    caution: float = 0.4
    block: float = 0.8
    mode: str = "FAST"
    log_level: str = "MINIMAL"
    retention_days: int = 30
    auto_delete: bool = True
    require_pii_masking: bool = False

    def validate(self):
        if not 0 < self.caution < self.block <= 1:
            raise ValueError("임계값은 0 < 주의 < 차단 ≤ 1이어야 합니다.")
        if not self.keywords or not self.core_keywords:
            raise ValueError("보호·핵심 키워드를 각각 하나 이상 입력하세요.")
        if any(not k.strip() or len(k) > 50 for k in self.keywords + self.core_keywords):
            raise ValueError("키워드는 1~50자로 입력하세요.")
        if set(k.casefold() for k in self.keywords) & set(k.casefold() for k in self.core_keywords):
            raise ValueError("보호·핵심 키워드는 중복될 수 없습니다.")
        if self.mode not in ("FAST", "PRECISE_DEMO"):
            raise ValueError("지원하지 않는 분석 모드입니다.")
        if self.log_level not in ("MINIMAL", "DETAILED"):
            raise ValueError("지원하지 않는 기록 수준입니다.")
        if type(self.retention_days) is not int or not 1 <= self.retention_days <= 365:
            raise ValueError("보관 기간은 1~365일 정수입니다.")
        if type(self.auto_delete) is not bool or type(self.require_pii_masking) is not bool:
            raise ValueError("자동 삭제와 마스킹 설정은 켜기 또는 끄기로 지정하세요.")


@dataclass(frozen=True)
class DetectedItem:
    kind: str
    value: str
    start: int
    end: int
    category: str = "CONFIDENTIAL"
    from_history: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    level: str
    score: float
    items: tuple
    revision: int
    policy_version: int
    content: str
    result_id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def has_current_pii(self):
        return any(not item.from_history and item.kind in {"PHONE", "EMAIL", "IDENTIFIER", "PERSON"}
                   for item in self.items)


@dataclass
class Prompt:
    content: str
    prompt_id: str = field(default_factory=lambda: uuid4().hex)
    original: str = field(init=False)
    revision: int = 1
    status: str = "INPUT"
    converted: bool = False
    result: Optional[AnalysisResult] = None

    def __post_init__(self):
        self.original = self.content

    def matches(self, policy):
        r = self.result
        return bool(r and r.revision == self.revision and r.content == self.content
                    and r.policy_version == policy.version)


@dataclass(frozen=True)
class ConversionPreview:
    content: str
    revision: int
    policy_version: int
    result_id: str


class PseudonymVault:
    """대화 수명 동안만 존재한다. 로그/파일 직렬화 금지."""
    def __init__(self):
        self.mapping = {}
        self.prefix = uuid4().hex[:8]

    def get_or_create(self, value):
        if value not in self.mapping:
            self.mapping[value] = "[연구자-{}-{}]".format(self.prefix, len(self.mapping) + 1)
        return self.mapping[value]

    def restore(self, response):
        for value, pseudonym in self.mapping.items():
            response = response.replace(pseudonym, value)
        return response


@dataclass
class Conversation:
    prompts: List[Prompt] = field(default_factory=list)
    vault: PseudonymVault = field(default_factory=PseudonymVault)

    def recent_before(self, prompt):
        previous = []
        for item in self.prompts:
            if item is prompt:
                break
            if item.status != "CANCELLED":
                previous.append(item.content)
        return previous[-4:]
