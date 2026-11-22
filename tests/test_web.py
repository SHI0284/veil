"""Flask 어댑터 회귀 테스트. 네트워크/브라우저 없이 독립 메모리 DB 사용."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veil_app.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(":memory:", testing=True)
        self.client = self.app.test_client()
        self.csrf = self.client.get("/api/session").json["csrf"]

    def tearDown(self):
        self.app.extensions["veil_repository"].close()

    def post(self, route, data, client=None, csrf=None):
        return (client or self.client).post("/api/" + route, json=data,
            headers={"X-CSRF-Token": csrf or self.csrf})

    def login(self, user="researcher"):
        result = self.post("login", {"username":user,"password":"veil1234!"})
        self.assertEqual(result.status_code, 200, result.json)
        self.csrf = result.json["csrf"]
        return result.json

    def analyze(self, text):
        result = self.post("analyze", {"content":text})
        self.assertEqual(result.status_code, 200, result.json)
        p = result.json["prompt"]
        return {"prompt_id":p["id"],"result_id":p["result"]["id"],"content":p["content"]}

    def test_pages_assets_and_security_headers(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for asset in ("app.css", "app.js"):
            response = self.client.get("/static/" + asset)
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(self.client.get("/workspace").status_code, 302)

    def test_csrf_and_origin_rejected(self):
        self.assertEqual(self.client.post("/api/login",json={}).status_code,403)
        self.assertEqual(self.client.post("/api/login",json={},
            headers={"X-CSRF-Token":self.csrf,"Origin":"https://other.example"}).status_code,403)

    def test_login_rotates_csrf_and_cookie_has_no_content(self):
        before=self.csrf
        self.login()
        self.assertNotEqual(before,self.csrf)
        self.analyze("김연구")
        with self.client.session_transaction() as session:
            self.assertEqual(set(session), {"sid","csrf"})

    def test_roles_enforced_for_api_and_html(self):
        self.assertEqual(self.post("analyze",{"content":"공개 자료"}).status_code,401)
        self.login()
        self.assertEqual(self.client.get("/admin").status_code,403)
        self.assertEqual(self.client.get("/api/logs").status_code,403)
        self.assertEqual(self.post("policy",{"version":1,"caution":0.3}).status_code,403)

    def test_safe_workflow_and_duplicate_send(self):
        self.login()
        data=self.analyze("공개 논문 요약")
        result=self.post("send",data)
        self.assertEqual(result.json["prompt"]["status"],"SENT")
        self.assertEqual(len(result.json["messages"]),2)
        self.assertEqual(self.post("send",data).status_code,400)

    def test_block_and_reason_rules_remain(self):
        self.login()
        blocked=self.analyze("핵심기술")
        self.assertEqual(self.post("send",{**blocked,"reason":"공개 동의 완료"}).status_code,400)
        caution=self.analyze("010-1234-5678")
        self.assertEqual(self.post("send",caution).status_code,400)
        self.assertEqual(self.post("send",{**caution,"reason":"공개 동의 확인 완료"}).status_code,200)

    def test_preview_server_owned_and_reanalyzed(self):
        self.login()
        data=self.analyze("김연구 비공개 010-1234-5678")
        preview=self.post("preview",data).json
        self.assertNotIn("010-1234-5678", preview["after"])
        self.assertEqual(self.post("approve",{**data,"token":"tampered"}).status_code,400)
        result=self.post("approve",{**data,"token":preview["token"],"after":"보안과제"})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json["prompt"]["result"]["level"],"SAFE")
        self.assertNotIn("보안과제",result.json["prompt"]["content"])

    def test_stale_edit_preview_and_cross_tab_result(self):
        self.login()
        data=self.analyze("김연구")
        preview=self.post("preview",data).json
        self.analyze("보안과제")
        self.assertEqual(self.post("approve",{**data,"token":preview["token"]}).status_code,400)
        self.assertEqual(self.post("send",{**data,"reason":"확인 완료입니다"}).status_code,400)

    def test_sessions_isolated_and_logout_clears_memory(self):
        self.login()
        self.analyze("김연구")
        other=self.app.test_client()
        self.assertIsNone(other.get("/api/session").json["user"])
        self.assertEqual(self.post("logout",{}).status_code,200)
        self.assertEqual(self.app.extensions["veil_states"],{})
        self.assertIsNone(self.client.get("/api/session").json["user"])

    def test_policy_version_change_blocks_old_send(self):
        self.login()
        data=self.analyze("공개 정보")
        admin=self.app.test_client()
        csrf=admin.get("/api/session").json["csrf"]
        login=self.post("login",{"username":"manager","password":"veil1234!"},admin,csrf).json
        changed=self.post("policy",{"version":1,"caution":0.3},admin,login["csrf"])
        self.assertEqual(changed.status_code,200)
        self.assertEqual(self.post("send",data).status_code,400)
        self.assertEqual(self.post("policy",{"version":1,"caution":0.4},admin,login["csrf"]).status_code,400)

    def test_timeout_and_error_preserve_retry(self):
        self.login()
        data=self.analyze("공개 정보")
        self.post("scenario",{"scenario":"TIMEOUT"})
        self.assertEqual(self.post("send",data).status_code,503)
        snapshot=self.client.get("/api/session").json
        self.assertEqual(snapshot["prompt"]["status"],"SAFE")
        self.assertEqual(snapshot["messages"],[])
        self.post("scenario",{"scenario":"SUCCESS"})
        self.assertEqual(self.post("send",data).status_code,200)

    def test_log_search_and_no_raw_data(self):
        self.login()
        data=self.analyze("010-1234-5678")
        self.post("send",{**data,"reason":"010-9999-1111 확인 완료"})
        self.login("manager")
        logs=self.client.get("/api/logs?level=CAUTION").json["logs"]
        self.assertEqual(len(logs),1)
        self.assertNotIn("010-",str(logs))
        self.assertEqual(self.client.get("/api/logs?start=2026-12-01&end=2026-01-01").status_code,400)
        self.assertEqual(self.client.get("/api/logs?level=INVALID").status_code,400)

    def test_request_shape_errors_and_session_expiry(self):
        self.login()
        self.assertEqual(self.post("analyze",{"content":[]}).status_code,400)
        self.assertEqual(self.post("scenario",{"scenario":"OTHER"}).status_code,400)
        for value in self.app.extensions["veil_states"].values():
            value["accessed"]-=3601
        self.assertIsNone(self.client.get("/api/session").json["user"])

    def test_admin_forms_and_validation(self):
        self.login("manager")
        self.assertEqual(self.client.get("/admin").status_code,200)
        self.assertEqual(self.post("policy",{"version":1,"caution":"bad"}).status_code,400)
        self.assertEqual(self.post("policy",{"version":1,"retention_days":0}).status_code,400)
        self.assertEqual(self.post("policy",{"version":1,"auto_delete":"false"}).status_code,400)
        self.assertEqual(self.post("policy",{"version":1,"mode":"PRECISE_DEMO"}).status_code,200)


if __name__ == "__main__":
    unittest.main()
