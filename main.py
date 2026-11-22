"""VEIL local Flask app. python main.py -> http://127.0.0.1:5000"""
import argparse
import threading
import time
import webbrowser
from pathlib import Path
from werkzeug.serving import make_server
from veil_app.storage import LocalRepository
from veil_app.web import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--reset-demo-locks', action='store_true')
    args = parser.parse_args()
    if args.reset_demo_locks:
        folder = Path(__file__).resolve().parent / 'data'
        folder.mkdir(exist_ok=True)
        repo = LocalRepository(folder / 'veil_demo.sqlite3')
        repo.db.execute('UPDATE users SET failures=0, locked=0')
        repo.db.commit()
        repo.close()
        print('Demo account locks reset.')
        return
    app = create_app()
    server = make_server('127.0.0.1', args.port, app, threaded=True)
    url = 'http://127.0.0.1:{}/'.format(args.port)
    print('VEIL is running at ' + url, flush=True)
    stop = threading.Event()

    def cleanup():
        while not stop.wait(60):
            with app.extensions['veil_lock']:
                app.extensions['veil_repository'].purge()
                for sid, state in list(app.extensions['veil_states'].items()):
                    if time.monotonic() - state['accessed'] > 3600:
                        state['agent'].logout()
                        del app.extensions['veil_states'][sid]

    threading.Thread(target=cleanup, daemon=True).start()
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        app.extensions['veil_repository'].close()


if __name__ == '__main__':
    main()
