"""실제 Tk 위젯을 생성하는 로컬 개발 테스트. 실행: python tests/gui_smoke.py

--preview를 붙이면 테스트 완료 후 연구자 화면을 90초 표시한다.
실제 데이터베이스/사용자 계정을 변경하지 않는다.
"""
import sys
import tkinter as tk
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veil_app.controller import PCAgent
from veil_app.gui import VeilApp
from veil_app.storage import LocalRepository

repo = LocalRepository(":memory:")
agent = PCAgent(repo)
root = tk.Tk()
app = VeilApp(root, agent)
root.update()
assert app.password.winfo_viewable()
agent.login("researcher", "veil1234!")
app.researcher_view()
app.fill_input("공개된 논문을 요약해줘")
app.analyze()
root.update()
assert agent.current.status == "SENT"
assert "모의 AI 응답" in app.chat.get("1.0", "end")
app.new_chat()
app.fill_input("김연구의 비공개 계획 010-1234-5678")
app.analyze()
root.update()
assert agent.current.status == "CAUTION"
assert str(app.send_button.cget("state")) == "disabled"
app.reason.set("공개 동의 확인 완료")
root.update()
assert str(app.send_button.cget("state")) == "normal"
app.fill_input("바뀐 입력")
root.update()
assert str(app.send_button.cget("state")) == "disabled"
app.new_chat()
app.fill_input("보안과제")
app.analyze()
root.update()
assert not any("그대로 전송" in str(w.cget("text")) for w in app.panel.winfo_children() if isinstance(w, tk.Button))
app.preview()
root.update()
dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
approve = next(w for w in dialog.winfo_children() if isinstance(w, tk.Button) and "승인 및" in w.cget("text"))
approve.invoke()
root.update()
assert agent.current.status == "SENT"
agent.login("manager", "veil1234!")
app.admin_view()
root.update()
assert "검색 결과" in app.log_count.cget("text")
print("GUI smoke passed: 로그인 화면, 정상 전송, 경고 사유, 입력 변경, 차단, 변환 승인, 관리자 4개 탭")
if "--preview" in sys.argv:
    agent.login("researcher", "veil1234!")
    app.researcher_view()
    app.fill_input("김연구의 비공개 연구 계획을 요약하고 010-1234-5678에 보낼 안내문을 작성해줘.")
    app.analyze()
    root.title("VEIL · GUI 검증 미리보기")
    root.after(90000, root.destroy)
    root.mainloop()
else:
    root.destroy()
repo.close()
