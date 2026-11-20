#!/usr/bin/env python3
"""PreToolUse(Bash) 훅: git commit 직전에 비밀값이 스테이징돼 있으면 막는다.

검사 대상
  1) .env / .env.* 파일이 스테이징돼 있는지 (.env.example 등 템플릿은 허용)
  2) 스테이징된 diff의 '추가된 줄'에 Google API 키 패턴 또는 디스코드 웹훅 URL 패턴이 있는지
  (git commit -a/--all/-am 이면 추적 중인 파일의 작업 트리 변경도 함께 검사)
차단하려면 exit 2 + stderr. 그 외는 exit 0.
찾은 값 자체는 출력하지 않는다(파일:줄 번호와 종류만).
"""
import json
import os
import re
import subprocess
import sys

ALLOWED_SUFFIXES = (".example", ".sample", ".template")

# 정규식 문자열이라 이 파일 자체는 패턴에 걸리지 않는다
PATTERNS = [
    ("Google API 키 패턴", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("디스코드 웹훅 URL", re.compile(r"discord(?:app)?\.com/api/webhooks", re.IGNORECASE)),
]

# 'git commit' (git -C dir commit, git -c k=v commit 등 포함). 따옴표 안 문자열은 완벽히 구분하지 않는다.
COMMIT_RE = re.compile(r"(^|[;&|(\s])git\s+(?:-[^\s]+\s+(?:[^\s-][^\s]*\s+)?)*commit(\s|$)")
ALL_FLAG_RE = re.compile(r"\scommit\b[^;&|\n]*?\s(-[a-zA-Z]*a[a-zA-Z]*|--all)(\s|$)")


CD_RE = re.compile(r"(?:^|[;&|(]\s*)cd\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")
GIT_C_RE = re.compile(r"\bgit\s+(?:[^;&|\n]*?\s)?-C\s+(\"[^\"]+\"|'[^']+'|[^\s;&|]+)")


def _unquote(v):
    return v[1:-1] if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0] else v


ASSIGN_RE = re.compile(r"(?:^|[;&|(]\s*)([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]*)")
VAR_RE = re.compile(r"\$(?:\{(\w+)\}|(\w+))")


def _expand(value, local):
    """$VAR / ${VAR} 를 명령 앞부분의 대입(VAR=값;)과 환경변수로 푼다. 못 풀면 그대로 둔다."""
    def rep(m):
        name = m.group(1) or m.group(2)
        return local.get(name, os.environ.get(name, m.group(0)))
    return os.path.expanduser(VAR_RE.sub(rep, value))


def target_dir(command, cwd):
    """명령에 적힌 'cd <dir> &&' 와 'git -C <dir>' 를 따라가 실제로 commit이 일어날 디렉터리를 구한다.
    돌려주는 값: (디렉터리, 못 푼 경로 목록)"""
    m = COMMIT_RE.search(command)
    head = command[: m.end()] if m else command
    local = {n: _unquote(v) for n, v in ASSIGN_RE.findall(head)}
    d, unresolved = cwd, []
    for cd in CD_RE.finditer(head):
        t = _expand(_unquote(cd.group(1)), local)
        if "$" in t or "`" in t:
            unresolved.append(t)
        d = os.path.join(d, t)
    g = GIT_C_RE.search(head)
    if g:
        t = _expand(_unquote(g.group(1)), local)
        if "$" in t or "`" in t:
            unresolved.append(t)
        d = os.path.join(d, t)
    return os.path.normpath(d), unresolved


def run_git(args, cwd):
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=off"] + args,
            cwd=cwd, capture_output=True, encoding="utf-8", errors="replace",
        )
    except (OSError, ValueError):  # 폴더가 없거나 git이 없는 경우
        return ""
    return r.stdout if r.returncode == 0 else ""


def is_git_repo(d):
    return run_git(["rev-parse", "--is-inside-work-tree"], d).strip() == "true"


# 같은 명령 안에서 'git add ... && git commit' 처럼 이어지면, 훅이 도는 시점에는 아직 스테이징 전이다.
ADD_SEG_RE = re.compile(r"\bgit\s+(?:[^;&|\n]*?\s)?add\b([^;&|\n]*)")
MAX_SCAN_BYTES = 1_000_000
MAX_SCAN_FILES = 2000


def add_targets(head):
    """head(commit 앞부분)에서 git add 의 인자들을 돌려준다. 없으면 None."""
    segs = ADD_SEG_RE.findall(head)
    if not segs:
        return None
    args = []
    for seg in segs:
        args += [_unquote(t) for t in seg.split() if not t.startswith("-")]
    return args


BROAD_FLAGS = {"-A", "--all", "-u", "--update"}


def is_broad_add(head, cwd):
    """git add 가 '전부'를 추가하는 형태인지(., -A, *, 디렉터리 등). 파일을 명시했으면 False."""
    for seg in ADD_SEG_RE.findall(head):
        toks = seg.split()
        if any(t in BROAD_FLAGS for t in toks):
            return True
        paths = [_unquote(t) for t in toks if not t.startswith("-")]
        if not paths:
            return True
        for t in paths:
            if t in (".", "..", ":/") or "*" in t or t.endswith(("/", "\\")) or os.path.isdir(os.path.join(cwd, t)):
                return True
    return False


def is_update_only(head):
    """git add -u / --update (새 파일은 추가하지 않고 추적 중인 파일의 수정만 스테이징)인지."""
    for seg in ADD_SEG_RE.findall(head):
        toks = seg.split()
        if any(t in ("-u", "--update") for t in toks) and not any(t in ("-A", "--all") for t in toks):
            return True
    return False


def scan_files(cwd, paths):
    """명시한 파일만 검사: 추적 중이고 수정됐으면 diff의 추가 줄, 아니면 본문 전체."""
    hits = []
    for f in paths:
        full = os.path.join(cwd, f)
        diff = run_git(["diff", "-U0", "--no-color", "--", f], cwd)
        if diff.strip():
            hits += scan_diff(diff)
            continue
        try:
            if os.path.isfile(full) and os.path.getsize(full) <= MAX_SCAN_BYTES:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    for n, line in enumerate(fh, 1):
                        for label, rx in PATTERNS:
                            if rx.search(line):
                                hits.append((f, n, label))
        except OSError:
            pass
    return hits


def scan_untracked(cwd):
    """추적되지 않은(ignore 되지 않은) 파일 본문에서 비밀 패턴을 찾는다."""
    hits = []
    files = run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines()[:MAX_SCAN_FILES]
    for f in files:
        path = os.path.join(cwd, f)
        try:
            if os.path.getsize(path) > MAX_SCAN_BYTES:
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                for n, line in enumerate(fh, 1):
                    for label, rx in PATTERNS:
                        if rx.search(line):
                            hits.append((f, n, label))
        except OSError:
            continue
    return files, hits


def scan_diff(diff_text):
    """diff에서 추가된 줄만 훑어 (파일, 줄번호, 종류) 목록을 돌려준다."""
    hits, cur_file, new_line = [], "?", 0
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            cur_file = line[4:].strip()
            cur_file = cur_file[2:] if cur_file.startswith("b/") else cur_file
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            new_line = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            for label, rx in PATTERNS:
                if rx.search(line):
                    hits.append((cur_file, new_line, label))
            new_line += 1
        elif not line.startswith("-"):
            new_line += 1
    return hits


def is_env_file(path):
    name = path.replace("\\", "/").lower().rsplit("/", 1)[-1]
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(ALLOWED_SUFFIXES)


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except Exception:
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if not COMMIT_RE.search(command):
        return 0

    base_cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cwd, unresolved = target_dir(command, base_cwd)
    if not unresolved and not is_git_repo(cwd):   # 존재하지 않는 경로면 세션의 작업 폴더로 되돌린다
        cwd = base_cwd
    include_worktree = bool(ALL_FLAG_RE.search(command))
    m = COMMIT_RE.search(command)
    head = command[: m.end()] if m else command
    add_args = add_targets(head)

    problems = []

    for u in unresolved:
        problems.append(f"{u}: cd/git -C 경로에 풀 수 없는 셸 변수가 있어 어느 저장소를 커밋하는지 검사할 수 없습니다 (경로를 직접 쓰거나 git add와 git commit을 따로 실행하세요)")

    if add_args is not None:
        # git add 가 같은 명령에서 먼저 실행된다 → 아직 스테이징 전이므로 add 대상을 직접 검사한다
        for a in add_args:
            if is_env_file(a):
                problems.append(f"{a}: git add 대상에 .env 파일이 포함돼 있습니다")
        if is_update_only(head):
            include_worktree = True      # -u: 추적 중인 파일의 수정만 (새 파일은 추가되지 않음)
        elif is_broad_add(head, cwd):
            include_worktree = True      # . / -A / 디렉터리: 작업 트리 전체(수정 + 새 파일)
            files, hits = scan_untracked(cwd)
            for f in files:
                if is_env_file(f):
                    problems.append(f"{f}: 추적되지 않은 .env 파일이 있습니다(.gitignore에 없음)")
            for f, ln, label in hits:
                problems.append(f"{f}:{ln}: {label} 발견 (git add 로 함께 커밋될 수 있는 새 파일)")
        else:
            for f, ln, label in scan_files(cwd, add_args):
                problems.append(f"{f}:{ln}: {label} 발견 (git add 대상)")

    staged = run_git(["diff", "--cached", "--name-only"], cwd).splitlines()
    if include_worktree:
        staged += run_git(["diff", "--name-only"], cwd).splitlines()
    for f in staged:
        if is_env_file(f):
            problems.append(f"{f}: .env 파일이 커밋 대상에 포함돼 있습니다")

    diff = run_git(["diff", "--cached", "-U0", "--no-color"], cwd)
    if include_worktree:
        diff += "\n" + run_git(["diff", "-U0", "--no-color"], cwd)
    for f, ln, label in scan_diff(diff):
        problems.append(f"{f}:{ln}: {label} 발견")

    if not problems:
        return 0
    print("[guard_commit] 커밋 차단: 비밀값이 포함됐을 수 있습니다.", file=sys.stderr)
    for p in dict.fromkeys(problems):
        print("  - " + p, file=sys.stderr)
    print("  → 해당 파일/줄을 빼고(git restore --staged <파일>) 키·웹훅 URL은 .env에만 두세요. 이미 노출된 키는 폐기하고 새로 발급하세요.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
