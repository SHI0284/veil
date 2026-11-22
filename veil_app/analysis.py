"""담당 B: 탐지 전략·점수·변환. 현재는 규칙 기반 데모 탐지기."""
import re
from .domain import AnalysisResult, ConversionPreview, DetectedItem


class KeywordDetection:
    def detect(self, content, policy):
        items = []
        for category, words in (("CORE_SECRET", policy.core_keywords),
                                ("CONFIDENTIAL", policy.keywords)):
            for word in words:
                for match in re.finditer(re.escape(word), content, re.IGNORECASE):
                    kind = "PERSON" if word == "김연구" and category != "CORE_SECRET" else "KEYWORD"
                    items.append(DetectedItem(kind, match.group(), *match.span(), category))
        return items


class PatternDetection:
    patterns = (
        ("PHONE", r"(?<!\d)01[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)"),
        ("EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        ("IDENTIFIER", r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
        ("PERSON", r"(?<=이름: )[가-힣]{2,4}"),
    )

    def detect(self, content, policy):
        return [DetectedItem(kind, m.group(), *m.span())
                for kind, pattern in self.patterns for m in re.finditer(pattern, content)]


class SecurityAnalyzer:
    def __init__(self):
        self.strategies = (KeywordDetection(), PatternDetection())

    def analyze(self, prompt, policy, conversation):
        from dataclasses import replace
        items = []
        for history, content in [(True, s) for s in conversation.recent_before(prompt)] + [(False, prompt.content)]:
            for strategy in self.strategies:
                items.extend(replace(i, from_history=history) for i in strategy.detect(content, policy))
        unique = {(i.kind, i.value.casefold(), i.category) for i in items}
        # 기초 버전의 설명 가능한 임시 점수. 실제 문맥 모델 점수가 아님.
        score = min(0.95, 0.45 + 0.1 * (len(unique) - 1)) if unique else 0.0
        core = any(i.category == "CORE_SECRET" for i in items)
        level = "BLOCKED" if core or score >= policy.block else "CAUTION" if score >= policy.caution else "SAFE"
        return AnalysisResult(level, round(score, 2), tuple(items), prompt.revision, policy.version, prompt.content)


class PromptSanitizer:
    def preview(self, prompt, policy, conversation):
        if not prompt.matches(policy) or prompt.status not in ("CAUTION", "BLOCKED"):
            raise ValueError("최신 위험 분석 결과가 필요합니다.")
        # 겹치는 탐지는 하나의 구간으로 합친다. 긴 키워드 안의 개인정보 누락 방지.
        current = sorted((i for i in prompt.result.items if not i.from_history), key=lambda i: (i.start, -i.end))
        groups = []
        for item in current:
            if groups and item.start < groups[-1][1]:
                start, end, members = groups[-1]
                groups[-1] = (start, max(end, item.end), members + [item])
            else:
                groups.append((item.start, item.end, [item]))
        content = prompt.content
        for start, end, members in reversed(groups):
            person = all(i.kind == "PERSON" for i in members)
            token = conversation.vault.get_or_create(content[start:end]) if person and policy.mode == "PRECISE_DEMO" else "[보호정보]"
            content = content[:start] + token + content[end:]
        return ConversionPreview(content, prompt.revision, policy.version, prompt.result.result_id)
