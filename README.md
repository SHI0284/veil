# VEIL · 연구자를 위한 프롬프트 보호 작업실

연구자가 AI에 보낼 내용을 PC에서 먼저 검사하고, 필요한 정보를 마스킹·가명화한 뒤 전송하는 **소프트웨어공학 4인 팀 프로젝트의 기초 구현**입니다.

**현재 상태 (2026-11-22):** Flask 웹 화면과 분석 → 변환 검토 → 재검사 → 전송 통제 흐름을 구현했습니다. OpenAI Responses API 호출 코드도 포함되어 있지만, **유효한 API 키를 사용하는 실제 응답 검증은 아직 완료하지 않았습니다.** 정밀 문맥 분석 모델과 중앙 보안 서버는 후속 개발 범위입니다.

![VEIL 연구 작업실](docs/screenshots/veil-studio.jpg)

## 팀원이 처음 볼 문서

- [현재 구현 범위와 인수인계](docs/TEAM_HANDOFF.md): 완료·미완료 구분, 코드 흐름, 먼저 확인할 시나리오
- [4인 역할 분담안](docs/TEAM_PLAN.md): A(초기 개발자)·B·C·D 담당 경계와 후속 과제
- [협업 방법](CONTRIBUTING.md): 브랜치, PR, 테스트, 파일별 담당
- [초기 개발자가 먼저 읽을 코드](docs/FIRST_TASKS.md)

## 설치와 실행

Python 3.9 이상이 필요합니다. 현재 검증 환경은 Windows / Python 3.9.6 / Flask 3.1.0입니다. 프런트엔드는 HTML·CSS·JavaScript이며 Node.js는 앱 실행에 필요하지 않습니다.

공개 저장소이므로 누구나 코드를 열람하거나 clone할 수 있습니다. 팀원이 직접 push하려면 저장소 협업자 권한이 필요합니다.

```powershell
git clone https://github.com/SHI0284/veil.git
cd veil
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 main.py
```

브라우저가 자동으로 열립니다. 주소는 **http://127.0.0.1:5000**입니다. 가상환경 없이 빠르게 실행하려면 Python 설치 후 `start.bat`를 더블클릭해도 됩니다. 이 경우 필요한 Flask를 현재 Python 환경에 설치합니다.

| 로컬 개발용 계정 | 아이디 | 비밀번호 |
|---|---|---|
| 연구자 | `researcher` | `veil1234!` |
| 연구 책임자 | `manager` | `veil1234!` |

처음 실행하면 `data/veil_demo.sqlite3`와 개발용 계정이 자동으로 생성됩니다. 각 팀원의 DB는 독립적이며 저장소에 포함되지 않습니다. 위 계정은 실제 서비스용 계정이 아닙니다.

종료는 실행 터미널에서 `Ctrl+C`입니다. 브라우저만 닫으면 서버는 계속 실행됩니다. 포트 충돌이나 계정 잠금은 다음 명령으로 처리합니다.

```powershell
python -X utf8 main.py --port 5001
python -X utf8 main.py --no-browser
python -X utf8 main.py --reset-demo-locks
```

마지막 명령은 개발용 계정 잠금만 해제하고 종료합니다. 해제 후 앱을 다시 실행하세요. 공개 서버 배포나 GitHub Pages 호스팅을 구성한 저장소는 아닙니다.

## OpenAI 연결

1. [OpenAI API 키](https://platform.openai.com/api-keys)를 발급하고 API 사용 가능한 잔액·권한을 확인합니다.
2. `manager`로 로그인 → **AI 연결** → API 키 입력 → **연결 설정 저장**.
3. 기본 모델은 `gpt-4.1-mini`입니다. 키는 서버 프로세스 메모리에만 보관하며 재시작하면 다시 등록해야 합니다. 서버 시작 전에 `OPENAI_API_KEY` 환경 변수로 설정하는 방법도 지원합니다. 모델 환경 변수는 `OPENAI_MODEL`입니다.
4. 로그아웃 후 `researcher`로 로그인 → 공개 질문 작성 → **검사하고 보내기**.

키는 GitHub·카톡·코드에 넣지 않습니다. `.env` 자동 로드는 구현하지 않았습니다. 키가 없으면 안내 오류가 나오며 모의 답변으로 대체하지 않습니다. 키 등록 표시는 실제 인증 성공을 뜻하지 않으며, 질문에 대한 응답 수신으로 연결을 확인해야 합니다.

실제 요청은 HTTPS `POST https://api.openai.com/v1/responses`, `store: false`, 최대 출력 1,800토큰, 대기 제한 45초를 사용합니다. **현재 승인된 입력만 전송**하며 가명 대응표와 이전 대화는 보내지 않습니다. 이전 최대 4개 입력은 로컬 검사에만 사용하므로 AI의 대화 기억 기능은 아직 없습니다. API 사용 요금은 연결한 계정에 부과됩니다. `store: false`가 공급자의 모든 데이터 보관을 없앤다는 뜻은 아닙니다. [OpenAI 데이터 처리 안내](https://developers.openai.com/api/docs/guides/your-data)

## 사용 흐름

| 화면에서 할 일 | 현재 동작 |
|---|---|
| 공개 논문의 연구 방법 요약 → 검사하고 보내기 | SAFE면 OpenAI 자동 전송. 키 미등록 시 안내와 입력 유지 |
| 새 노트 → 개인정보가 담긴 연구 계획 → 검사 | CAUTION 경고와 변환 미리보기 제공 |
| 변환 미리보기 → 변환 승인 및 재검사 | 승인된 변환문만 재검사. SAFE면 전송 |
| 승인하지 않고 돌아가기 | 원문 유지 |
| 주의 확인 후 전송 | CAUTION에서만 5~200자 사유 확인 후 그대로 전송 |
| 새 노트 → 고민감 정보 검사 | BLOCKED. 그대로 전송하는 경로 없음 |
| 검사 후 입력 수정 | 이전 결과 사용 불가, 재검사 필요 |
| 관리자 → 정책·보안 기록·로그 보관 설정 | 정책 저장, 최소화된 처리 기록 조회, 만료 기록 정리 |

개별 예시를 비교할 때는 **새 노트**를 사용하세요. 같은 노트의 이전 위험 정보도 검사하므로 새 입력만 바꿔도 경고가 남을 수 있습니다. `Ctrl+Enter`는 검사 후 전송 단축키입니다. 가명화 체험은 관리자 정책에서 `PRECISE_DEMO`를 선택합니다.

![변환 전후 비교](docs/screenshots/veil-studio-review.jpg)

## 코드 위치

| 파일 | 역할 |
|---|---|
| `main.py` | 로컬 Flask 서버 실행·주기적 정리 |
| `veil_app/web.py` | HTTP API·역할 검사·CSRF·세션·공유 락 |
| `veil_app/controller.py` | 분석·변환·전송 유즈케이스 연결 |
| `veil_app/domain.py` | 프롬프트·정책·대화·메모리 가명표 |
| `veil_app/analysis.py` | 규칙 기반 탐지, 마스킹·가명화 |
| `veil_app/gateway.py` | 전송 직전 검증, 응답 불명 시 반복 전송 차단 |
| `veil_app/openai_client.py` | OpenAI 호출·키 설정·오류 분류 |
| `veil_app/storage.py` | SQLite 계정·정책·최소화한 로그 |
| `veil_app/templates/` | 로그인·연구 노트·관리자 화면 |
| `veil_app/static/app.js` | 화면 상태·API 요청·입력 제어 |
| `veil_app/static/app.css`, `brand.css` | 기본 스타일·VEIL 작업실 디자인 |
| `tests/test_*.py` | 업무 로직·Flask·OpenAI 어댑터 테스트 |

`desktop_legacy.py`, `veil_app/gui.py`, `tests/gui_smoke.py`는 이전 Tkinter 구현을 비교하기 위해 보관했습니다. 현재 개발·기본 실행 대상은 Flask입니다.

## 데이터와 한계

- 원문·변환문·대화·가명표는 PC의 Flask 프로세스 메모리에 있습니다. DB에는 처리 결과·탐지 유형·건수 등을 기록하며 원문·가명표·사유 원문은 기록하지 않습니다.
- 새 노트·로그아웃·서버 종료 시 해당 대화를 해제하고 유휴 세션은 1시간 후 정리합니다. 브라우저 저장소에는 프롬프트를 저장하지 않습니다.
- 실제 API는 자동 재시도하지 않습니다. 응답을 잃은 요청은 이미 처리·과금됐을 수 있어 `SEND_UNKNOWN` 상태로 두고 반복 전송을 막습니다.
- 분석은 키워드·패턴 기반이며 점수는 임시 규칙 점수입니다. `PRECISE_DEMO`도 정밀 AI 모델이 아닙니다. 모든 민감정보를 탐지한다고 보장할 수 없습니다.
- 중앙 서버·정책 캐시·정밀 문맥 모델·스트리밍·작업 중 취소는 미구현입니다.
- 공유 락으로 요청을 직렬화하므로 AI 응답을 기다리는 동안 다른 세션도 대기합니다. 다중 사용자 서비스 전 작업 큐·비동기 처리 설계가 필요합니다.
- 실제 전송 성공과 감사 로그 저장의 원자성·복구는 후속 과제입니다. 응답 10초·정책 캐시 24시간 등 설계 목표를 달성했다고 주장하지 않습니다.

## 검증

```powershell
python -X utf8 -m unittest discover -s tests -p "test_*.py" -v
node --check veil_app/static/app.js
```

업무 로직 19개 + Flask API 14개 + OpenAI 어댑터 10개 = **43개 테스트**입니다. OpenAI 테스트는 전송 계층을 대체하므로 실제 API에 접속하거나 과금하지 않습니다. 실제 키로 질문 전송·응답 수신은 별도 검증해야 합니다. 브라우저에서 로그인, 입력 집중 모드, 변환 비교, 키 미등록 오류, 관리자 화면과 모바일 배치를 확인했습니다.

## 디자인·참고

팀 GUI 설계와 VEIL 로고를 바탕으로 연구 노트 + 검사 데스크 구조를 구현했습니다. 원본 PNG와 배경을 제거한 PNG를 `veil_app/static/`에 보관했습니다. 이전 발표·설계 원본 문서는 이 저장소에 포함되지 않습니다. Pretendard는 로컬 폰트로 제공하며 [SIL OFL 라이선스](veil_app/static/Pretendard-LICENSE.txt)를 포함했습니다.

- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Flask Quickstart](https://flask.palletsprojects.com/en/stable/quickstart/)
