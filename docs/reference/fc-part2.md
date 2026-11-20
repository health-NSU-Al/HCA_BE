# 참고: 펑션 콜링 2부 — 손으로 한 바퀴 (코랩 11~17단계 슬라이드)

- 출처: `docs/lectures/ch03_2부_function_calling.pdf` (3장 2부 슬라이드, 코드 11~17단계 설명). 내용 대부분이 `react-fc-theory.md`(2부)·`function-calling.md`(14~17단계)와 겹쳐서 **겹치지 않는 부분만** 정리했다.

## 왜 펑션 콜링인가 (슬라이드 3~4)
- 모델은 우리 회사(프로젝트) 데이터를 모른다 → 모델이 "이 함수를 이 값으로 불러 줘"라고 **부탁**하고, 우리가 실행해서 결과를 돌려주면 모델이 말로 답한다.
- 비유: 온라인 쇼핑의 "주문하기" — 손님(모델)은 주문서만 쓰고, 꺼내 포장하는 건 직원(우리 코드).
- **왜 나눠 놨나**: 모델이 직접 DB를 만지면 통제가 안 된다. 요청서만 쓰게 하면 **실행 전에 검사·거절·사람에게 묻기**가 가능하다(보안의 전제).

## 11단계 — 손으로 한 바퀴 코드 (슬라이드 7~9)
```python
@tool
def get_temperature(city: str) -> str:
    """도시의 현재 기온을 알려줍니다. city는 도시 이름 (예: 서울, 부산, 제주)."""
    ...
schema = convert_to_openai_tool(get_temperature)      # 함수 → 모델이 보는 JSON 설명서
out = chat(messages, tools=[schema])                  # ① 설명서 전달
calls = parse_tool_calls(out)                         # ② 요청 받기 (이 순간 함수는 아직 실행 안 됨)
result = get_temperature.invoke(c["arguments"])       # ③ 실행은 우리 코드가
messages.append({"role": "assistant", "content": out})                  # 모델의 요청을 기록
messages.append({"role": "tool", "name": c["name"], "content": result})  # ④ 결과를 tool 메시지로
final = chat(messages, tools=[schema])                # 결과를 본 모델이 최종 답
```
- `convert_to_openai_tool`이 이름·docstring·인자 타입을 읽어 설명서(`name`/`description`/`parameters`)를 만든다. `tools=`로 넘기면 제작사가 정한 자리에 자동으로 끼워진다.
- **호출하지 않기도 능력**: "안녕, 넌 누구야?"에는 `tool_calls: []`로 바로 말로 답한다(11-3).
- `tool` 메시지에는 `name`을 넣는다(수업 로컬 모델 기준). **우리(LangChain)는 `ToolMessage(content, tool_call_id=...)`** — 형식만 다르고 구조는 같다.
- 막히면 이 "손으로 한 바퀴"로 내려와 모델이 무엇을 돌려주는지 본다.

## 우리 프로젝트에 적용할 점
- 우리 `run_agent`(async)는 이 4단계의 반복이다. 발표 때 "모델은 요청서만 쓰고 우리 코드가 실행하기 때문에, 실행 전에 **승인·거절·환자 ID 주입**이 가능하다"고 설명한다.
- `get_today_medications`처럼 인자가 없는 도구는 모델이 `arguments: {}`로 호출한다. 환자 ID를 넣을 칸 자체가 없다.
