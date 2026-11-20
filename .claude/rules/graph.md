---
paths:
  - "graph/**"
---

# LangGraph 규칙

설계는 `docs/planning/기획서.md` 9장. LangGraph 강의 요약이 `docs/reference/langgraph.md`에 있으면 함께 본다.

- **디스코드 전송 노드와 interrupt 노드를 반드시 분리한다.** 재개(resume)할 때 노드가 처음부터 다시 실행되므로, 같은 노드에 두면 알림이 중복 발송된다. (`send_reminder` ≠ `wait_check`)
- **노드 안에서 반복문으로 interrupt를 돌리지 않는다.** 조건 엣지로 이전 노드에 돌아가고, state에 횟수를 넣어 제한한다.
- 체크포인터는 `InMemorySaver`. 재개는 `Command(resume=...)`.
- `thread_id`는 **복약 1회마다 따로** 준다: `YYYY-MM-DD-slot` (예: `2026-11-20-morning`). 측정 판정 플로우는 `YYYY-MM-DD-measure-N` 형식으로 구분한다.
- **재측정은 1회까지.** state의 재측정 횟수로 제한하고, 두 번째에도 오류 의심이면 저장하고 진료 때 확인하도록 안내한다.
- 복약 무응답: 1회 → 재알림, 2회 → 보호자 알림 + `missed` 기록. 늦게 체크하면 `late`로 기록.
- 판정은 `rules/health_rules.py`의 `judge()` 결과를 그대로 따른다(정상 / 범위 밖 / 측정 오류 의심 / 위험). 위험은 `emergency` 노드가 **정해진 문구 상수**로 처리하고 LLM을 거치지 않는다.
- 알림은 합의된 `notify.discord_notify.send_discord(channel, kind) -> bool`만 호출한다(권현진 담당). 아직 없으면 print만 하는 가짜 함수로 두고 플로우를 먼저 만든다.
- 복약 기록은 `db.database.record_dose(dose_date, slot, status) -> bool`(이미 있으면 False)과 `get_dose(dose_date, slot)`를 쓴다.
- 알림 발송·판정은 그래프(코드)가 결정한다. LLM은 "범위 밖 설명" 같은 쉬운 말 설명 노드에서만 쓴다.
- 시간은 `sim/virtual_clock.py`의 가상 시계를 쓴다(실제 시계·스케줄러 금지).
- state 정의는 `graph/state.py` 한 곳에 둔다.
