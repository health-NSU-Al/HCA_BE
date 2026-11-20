"""훅 동작 테스트: python3 .claude/hooks/test_hooks.py   (Windows는 python)

임시 폴더에 git 저장소를 만들어 guard_edit.py / guard_commit.py 가 기대대로 막는지(exit 2) 또는 통과시키는지(exit 0)를 확인한다.
프로젝트 저장소는 건드리지 않는다. 가짜 키·웹훅 문자열은 실행 중에 조립한다(이 파일에는 실제 패턴이 없다).
실패가 하나라도 있으면 종료 코드 1.
"""
import json, os, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SC = tempfile.mkdtemp(prefix="hooktest_")
HOOKS = os.path.join(ROOT, ".claude", "hooks")
def run(hook, payload, cwd=None):
    r = subprocess.run([sys.executable, "-I", os.path.join(HOOKS, hook)], input=json.dumps(payload).encode("utf-8"),
                       capture_output=True, cwd=cwd)
    return r.returncode, r.stderr.decode("utf-8", "replace")
rows = []
def check(name, got, want):
    rows.append((name, want, got, "PASS" if got == want else "FAIL"))

# ---- guard_edit
for path, want in [(".env",2),("/Users/x/proj/.env.local",2),("C:\\proj\\.env",2),("C:\\proj\\.env.production",2),
                   ("docs/lectures/a.pdf",2),("/Users/x/HCA_BE/docs/lectures/b.pdf",2),("C:\\x\\docs\\lectures\\c.pdf",2),
                   (".env.example",0),("docs/README.md",0),("docs/lectures_notes.md",0),("CLAUDE.md",0),("src/env.py",0)]:
    rc,_ = run("guard_edit.py", {"tool_name":"Write","tool_input":{"file_path":path}})
    check(f"edit  {path}", rc, want)
rc,_ = run("guard_edit.py", {}); check("edit  빈 입력", rc, 0)

# ---- guard_commit
base = os.path.join(SC, "hooktest"); shutil.rmtree(base, ignore_errors=True); os.makedirs(base)
repo = os.path.join(base, "repo"); sp = os.path.join(base, "sp ace repo"); other = os.path.join(base, "other")
for d in (repo, sp, other): os.makedirs(d); subprocess.run(["git","init","-q"],cwd=d)
def git(d,*a): subprocess.run(["git","-c","user.email=t@t","-c","user.name=t",*a],cwd=d,check=True,capture_output=True)
def stage(d, name, text): open(os.path.join(d,name),"w",encoding="utf-8").write(text); git(d,"add","-f",name)
def unstage_all(d): subprocess.run(["git","reset","-q"],cwd=d,capture_output=True)
KEY = "AIza" + "x"*35
WEB = "https://discord" + ".com/api/web" + "hooks/1/x"
def commit(cmd, cwd): return run("guard_commit.py", {"tool_input":{"command":cmd},"cwd":cwd})[0]

stage(repo,"ok.txt","hello"); check("commit 깨끗한 파일", commit("git commit -m t", repo), 0); unstage_all(repo)
stage(repo,"k.txt","k="+KEY); check("commit API 키", commit("git commit -m t", repo), 2); unstage_all(repo)
stage(repo,"w.txt","u="+WEB); check("commit 웹훅 URL", commit("git commit -m t", repo), 2); unstage_all(repo)
stage(repo,".env","X=1"); check("commit .env", commit("git commit -m t", repo), 2); unstage_all(repo)
stage(repo,".env.local","X=1"); check("commit .env.local", commit("git commit -m t", repo), 2); unstage_all(repo)
stage(repo,".env.example","X="); check("commit .env.example만", commit("git commit -m t", repo), 0); unstage_all(repo)
stage(repo,"ok.txt","hello2"); check("비커밋 명령(git status)", commit("git status", repo), 0)
check("echo 'git' 문자열만", commit("echo hello", repo), 0)
# 키가 있어도 스테이징 안 됐으면 통과
open(os.path.join(repo,"untracked.txt"),"w").write(KEY); check("키 있는 untracked(미스테이징)", commit("git commit -m t", repo), 0)
unstage_all(repo)

# 대상 레포 따라가기: cwd는 other(깨끗), 실제 커밋 대상은 repo(오염)
stage(repo,"k.txt","k="+KEY)
check("git -C <repo> commit (cwd=다른곳)", commit(f"git -C {repo} commit -m t", other), 2)
check("cd <repo> && git commit", commit(f"cd {repo} && git commit -m t", other), 2)
check("cd \"<공백 경로>\" && git commit", (stage(sp,"k.txt","k="+KEY), commit(f'cd "{sp}" && git commit -m t', other))[1], 2)
unstage_all(sp)
check("git -C \"<공백 경로>\" commit (깨끗)", commit(f'git -C "{sp}" commit -m t', other), 0)
check("git -c user.name=x commit", commit("git -c user.name=x commit -m t", repo), 2)
check("git commit --amend", commit("git commit --amend --no-edit", repo), 2)
unstage_all(repo)

# -a / -am : 추적 중인 파일의 작업 트리 변경
git(repo,"add","-f","a.txt") if os.path.exists(os.path.join(repo,"a.txt")) else None
open(os.path.join(repo,"a.txt"),"w").write("clean"); git(repo,"add","a.txt"); git(repo,"commit","-q","-m","init")
open(os.path.join(repo,"a.txt"),"a").write("\nk="+KEY)
check("commit -am (추적 파일에 키)", commit("git commit -am t", repo), 2)
check("commit -m (키가 스테이징 안 됨)", commit("git commit -m t", repo), 0)
check("commit --all", commit("git commit --all -m t", repo), 2)


# ---- 같은 명령 안의 git add && git commit (실제 세션 테스트에서 발견된 우회)
for junk in ("k.txt","w.txt",".env",".env.local",".env.example"):
    jp = os.path.join(repo, junk)
    os.remove(jp) if os.path.exists(jp) else None
unstage_all(repo); subprocess.run(["git","checkout","--","a.txt"],cwd=repo,capture_output=True)
os.remove(os.path.join(repo,"untracked.txt")) if os.path.exists(os.path.join(repo,"untracked.txt")) else None
open(os.path.join(repo,"newkey.txt"),"w").write("k="+KEY)
check("add . && commit (새 파일에 키)", commit("git add . && git commit -m t", repo), 2)
check("add -A && commit (새 파일에 키)", commit("git add -A && git commit -m t", repo), 2)
check("add newkey.txt && commit", commit("git add newkey.txt && git commit -m t", repo), 2)
check("cd <repo> && add . && commit", commit(f"cd {repo} && git add . && git commit -m t", other), 2)
os.environ["HOOKREPO"] = repo
check("git -C (환경변수 경로) add && commit", commit("git -C " + chr(36) + "HOOKREPO add . && git -C " + chr(36) + "HOOKREPO commit -m t", other), 2)
check("셸변수 경로(풀 수 없음) → cwd 대체", commit('T=/nonexistent; git -C  add . && git -C  commit -m t', repo), 2)
os.remove(os.path.join(repo,"newkey.txt"))
check("add . && commit (깨끗)", commit("git add . && git commit -m t", repo), 0)
open(os.path.join(repo,".env"),"w").write("X=1")
check("add . && commit (.env는 untracked지만 gitignore 없음)", commit("git add . && git commit -m t", repo), 2)
open(os.path.join(repo,".gitignore"),"w").write(".env" + chr(10))
check("add . && commit (.env가 gitignore됨)", commit("git add . && git commit -m t", repo), 0)
check("add -f .env && commit (강제 추가)", commit("git add -f .env && git commit -m t", repo), 2)
check("add .env.example && commit", commit("git add .env.example && git commit -m t", repo), 0)
check("commit -m 메시지에 .env 언급(문제없음)", commit('git commit -m "docs: .env.example 설명 추가"', repo), 0)


# ---- 같은 명령 안에서 정의한 셸 변수가 대상 레포를 가리킴
dirty = os.path.join(base, "dirty"); clean2 = os.path.join(base, "clean2")
for d in (dirty, clean2):
    os.makedirs(d); subprocess.run(["git", "init", "-q"], cwd=d)
open(os.path.join(dirty, "leak.txt"), "w").write("k=" + KEY)
open(os.path.join(clean2, "ok.txt"), "w").write("ok")
D = chr(36)
check("T=dirty; git -C $T add . && git -C $T commit (cwd=깨끗)",
      commit("T=" + dirty + "; git -C " + D + "T add . && git -C " + D + "T commit -m t", clean2), 2)
check("T=\"dirty\"; cd $T && git add . && git commit",
      commit("T=\"" + dirty + "\"; cd " + D + "T && git add . && git commit -m t", clean2), 2)
check("T=dirty; git -C ${T} add . && git -C ${T} commit",
      commit("T=" + dirty + "; git -C " + D + "{T} add . && git -C " + D + "{T} commit -m t", clean2), 2)
check("T=clean2; git -C $T ... commit (cwd=오염 레포여도 대상은 깨끗)",
      commit("T=" + clean2 + "; git -C " + D + "T add . && git -C " + D + "T commit -m t", dirty), 0)
check("정의 안 된 변수 git -C $NOPE commit -> 검사 불가라 차단",
      commit("git -C " + D + "NOPE_UNDEFINED commit -m t", clean2), 2)
check("cd $NOPE && git commit -> 차단",
      commit("cd " + D + "NOPE_UNDEFINED && git commit -m t", clean2), 2)
os.environ["CLEAN2"] = clean2
check("환경변수로 푸는 경로(깨끗) git -C $CLEAN2 commit",
      commit("git -C " + D + "CLEAN2 commit -m t", dirty), 0)
check("메시지 안의 $(cat <<EOF) 는 무시",
      commit("git commit -m " + chr(34) + D + "(cat <<'EOF'" + chr(10) + "msg" + chr(10) + "EOF" + chr(10) + ")" + chr(34), clean2), 0)


# ---- git add 정밀도: 파일을 명시하면 그 파일만, 넓은 add(. -A * 디렉터리)는 전체 검사
mix = os.path.join(base, "mix"); os.makedirs(mix); subprocess.run(["git", "init", "-q"], cwd=mix)
open(os.path.join(mix, "leak.txt"), "w").write("k=" + KEY)
open(os.path.join(mix, "fine.txt"), "w").write("fine")
os.makedirs(os.path.join(mix, "sub")); open(os.path.join(mix, "sub", "deep.txt"), "w").write("w=" + WEB)
check("add fine.txt && commit (옆에 오염 파일이 있어도 통과)", commit("git add fine.txt && git commit -m t", mix), 0)
check("add leak.txt && commit", commit("git add leak.txt && git commit -m t", mix), 2)
check("add fine.txt leak.txt && commit", commit("git add fine.txt leak.txt && git commit -m t", mix), 2)
check("add . && commit", commit("git add . && git commit -m t", mix), 2)
check("add sub/ && commit (디렉터리)", commit("git add sub/ && git commit -m t", mix), 2)
check("add sub && commit (디렉터리 이름만)", commit("git add sub && git commit -m t", mix), 2)
check("add *.txt && commit (글롭)", commit("git add *.txt && git commit -m t", mix), 2)
check("add -u && commit", commit("git add -u && git commit -m t", mix), 0)
check("add -A fine.txt && commit (넓은 add)", commit("git add -A fine.txt && git commit -m t", mix), 2)
check("add nonexistent.txt && commit", commit("git add nonexistent.txt && git commit -m t", mix), 0)

w = max(len(r[0]) for r in rows)
for n,want,got,st in rows: print(f"{st}  {n.ljust(w)}  기대={want} 실제={got}")
fails = [r for r in rows if r[3]=="FAIL"]
print(f"\n합계 {len(rows)}개 중 통과 {len(rows)-len(fails)}, 실패 {len(fails)}")
shutil.rmtree(SC, ignore_errors=True)
sys.exit(1 if fails else 0)
