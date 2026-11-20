---
paths:
  - "notify/**"
---

# 알림 규칙

- 메시지에는 **최소 정보만** 넣는다 (예: "아침 약 드실 시간이에요", "저녁 약 확인이 안 됐어요"). **수치·약 이름·질환명은 넣지 않는다.** 문구는 `notify/messages.py`에 모은다.
- **파일 이름을 `discord.py`로 만들지 않는다**(같은 이름의 라이브러리를 가린다). `discord_notify.py`를 쓴다.
- 공개 함수는 합의된 모양 `send_discord(channel: str, kind: str) -> bool`(channel: `patient`|`guardian`, kind: `reminder`|`retry`|`guardian`|`emergency`). 성공이면 True, **실패하면 예외 대신 False**를 돌려준다. 그래프(민영)가 이 함수만 호출한다.
- 디스코드는 웹훅 + `requests.post`. 웹훅 URL은 `.env`(`DISCORD_WEBHOOK_PATIENT`, `DISCORD_WEBHOOK_GUARDIAN`)에서만 읽는다. 코드·테스트·문서에 URL을 쓰지 않는다.
- **발송 실패해도 예외로 죽지 않는다.** 실패는 `notification_log`(채널, 종류, 성공 여부, 오류)에 기록하고, **Gradio 알림은 그대로 표시**한다. 타임아웃을 짧게 둔다.
- 보호자 알림은 **무응답 2회일 때와 위험 수치일 때만**, 가상 보호자 채널로만 보낸다.
- 알림은 LLM 도구로 노출하지 않는다. 그래프 노드가 확정적으로 보낸다.
