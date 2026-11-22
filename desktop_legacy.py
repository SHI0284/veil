"""실행: python main.py. Python 표준 라이브러리만 사용."""
import argparse
import socket
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from veil_app.controller import PCAgent
from veil_app.gui import VeilApp
from veil_app.storage import LocalRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-demo-locks", action="store_true", help="데모 계정의 로그인 잠금만 해제")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent / "data"
    directory.mkdir(exist_ok=True)
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", 54187))
    except OSError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("VEIL", "VEIL이 이미 실행 중이거나 실행 확인용 포트(54187)가 사용 중입니다.")
        root.destroy()
        return
    repo = LocalRepository(directory / "veil_demo.sqlite3")
    if args.reset_demo_locks:
        repo.db.execute("UPDATE users SET failures=0, locked=0")
        repo.db.commit()
        repo.close()
        lock.close()
        print("데모 계정 잠금 해제 완료")
        return
    root = tk.Tk()
    agent = PCAgent(repo)
    VeilApp(root, agent)

    def purge():
        try:
            repo.purge()
        finally:
            root.after(60000, purge)

    def close():
        agent.logout()
        repo.close()
        lock.close()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", close)
    root.after(60000, purge)
    root.mainloop()


if __name__ == "__main__":
    main()
