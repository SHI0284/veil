# 본인이 먼저 할 개발 · Flask 전환 후

본인(A)은 **웹 GUI와 전체 유즈케이스 연결**을 맡습니다. 기존 Tkinter의 gui.py 대신 아래 파일부터 읽고 수정합니다.

## 먼저 실행

start.bat를 실행하고 researcher / veil1234!로 로그인합니다. 개인정보가 담긴 연구 계획 → 검사하고 보내기 → 변환 미리보기를 확인하세요. 승인 후 실제 전송하려면 관리자 AI 연결에서 유효한 키를 먼저 등록합니다.

## 한 흐름만 읽기

1. veil_app/templates/workspace.html: 상단 메뉴·연구 노트·하단 검사 데스크 배치.
2. veil_app/static/app.css와 brand.css: 기본 스타일과 현재 VEIL 디자인·반응형 규칙.
3. static/app.js의 analyze(): 입력을 /api/analyze에 전달.
4. web.py의 analyze(): 세션/권한을 확인하고 기존 PCAgent.analyze 호출.
5. controller.py → analysis.py: 정책과 대화에 따라 분석.
6. app.js의 renderPanel(): 주의/차단/미리보기/응답 화면 전환.
7. /api/preview → /api/approve: 서버에 저장된 미리보기만 승인하고 재검사.
8. /api/send → TransmissionGuard → OpenAIClient: 전송 통제 후 Responses API 응답. 관리자 AI 연결에서 키를 먼저 등록합니다.
9. PCAgent.send(): 기존 기록 및 가명 복원.

## 첫 직접 수정

- brand.css의 :root 색상과 검사 데스크 여백을 조정해 GUI를 이해합니다.
- HTML에서 안내 문구를 바꾸고 새로고침해 결과를 확인합니다.
- app.js에서 탐지 유형 설명이나 접근성 피드백 하나를 개선합니다.
- 이미 적용된 입력 수정 → STALE 안내 → 재검사 흐름을 유지합니다.
- 사용자 입력을 innerHTML에 그대로 넣거나 localStorage에 저장하지 않습니다.

## 팀에게 넘길 경계

- A: workspace.html/login.html, app.js의 연구자 흐름, web.py의 연구자 API 연결.
- B: analysis.py와 탐지 데이터 모델.
- C: gateway.py와 실제 AI 클라이언트.
- D: admin.html, app.js의 관리자 영역, storage.py와 서버 API.
- 공용 CSS와 web.py 변경은 동시에 덮어쓰지 않도록 PR로 합칩니다. 먼저 app.js를 연구자/관리자 JS로 분리하는 작업도 좋은 본인 과제입니다.

## 실제 API 연결 후 다음 작업

실제 OpenAI 연결과 45초 대기 제한, 응답 불명 시 자동 재전송 금지가 구현됐습니다. 키는 관리자 화면에서 등록하며 서버 메모리에만 보관됩니다. 브라우저는 fetch 중 입력을 잠그지만 Python 호출은 동기식이고 공유 락을 사용합니다. C와 함께 작업 큐, 작업 ID, 취소, 완료 시 revision 재검증을 추가하세요. 서버 호출은 아직 병렬 처리되지 않습니다.

## 수정 후 확인

```powershell
python -m unittest discover -s tests -v
node --check veil_app/static/app.js
```

브라우저에서 공개·주의·차단·변환 거부·변환 승인·입력 수정·로그아웃을 확인하세요. Python 파일을 바꾸면 서버를 재시작하고 다시 로그인합니다. CSS/JS/HTML 변경 후에는 브라우저를 새로고침합니다. debug/reloader는 기본적으로 꺼져 있습니다.
