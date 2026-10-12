# AI Agent Guidelines & Policies (AGENTS.md)

이 문서는 이 리포지토리에서 작업하는 AI 에이전트(Antigravity 등)가 준수해야 하는 운영 지침과 정책을 정의합니다.

---

## 📌 Git Commit Policy (깃 커밋 정책)

AI 에이전트가 Git 커밋을 수행할 때는 반드시 다음 규칙을 엄격히 준수해야 합니다.

1. **Commit Title (커밋 제목)**
   - **영어(English)** 로 작성합니다.
   - 직관적이고 명확하게 Conventional Commits 형식을 따릅니다.
     - `feat:` 새로운 기능 추가 / 기능 개선
     - `fix:` 버그 수정
     - `refactor:` 코드 리팩터링
     - `docs:` 문서 수정
     - `chore:` 기타 잡무 / 설정 변경
   - 명령문 형태로 간결하게 작성합니다. (예: `feat: allow defaulting to current directory in pre_srt and post_srt scripts`)

2. **Commit Body (커밋 본문)**
   - **한글(Korean)** 로 자세하게 작성합니다.
   - 변경된 파일 목록과 각 파일별 주요 변경점, 설계 의도 및 변경 사유를 글머리 기호(`-`)로 상세히 기록합니다.
   - 줄바꿈으로 제목과 본문을 명확히 구분합니다.

### 커밋 메시지 예시
```text
feat: allow defaulting to current directory in pre_srt and post_srt scripts

- pre_srt.py: 경로 인자가 지정되지 않은 경우(len(sys.argv) < 2) 사용법 출력 후 종료하는 대신 현재 작업 디렉토리(os.getcwd())를 기본값으로 사용하도록 개선
- post_srt.py: argparse의 directory 인자를 선택적(nargs="?", default=".")으로 변경하여 경로 생략 시 현재 디렉토리를 기본값으로 사용하도록 수정 및 작업 디렉토리 경로 출력 추가
- README.md: pre_srt 및 post_srt 스크립트 실행 가이드에 경로 생략 시 현재 디렉토리 기준 동작 설명 추가
```

---

