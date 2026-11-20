#!/usr/bin/env python3
"""PreToolUse(Edit|Write) 훅: .env 와 docs/lectures/ 수정을 막는다.

- stdin: Claude Code가 주는 JSON (tool_input.file_path 사용)
- 차단하려면 exit 2 + stderr 메시지 (Claude에게 전달됨). 그 외는 exit 0.
- Mac/Windows 공통으로 돌도록 셸 대신 파이썬으로 작성했다.
"""
import json
import os
import sys

# .env.example 같은 템플릿은 허용
ALLOWED_SUFFIXES = (".example", ".sample", ".template")


def main():
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0  # 입력을 못 읽으면 막지 않는다
    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path:
        return 0

    norm = path.replace("\\", "/")          # Windows 경로 통일
    lower = norm.lower()
    name = lower.rsplit("/", 1)[-1]

    # 1) .env, .env.local, .env.production ... (단 .env.example 등은 허용)
    if (name == ".env" or name.startswith(".env.")) and not name.endswith(ALLOWED_SUFFIXES):
        return block(f".env 파일은 수정할 수 없습니다 ({path}). 키와 웹훅 URL은 사용자가 직접 .env에 넣습니다. 형식은 .env.example을 참고하세요.")

    # 2) docs/lectures/ (강의 PDF, 커밋하지 않는 폴더)
    if "/docs/lectures/" in ("/" + lower) or lower.endswith("/docs/lectures"):
        return block(f"docs/lectures/는 수정할 수 없습니다 ({path}). 강의 자료 원본 폴더입니다. 요약은 docs/reference/에 쓰세요.")
    return 0


def block(msg):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("[guard_edit] 차단: " + msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
