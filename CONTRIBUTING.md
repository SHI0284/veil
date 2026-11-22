# 팀 개발 방법

저장소는 `veil/` 폴더 자체를 루트로 사용합니다. 수업 자료 전체나 개인 DB는 올리지 않습니다. 담당 이름은 팀에서 확정하고 [역할 분담안](docs/TEAM_PLAN.md)에 반영합니다.

## 작업 시작

```powershell
git switch main
git pull --ff-only
git switch -c feature/agent-ui
```

| 담당 | 제안 브랜치 | 주요 파일 |
|---|---|---|
| A · 초기 개발자 | `feature/agent-ui` | 연구자·로그인 HTML, `app.js`, `brand.css`, 유즈케이스 연결 |
| B | `feature/local-analysis` | `analysis.py`, 탐지·가명화 데이터 모델과 테스트 |
| C | `feature/ai-gateway` | `gateway.py`, `openai_client.py`, API·장애 처리 테스트 |
| D | `feature/security-server` | `storage.py`, 관리자 HTML·API, 계정·정책·로그 |

브랜치 이름은 예시입니다. 실제로 맡은 작은 작업에 맞게 붙여도 됩니다. `web.py`, `app.js`, `domain.py`, 공용 CSS는 여러 담당이 함께 사용하므로 수정 전에 범위를 공유합니다.

## 변경 후 확인

```powershell
python -X utf8 -m unittest discover -s tests -p "test_*.py" -v
node --check veil_app/static/app.js
git diff --check
git status --short
```

Node.js는 JavaScript 문법 확인에만 필요합니다. UI를 바꿨으면 브라우저에서 공개 질문·주의 경고·변환 거부·변환 승인·차단·입력 수정·로그아웃을 확인합니다. 실제 API 테스트는 키와 사용량이 필요하며 자동 테스트와 구분해 기록합니다.

Python 코드를 바꾸면 서버를 재시작합니다. HTML은 템플릿 자동 갱신이 켜져 있어 새로고침하면 반영되고 CSS/JS도 새로고침으로 확인합니다. 디버거나 Python 자동 재시작은 켜져 있지 않습니다.

## 올리는 방법

```powershell
git add 수정한파일경로
git commit -m "변경한 동작을 짧게 설명"
git push -u origin 현재브랜치이름
```

GitHub에서 `main` 대상으로 Pull Request를 열고 변경 이유·확인 방법·남은 제한을 적습니다. 한 명 이상 검토한 뒤 합치는 것을 팀 규칙으로 제안합니다. 브랜치 보호나 필수 리뷰 설정이 적용됐다는 의미는 아닙니다.

API 키, `.env`, `data/`, 개인 로그와 실제 연구 원문은 커밋하지 않습니다. 앱 실행 시 생성되는 데이터는 `.gitignore`로 제외합니다. 테스트에는 가상 예시만 사용합니다. 프런트엔드 입력과 응답은 HTML로 실행하지 않고 이스케이프해서 표시하는 규칙을 유지합니다.

팀원의 비공개 저장소 접근 권한은 저장소 소유자가 GitHub의 **Settings → Collaborators**에서 초대해야 합니다. 링크 공유만으로 접근 권한이 생기지는 않습니다.
