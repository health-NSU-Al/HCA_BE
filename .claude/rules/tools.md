---
paths:
  - "tools/**"
  - "agent/tool_registry.py"
---

# 도구(@tool) 작성 규칙

참고: `docs/reference/function-calling.md` 14단계, 17단계. 위험도 등급은 `docs/planning/기획서.md` 8장 표.

- 데코레이터는 `@tool(parse_docstring=True)`. docstring은 Google 스타일 `Args:`로 인자마다 설명과 예시 값을 적는다. 선택 인자는 `Optional[...] = None`이고 생략 시 동작을 적는다.
- 이름은 **"동사 + 대상"** (`get_today_medications`, `check_medication`, `save_doctor_question`).
- 반환은 **모델이 그대로 말할 수 있는 문장**. ID보다 이름을 돌려준다. 빈 결과도 문장으로 돌려준다.
- **오류도 예외로 던지지 않고 "다음에 할 일" 문장으로 반환**한다 (예: "형식(예: 2026-11-20)을 확인해 주세요").
- **환자 ID는 인자로 받지 않는다.** `config.PATIENT_ID`를 도구 안에서 서버가 넣는다. 인자 없는 도구는 `list(tool.args) == []`로 확인.
- 날짜·시간은 코드가 넣는다(가상 시계 기준). docstring에 형식(YYYY-MM-DD)을 명시한다.
- 쓰기 도구는 실행 전에 대상이 있는지 확인하고, 위험도 등급(기획서 8장)을 지킨다:
  - 읽기 → 자유
  - 되돌릴 수 있는 쓰기(`check_medication`, `make_report`, `save_doctor_question`) → 실행 + 기록
  - 외부 반영·되돌리기 어려운 쓰기(`add_calendar_event`) → `NEED_APPROVAL`에 등록해 승인 버튼
  - 외부 전송(보호자 알림) → **LLM 도구로 노출하지 않는다**(그래프 노드가 보냄)
- `check_medication`은 `db.database.record_dose(...)`(이미 있으면 False)와 `get_dose(...)`(민영 담당)를 쓴다. **같은 날짜·같은 시간대의 중복 기록을 막는다.** `record_dose`가 False면 아래 문장을 반환한다. 이미 기록돼 있으면 새로 쓰지 않고 "오늘 HH:MM에 이미 드신 걸로 기록돼 있어요. 또 드시면 안 돼요." 같은 문장을 반환한다. DB에도 `UNIQUE(patient_id, dose_date, slot)`가 있어야 한다.
- 새 도구는 `agent/tool_registry.py`에 등록한다. 에이전트에 붙이기 전에 `.invoke({...})`로 정상 / 빈 결과 / 잘못된 값 / 인자 없음 4경우를 직접 돌려 본다.
- 의료 판단(범위·위험)은 도구가 하지 않고 `rules/health_rules.py`의 `judge()`를 호출한다.
