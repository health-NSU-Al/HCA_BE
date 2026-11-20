# 만성질환자 복약·측정 기록 에이전트

생성형AI활용프로그래밍 기말 팀프로젝트(2인, 발표 12/10). 고혈압·당뇨·심방세동을 가진 **가상 사용자**의 복약·측정을 기록하고 진료 리포트를 만들어 주는 에이전트.
사용 기술 4개: **도구 호출, RAG, MCP, LangGraph** (+ Gradio 화면, 디스코드 웹훅 알림).

## 문서 우선순위
`docs/planning/결정사항.md` > `시나리오.md` > `기획서.md`
- 기획서의 Ollama/qwen3 내용은 **이전 결정**이다. 현재 LLM은 결정사항.md 3장(Gemini, `langchain-google-genai`)을 따른다.
- 폴더 구조·담당은 결정사항.md「파일 구조」, 테이블은 「ERD」를 따른다. (장 번호는 바뀔 수 있어 장 이름으로 부른다)

## 무엇을 언제 읽나 (필요할 때만 연다. @로 통째로 불러오지 않는다)
| 하려는 일 | 읽을 파일 |
|---|---|
| 무엇을 만들지·담당·일정 | `docs/planning/결정사항.md` |
| 장면·시연 순서·알림 방식 | `docs/planning/시나리오.md` |
| 도구 목록(8장)·LangGraph(9장)·테스트 7개(15장) | `docs/planning/기획서.md` |
| 제출물·배점·감점 | `docs/requirements.md` |
| `run_agent`·`@tool`·승인·Gradio 코드 구조 | `docs/reference/function-calling.md` |
| RAG 인덱스·임계값·`query_rag` | `docs/reference/rag.md` (응용: `rag-exercises.md`, 개념: `rag-lecture.md`) |
| 도구 설계·안전장치·보안 이론, 발표 설명 | `docs/reference/react-fc-theory.md`, `fc-code-reading.md` |
| 그 밖의 강의 요약(에이전트 기초·임베딩 등) | `docs/reference/` 목록은 `docs/README.md` |
| 폴더별 규칙 | `.claude/rules/*.md` (해당 폴더 작업 시 자동 적용) |

## 역할 분담 (결정사항.md「역할 분담」이 기준)
- **안민영**: RAG, LangGraph — `db/`, `rules/`, `rag/`, `graph/`, `sim/`
- **권현진**: 도구 호출, MCP, 디스코드 — `agent/`, `tools/`, `mcp_server/`, `app.py`, `config.py`, `notify/`
- 공통: DB 스키마 첫날 함께 확정, `tests/test_scenarios.py`, 보고서·발표

## 폴더 구분
- `docs/` = 기획·참고 문서. **RAG에 넣지 않는다.**
- 강의 자료는 **요약 md(`docs/reference/`, 커밋됨)가 기준**이다. PDF 원본(`docs/lectures/`)은 선택적인 로컬 보관용이라 커밋하지 않고, 요약으로 부족할 때만 연다.
- `rag/docs/` = RAG 검색 대상 공공 문서(의약품 허가정보, 질병관리청 자료).

## 실행·테스트 명령 (코드가 아직 없다 — 모두 예정)
```
pip install -r requirements.txt    # (예정)
python rag/build_index.py          # (예정) FAISS 인덱스 생성 → rag/index/
python app.py                      # (예정) Gradio 실행
pytest                             # (예정) LLM 호출 테스트는 @pytest.mark.llm, 기본은 API 없이 실행
```
Mac은 `python3`, Windows는 `python`을 쓴다.

## 절대 원칙
1. **진단·처방·용량 판단은 하지 않는다.** 의료 기능은 정보 안내까지만. 용량 질문은 거절하고 의사·약사 상담을 안내한다.
2. **범위·위험 판정은 `rules/health_rules.py`의 코드 규칙이 한다.** LLM은 판정을 바꿀 수 없다. 위험 수치는 LLM을 거치지 않고 **정해진 응급 문구**를 낸다.
3. **환자 ID는 도구 인자에 넣지 않는다.** `config.PATIENT_ID`를 서버에서만 넣는다.
4. **가상 데이터만 쓴다.** 실명·연락처를 넣지 않는다.
5. **API 키와 웹훅 URL은 `.env`에만 둔다.** 코드·문서·커밋에 넣지 않는다.

## 팀 관례
- 브랜치: `타입/설명-작성자` (예: `feat/rag-search-Min_Yeong`)
- 커밋 메시지: `타입: 한글 제목` + 본문(이전 상황 → 파일별 변경 → 테스트 → 검증 결과)
- 커밋은 **논리적 변경 단위**로 나누고, 각 커밋은 단독으로 빌드·테스트가 돼야 한다.
- 다른 팀원이 담당하는 파일을 고치면 그 팀원에게 공유하라고 알려 준다. 담당은 결정사항.md「역할 분담」·「파일 구조」의 (민영)/(현진) 표시와 각자의 `CLAUDE.local.md`로 확인한다.
- **DB 컬럼을 바꿀 때는 반드시 서로 알린다.** 미리 합의한 함수 모양(`send_discord(channel, kind) -> bool`, `record_dose(...) -> bool`, `get_dose(...)`)은 바꾸지 않는다. 상대 파일이 아직 없으면 print만 하는 가짜 함수로 두고 먼저 진행한다.
- **커밋은 사용자가 요청할 때만 한다.** 훅이 `.env`·`docs/lectures/` 수정과 비밀값(API 키·웹훅 URL) 커밋을 막는다(`.claude/hooks/README.md`).
- 모든 문서와 주석은 한국어. 발표 때 설명할 수 있도록 코드는 단순하게 쓰고 "왜 이렇게 짰는지"를 말할 수 있게 한다.

## 작업 흐름 (서브에이전트)
서브에이전트끼리는 서로 부를 수 없다. **메인 세션이 순서대로 부른다:** `developer`(구현 설명) → `tester`(테스트) → `qa`(검수).
- 전체 흐름은 `/feature-flow <기능 이름>`. 단계마다 사용자 확인을 받고 자동으로 넘어가지 않는다.
- `developer`·`tester`는 사용자가 "작성해줘"/"진행해줘"라고 할 때만 파일을 수정한다. `qa`는 코드를 고치지 않는다.
- 각 에이전트는 `한 일 / 바꾼 파일 / 남은 문제 / 다음 에이전트에 넘길 것` 형식으로 보고한다.
- 보조 스킬: `/scenario-test`(테스트 기록 → `docs/test-log.md`), `/ai-log`(AI 활용 기록 → `docs/ai-usage-log.md`), `/demo-check`(발표 전 점검).

## 미결 사항
`docs/planning/결정사항.md`「미결 사항」을 확인한다. 특히 **로컬 LLM 요건**(안내서는 Ollama 로컬 모델 요구, 우리는 Gemini API)은 교수님 확인이 필요하다.
