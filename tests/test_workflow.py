import json
import sys
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veil_app.controller import PCAgent
from veil_app.domain import SecurityPolicy
from veil_app.storage import LocalRepository


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.repo = LocalRepository(":memory:")
        self.agent = PCAgent(self.repo)
        self.agent.login("researcher", "veil1234!")

    def tearDown(self):
        self.repo.close()

    def test_safe_prompt_sends_once_and_logs(self):
        text = "공개 논문을 요약해줘"
        self.assertEqual(self.agent.analyze(text).level, "SAFE")
        self.agent.send(text)
        self.assertEqual(self.repo.logs()[0]["action"], "SENT")
        with self.assertRaises(ValueError):
            self.agent.send(text)
        self.assertEqual(self.agent.gateway.client.calls, 1)

    def test_blocked_cannot_send_even_with_reason(self):
        text = "보안과제 핵심기술"
        self.assertEqual(self.agent.analyze(text).level, "BLOCKED")
        with self.assertRaises(ValueError):
            self.agent.send(text, "책임자 승인 완료")
        self.assertEqual(self.agent.gateway.client.calls, 0)

    def test_caution_requires_reason_and_logs_no_raw_values(self):
        text = "010-1234-5678에게 연락해줘"
        self.agent.analyze(text)
        with self.assertRaises(ValueError):
            self.agent.send(text, "짧음")
        self.agent.send(text, "010-9999-1111의 승인 완료")
        data = json.dumps(self.repo.logs(), ensure_ascii=False)
        self.assertNotIn("010-1234-5678", data)
        self.assertNotIn("010-9999-1111", data)
        self.assertEqual(self.repo.logs()[0]["action"], "SENT_WITH_WARNING")

    def test_changed_text_requires_reanalysis(self):
        self.agent.analyze("공개 논문")
        with self.assertRaises(ValueError):
            self.agent.send("보안과제")
        # GUI를 우회해 모델을 직접 바꿔도 결과 본문과 불일치하면 차단.
        self.agent.current.content = "보안과제"
        with self.assertRaises(ValueError):
            self.agent.send("보안과제")
        self.assertEqual(self.agent.gateway.client.calls, 0)

    def test_policy_change_invalidates_analysis_and_preview(self):
        self.agent.analyze("김연구")
        preview = self.agent.preview()
        self.repo.save_policy(replace(self.repo.get_policy(), version=2))
        with self.assertRaises(ValueError):
            self.agent.approve(preview)
        with self.assertRaises(ValueError):
            self.agent.send("김연구", "책임자 승인 완료")

    def test_rejected_preview_keeps_original(self):
        self.agent.analyze("김연구 010-1234-5678")
        before = self.agent.current.content
        self.agent.preview()
        self.assertEqual(self.agent.current.content, before)
        self.assertEqual(self.agent.current.revision, 1)

    def test_conversion_reanalysis_and_log(self):
        text = "김연구의 비공개 계획 010-1234-5678"
        self.agent.analyze(text)
        result = self.agent.approve(self.agent.preview())
        self.assertEqual(result.level, "SAFE")
        self.assertEqual(self.agent.current.original, text)
        self.assertEqual(self.agent.current.revision, 2)
        self.agent.send(self.agent.current.content)
        self.assertEqual(self.repo.logs()[0]["action"], "CONVERTED_SENT")

    def test_pseudonym_consistency_restore_and_new_conversation(self):
        self.repo.save_policy(replace(self.repo.get_policy(), version=2, mode="PRECISE_DEMO"))
        self.agent.analyze("김연구 김연구 010-1234-5678")
        self.agent.approve(self.agent.preview())
        token = self.agent.conversation.vault.mapping["김연구"]
        self.assertEqual(self.agent.current.content.count(token), 2)
        raw, restored = self.agent.send(self.agent.current.content)
        self.assertIn(token, raw)
        self.assertIn("김연구", restored)
        self.assertNotIn("010-1234-5678", restored)
        self.agent.analyze("김연구")
        self.assertEqual(self.agent.preview().content, token)
        self.agent.new_conversation()
        self.assertEqual(self.agent.conversation.vault.mapping, {})

    def test_history_is_checked_and_not_silently_erased(self):
        self.agent.analyze("김연구")
        self.agent.send("김연구", "공개 동의 확인 완료")
        result = self.agent.analyze("일정만 알려줘")
        self.assertEqual(result.level, "CAUTION")
        self.assertTrue(any(i.from_history for i in result.items))
        self.assertEqual(self.agent.approve(self.agent.preview()).level, "CAUTION")

    def test_only_four_previous_prompts_used(self):
        self.agent.analyze("김연구")
        self.agent.send("김연구", "공개 동의 확인 완료")
        for n in range(4):
            text = "공개 자료 {}".format(n)
            self.agent.analyze(text)
            self.agent.send(text, "공개 동의 확인 완료")
        self.assertEqual(self.agent.analyze("공개 정보").level, "SAFE")

    def test_timeout_retries_twice_and_preserves_state(self):
        self.agent.analyze("공개 자료")
        self.agent.gateway.client.scenario = "TIMEOUT"
        with self.assertRaises(TimeoutError):
            self.agent.send("공개 자료")
        self.assertEqual(self.agent.gateway.client.calls, 3)
        self.assertEqual(self.agent.current.status, "SAFE")
        self.assertEqual(self.repo.logs(), [])

    def test_error_does_not_retry(self):
        self.agent.analyze("공개 자료")
        self.agent.gateway.client.scenario = "ERROR"
        with self.assertRaises(ConnectionError):
            self.agent.send("공개 자료")
        self.assertEqual(self.agent.gateway.client.calls, 1)
        self.assertEqual(self.repo.logs(), [])

    def test_five_failed_logins_lock_account(self):
        for n in range(5):
            with self.assertRaises(ValueError):
                self.repo.login("researcher", "wrong")
        with self.assertRaises(ValueError):
            self.repo.login("researcher", "veil1234!")

    def test_researcher_cannot_modify_policy_or_read_logs(self):
        with self.assertRaises(PermissionError):
            self.agent.save_policy(caution=0.3)
        with self.assertRaises(PermissionError):
            self.agent.logs()

    def test_admin_validates_and_persists_policy(self):
        self.agent.login("manager", "veil1234!")
        with self.assertRaises(ValueError):
            self.agent.save_policy(caution=0.9, block=0.8)
        with self.assertRaises(ValueError):
            self.agent.save_policy(keywords=("기밀",))
        self.assertEqual(self.repo.get_policy().version, 1)
        self.agent.save_policy(caution=0.3)
        self.assertEqual(self.repo.get_policy().version, 2)

    def test_log_retention_and_toggle(self):
        self.agent.analyze("공개 자료")
        self.agent.send("공개 자료")
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        self.repo.db.execute("UPDATE security_log SET created_at=?", (old,))
        self.repo.db.commit()
        self.repo.save_policy(replace(self.repo.get_policy(), version=2, auto_delete=False))
        self.assertEqual(len(self.repo.logs()), 1)
        self.repo.save_policy(replace(self.repo.get_policy(), version=3, auto_delete=True))
        self.assertEqual(self.repo.logs(), [])

    def test_failed_analysis_is_not_sendable(self):
        def fail(*args):
            raise TimeoutError("분석 실패")
        self.agent.analyzer.analyze = fail
        with self.assertRaises(TimeoutError):
            self.agent.analyze("공개 자료")
        self.assertEqual(self.agent.current.status, "INPUT")
        with self.assertRaises(ValueError):
            self.agent.send("공개 자료")

    def test_overlapping_detections_are_fully_masked(self):
        self.repo.save_policy(replace(self.repo.get_policy(), version=2, keywords=("010-1234",)))
        self.agent.analyze("010-1234-5678")
        self.assertEqual(self.agent.preview().content, "[보호정보]")

    def test_cancel_and_logout_clear_conversation(self):
        self.agent.analyze("보안과제")
        self.agent.cancel()
        self.assertEqual(self.repo.logs()[0]["action"], "CANCELLED")
        with self.assertRaises(ValueError):
            self.agent.send("보안과제", "확인 후 전송")
        self.agent.logout()
        self.assertIsNone(self.agent.current)
        self.assertEqual(self.agent.conversation.prompts, [])
        with self.assertRaises(PermissionError):
            self.agent.analyze("공개 자료")


if __name__ == "__main__":
    unittest.main()
