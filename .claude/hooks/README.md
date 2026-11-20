# hooks 안내

Claude Code가 도구를 실행하기 **직전**(PreToolUse)에 돌아가는 안전장치다. 셸 대신 파이썬으로 써서 Mac(`python3`)과 Windows(`python`)에서 모두 돈다. 등록은 `.claude/settings.json`.

| 스크립트 | 대상 | 막는 것 |
|---|---|---|
| `guard_edit.py` | Edit / Write | `.env`, `.env.*`(단 `.env.example` 등 템플릿은 허용), `docs/lectures/` 아래 파일 수정 |
| `guard_commit.py` | Bash(`git commit`) | `.env` 스테이징, 추가된 줄의 Google API 키 패턴(`AIza…`)·디스코드 웹훅 URL 패턴 |

막으면 종료 코드 2와 이유를 Claude에게 돌려준다. 찾은 비밀값 자체는 출력하지 않고 **파일:줄 번호**만 보여 준다.

## guard_commit.py가 검사하는 것
- 스테이징된 변경(`git diff --cached`)의 파일명과 **추가된 줄**.
- `git commit -a/--all/-am`: 추적 중인 파일의 작업 트리 변경도 함께.
- **같은 명령 안의 `git add … && git commit`**: 훅이 도는 시점에는 아직 스테이징 전이라, add 대상을 직접 검사한다.
  - 파일을 명시하면(`git add a.py`) 그 파일만, `.`/`-A`/`*`/디렉터리면 추적되지 않은 새 파일 전체(`.gitignore` 된 것은 제외)를 검사한다. `git add -u`는 수정된 추적 파일만.
- `git -C <경로> commit`, `cd <경로> && git commit`: 명령에 적힌 **실제 대상 저장소**를 검사한다. 같은 명령 앞에서 `T=경로;`로 정의한 변수와 환경변수는 풀어서 쓴다.

## 알려진 한계 (알고 쓰기)
- **셸 변수를 못 풀면 차단한다.** `cd`/`git -C` 경로에 풀 수 없는 `$변수`가 남으면 어느 저장소인지 검사할 수 없어서 막는다. 경로를 직접 쓰거나 `git add`와 `git commit`을 따로 실행한다.
- **명령 텍스트만 본다.** 문자열 안에 `git commit`이 들어 있으면(예: 테스트 스크립트를 heredoc으로 쓸 때) 진짜 커밋으로 오인해 막을 수 있다. 이때는 파일로 먼저 쓴 뒤 실행하면 된다.
- 같은 명령에서 폴더를 지웠다 다시 만드는 경우(`rm -rf $T && … git commit`)는 지우기 **전** 상태를 보고 판단한다.
- `guard_edit.py`는 Edit/Write 도구만 본다. Bash로 `echo > .env`처럼 쓰는 것은 막지 못한다(커밋은 `guard_commit.py`가 막는다).
- 패턴은 Google API 키(`AIza…`)와 디스코드 웹훅 URL뿐이다. 다른 서비스의 키는 잡지 못한다.
- 훅 실행에 파이썬이 없으면 훅이 실패해서(종료 코드 2가 아님) **막지 못하고 지나간다.** Python이 설치돼 있어야 한다.
- 훅이 막았더라도 이미 키가 노출됐다면 그 키는 폐기하고 새로 발급한다.

## 테스트하는 방법
**1) 스크립트 단독 테스트(자동, 61개)** — 임시 폴더에 git 저장소를 만들어 확인하므로 프로젝트에는 영향이 없다.
```
python3 .claude/hooks/test_hooks.py      # Windows: python .claude/hooks/test_hooks.py
```
끝에 `합계 61개 중 통과 61, 실패 0`이 나오면 정상이다(실패가 있으면 종료 코드 1). 개별 확인:
```
echo '{"tool_input":{"file_path":".env"}}' | python3 .claude/hooks/guard_edit.py; echo $?    # 2 (차단)
echo '{"tool_input":{"file_path":".env.example"}}' | python3 .claude/hooks/guard_edit.py; echo $?   # 0 (통과)
```

**2) 실제 세션 테스트** — Claude Code 안에서 훅이 정말 연결됐는지 본다. 새 세션이거나 `.claude/settings.json`을 방금 만들었다면 `/hooks`로 확인하거나 세션을 다시 연다.
- Claude에게 ".env 파일 만들어 줘"라고 한다 → `[guard_edit] 차단` 메시지가 나오고 파일이 안 생겨야 한다.
- 임시 폴더에 git 저장소를 만들고 가짜 키(`AIza` + 영문 35자)를 넣은 파일을 `git add` 한 뒤 Claude에게 그 폴더에서 커밋하라고 한다 → `[guard_commit] 커밋 차단`. 깨끗한 파일은 통과해야 한다. **프로젝트 저장소에서 시험하지 않는다**(차단이 실패하면 실제로 커밋될 수 있다).

> Windows(권현진)에서는 아직 실행해 보지 않았다. pull 받은 뒤 위 1)을 한 번 실행해서 결과를 공유한다.
