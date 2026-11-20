# 참고: 도구 호출(Function Calling) — 수업 3장 코드 구조

- 출처: `docs/lectures/ch03_function_calling_code_points.pdf` (3장 2부, 14 · 15-1 · 15-2 · 16-1 · 17-2 · 17-3단계)
- 주의: PDF의 코드는 슬라이드 이미지라 텍스트로 옮길 수 없다. 아래 코드는 **슬라이드 설명(덩어리 구조·포인트)을 바탕으로 우리 프로젝트 기준으로 줄여 다시 쓴 예시**이다. 정확한 원본은 PDF의 해당 슬라이드를 본다.
- 우리와 달라지는 점: 수업은 transformers + `chat()`, 우리는 `ChatGoogleGenerativeAI(...).bind_tools(tools)` + `async` (결정사항.md 3장). **루프 구조·로그·승인·기억은 그대로.**

---

## 14단계 — 도구 작성법 (슬라이드 37~56)

**구조 4줄:** ① `@tool(parse_docstring=True)` ② 시그니처 + docstring(`Args:`) ③ 본문 ④ 반환 문장. 모델이 보는 건 ②뿐이다.

```python
@tool(parse_docstring=True)
def get_today_medications() -> str:
    """오늘 먹을 약과 복용 여부를 조회한다."""
    ...
    return "아침 약 3종은 08:02에 드셨어요. 저녁 약 2종은 아직이에요."
```

핵심
- `parse_docstring=True`가 없으면 `Args:` 설명이 설명서에 안 들어간다 → **스키마를 출력해서** description을 눈으로 확인.
- 선택 인자는 `Optional[str] = None`. 설명서의 `required`에는 필수 인자만 들어간다.
- 오류도 예외가 아니라 **"다음에 할 일" 문장**으로 반환 (예: "찾을 수 없습니다. 형식(예: 2026-11-20)을 확인해 주세요").
- 반환은 ID보다 이름, 모델이 그대로 말할 수 있는 문장. 빈 결과도 문장으로(빈 리스트를 보면 모델이 지어낸다).
- `@tool`이 없는 함수는 모델에게 안 보이는 내부 도우미.
- 날짜는 코드가 넣는다. docstring에 형식(YYYY-MM-DD)을 적는다.
- 묶음 3종: `tools`(리스트) · `tool_map`(이름→도구) · `schemas`. 도구 추가·삭제는 이 묶음만 고친다 → 우리는 `agent/tool_registry.py`.
- **에이전트에 붙이기 전, 사람이 먼저** `.invoke({...})`로 4경우(정상 2 · 없는 값 · 인자 없는 도구)를 손으로 돌린다. 여기서 예외가 나면 `run_agent` 안에서도 난다.

우리 프로젝트에 적용: `tools/medication_tools.py` 등 모든 도구가 이 모양. (`.claude/rules/tools.md`)

---

## 15-1단계 — run_agent, NEED_APPROVAL, max_iters (슬라이드 57~66)

**덩어리:** ① 시스템 프롬프트 ② `NEED_APPROVAL`(승인 필요 도구 집합) ③ 머리·준비 ④ 모델 호출·최종 답 판단 ⑤ 요청마다 실행·tool 메시지 ⑥ 한도 초과 ⑦ 한 번 실행.

```python
NEED_APPROVAL = {"add_calendar_event"}          # 쓰기·외부 반영 도구

async def run_agent(question, history, tool_list, approve_fn, max_iters=5):
    tmap = {t.name: t for t in tool_list}
    llm_with_tools = make_llm().bind_tools(tool_list)
    messages = [SystemMessage(SYSTEM_PROMPT)] + history + [HumanMessage(question)]
    log = []
    for _ in range(max_iters):                   # 무한 루프·요금 폭발 방지
        ai = await llm_with_tools.ainvoke(messages)
        calls = ai.tool_calls
        if not calls:                            # 요청이 없으면 그 글이 최종 답
            messages.append(ai)
            return ai.content, messages, log
        messages.append(ai)                      # 요청을 실행보다 먼저 기록
        for c in calls:
            if c["name"] not in tmap:
                result = f"[에러] 없는 도구입니다. 사용 가능: {list(tmap)}"
            elif c["name"] in NEED_APPROVAL and not approve_fn(c):
                result = "[거절] 사용자가 승인하지 않았습니다."
            else:
                try:
                    result = await tmap[c["name"]].ainvoke(c["args"])
                except Exception as e:
                    result = f"[도구 실행 오류] {e}. 인자 형식을 확인하세요."
            log.append({"tool": c["name"], "args": c["args"], "result": str(result)})
            messages.append(ToolMessage(str(result), tool_call_id=c["id"]))
    return "[중단] 반복 한도를 넘었어요.", messages, log
```

핵심
- 메시지 = `[system] + 이전 대화 + [user]`. **모델에게 기억은 없다. 리스트를 통째로 넘겨서 기억처럼 보일 뿐.**
- 종료 조건 = 요청이 없음(`if not calls`).
- 네 갈래(없는 도구 / 승인 거절 / 실행 오류 / 정상)가 **전부 문장**으로 tool 메시지가 된다 → 모델이 다음 바퀴에 고친다.
- `max_iters`는 반드시 둔다. `log`는 `{tool, args, result}`로 쌓아 오른쪽 로그창의 재료로 쓴다.
- 요청 `[Parameters]`가 질문과 맞는지 보는 게 디버깅의 절반.
- 시스템 프롬프트 규칙 7개: ① 조회는 도구로 ② 맥락으로 인자 채우기 ③ 한국어 ④ ID 형식 ⑤ 기본 사용자 ⑥ 오늘 날짜(코드가 f-string으로) ⑦ 결과에 없는 말 금지. 규칙은 부탁이지 차단이 아니다(17단계).
- `tool_list`를 인자로 받아 도구 세트를 바꿔 끼운다.

---

## 15-2단계 — 대화 기억 (슬라이드 67~70)

```python
class Conversation:
    def __init__(self, keep=12):
        self.history, self.keep = [], keep        # system을 뺀 메시지 리스트
    async def process(self, question, tool_list, approve_fn):
        answer, messages, log = await run_agent(question, self.history, tool_list, approve_fn)
        self.history = messages[1:][-self.keep:]   # system 제외, 최근 12개만
        return answer, log
    def clear(self):
        self.history = []
```

- `keep`이 너무 크면 느려지고, 너무 작으면 "그 약"을 잊는다. 12 ≈ 6턴.
- 확인: `clear()` 뒤 `history == []`.
- 우리 파일: `agent/memory.py`.

---

## 16-1단계 — Gradio 화면 (슬라이드 73~77)

- 구조: 왼쪽 `Chatbot`(messages 형식) + 입력창, 오른쪽 **도구 호출 로그** `Textbox`, 전송·초기화 버튼.
- **껍데기(화면)와 두뇌(에이전트)를 나눠 두면** 에이전트만 갈아 끼울 수 있다.
- `chat_history`에는 `{"role", "content"}` 사전을 append (messages 형식만 허용).
- 변수 이름이 겹치지 않게 하고, 끝나면 `demo.close()`(공개 주소 방지).
- 우리는 여기에 승인 버튼, 토스트, 가상 시계, 리포트 다운로드가 더해진다. 우리 파일: `app.py`.

---

## 17-2단계 — 권한은 코드로 (슬라이드 80~85)

**구멍(17-1):** 시스템 프롬프트에 "기본 사용자는 C001"이 있어도 "C002 프로필"을 물으면 나온다. **규칙은 부탁이지 차단이 아니다.** "프롬프트를 더 강하게"라는 답은 받지 말 것.

```python
LOGIN_ID = "C001"                       # 서버만 아는 값. 모델은 보거나 바꿀 수 없다

@tool
def get_my_profile() -> str:            # 인자 없음 = 남의 ID를 넣을 칸 자체가 없다
    """내 프로필을 조회한다."""
    return get_customer_profile.invoke({"customer_id": LOGIN_ID})   # 원래 도구는 모델에 노출하지 않는다

safe_tools = [get_my_profile, ...]
assert list(get_my_profile.args) == []  # 설명서에 인자가 없다는 증거
```

- `run_agent`의 `tool_list=`로 **루프는 그대로, 도구 세트만 교체**.
- 우리: `config.PATIENT_ID`를 서버에서만 넣는다. 도구 인자에 환자 ID를 두지 않는다.

---

## 17-3단계 — 되돌릴 수 없으면 사람에게 (슬라이드 86~91)

- 쓰기 도구 docstring에 **"되돌릴 수 없다"를 명시**하면 모델도 신중해진다.
- 쓰기 도구는 실행 전에 대상이 존재하는지 확인하고 없으면 문장 반환. DB면 트랜잭션 안에서.
- `NEED_APPROVAL = {...}` + `approve_fn` 콜백 → 실행 직전에 사람에게 묻는다(Human-in-the-loop).
  - 수업은 `input()`으로 y/n, **실서비스에선 승인 버튼** (우리: Gradio [등록] [취소]).
- 확인: 승인 시 실행, 거절 시 `[거절]`이 tool 메시지로 가고 아무것도 바뀌지 않음. **둘 다 눈으로 확인.**
- 테스트는 항상 같은 상태에서 시작하도록 상태를 되돌리는 줄을 둔다.

우리 적용: `add_calendar_event`는 `NEED_APPROVAL`. 쓰기 도구의 위험도 등급은 기획서 8장 표.

---

## 바이브 코딩 체크리스트 (슬라이드 92)

프롬프트에 넣을 것: 기존 도구 코드 하나를 붙이고 "같은 꼴로" / 도구마다 docstring(하는 일·인자 뜻·예시·생략 시 동작) / 오류는 문장 / 날짜는 코드가 넣기 / 루프에 `max_iters`·승인 훅·`tool_list` 교체 자리.

받은 코드에서 확인할 것: 스키마의 `description`·`required` / `.invoke()`로 4경우 / 요청서를 바로 실행하는 코드가 없는가 / assistant 기록이 실행보다 먼저인가 / 로그의 `[Parameters]` / 남의 ID로 직접 공격해 보기 / **설명 못 하는 줄은 "왜 필요해?" 되묻고, 못 들으면 제출하지 않는다.**
