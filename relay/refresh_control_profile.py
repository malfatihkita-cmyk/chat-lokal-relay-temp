#!/usr/bin/env python3
import os, time, json, shutil, subprocess
from pathlib import Path

ROOT=Path("/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool")
APP=ROOT/"Chat-Lokal"
DEST=ROOT/"chat-local-control-profile"
SRCROOT=Path.home()/"Library/Application Support/Google/Chrome"
# Use the profile Chrome reports as last-used; do not assume Profile 33.
try:
    _ls=json.loads((SRCROOT/"Local State").read_text(errors="ignore"))
    PROFILE_NAME=((_ls.get("profile") or {}).get("last_used") or "Default")
except Exception:
    PROFILE_NAME="Default"
SRC=SRCROOT/PROFILE_NAME
LA=Path.home()/"Library/LaunchAgents"
LABEL="com.copytolive.chat-lokal-control-browser"
PLIST=LA/(LABEL+".plist")
uid=str(os.getuid())

def run(a,timeout=300,check=False):
    return subprocess.run(a,capture_output=True,text=True,timeout=timeout,check=check)

# Stop only the temporary control-browser service/profile.
run(["/bin/launchctl","bootout",f"gui/{uid}/{LABEL}"],30)
ps=run(["/bin/ps","-axo","pid=,command="],20)
needle=f"--user-data-dir={DEST}"
killed=[]
for line in ps.stdout.splitlines():
    try:
        pid_s,cmd=line.strip().split(None,1)
        if cmd.startswith("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome ") and needle in cmd:
            pid=int(pid_s)
            os.kill(pid,15); killed.append(pid)
    except Exception:
        pass
time.sleep(2)

# Snapshot the currently last-used signed-in Chrome profile without touching Main Chrome.
shutil.rmtree(DEST,ignore_errors=True)
DEST.mkdir(parents=True,exist_ok=True)
for name in ["Local State","First Run"]:
    s=SRCROOT/name
    if s.exists():
        if s.is_file(): shutil.copy2(s,DEST/name)

dp=DEST/PROFILE_NAME
dp.mkdir(parents=True,exist_ok=True)
cmd=[
    "/usr/bin/rsync","-a",
    "--exclude=Cache/","--exclude=Code Cache/","--exclude=GPUCache/",
    "--exclude=Media Cache/","--exclude=GrShaderCache/","--exclude=GraphiteDawnCache/",
    "--exclude=Crashpad/","--exclude=BrowserMetrics/",
    str(SRC)+"/",str(dp)+"/"
]
r=run(cmd,600)
if r.returncode:
    print(json.dumps({"ok":False,"stage":"rsync","stderr":r.stderr[-12000:]})); raise SystemExit(2)

# Do not restore source tabs into the temporary control browser.
for p in list(DEST.glob("Singleton*"))+list(dp.glob("Singleton*")):
    try:
        if p.is_dir(): shutil.rmtree(p)
        else: p.unlink()
    except Exception: pass
for name in ["Sessions","Current Session","Current Tabs","Last Session","Last Tabs"]:
    p=dp/name
    try:
        if p.is_dir(): shutil.rmtree(p)
        elif p.exists(): p.unlink()
    except Exception: pass

# Mark copied profile clean and prevent session-restore prompts.
pref=dp/"Preferences"
try:
    j=json.loads(pref.read_text(errors="ignore"))
    j.setdefault("profile",{})["exit_type"]="Normal"
    j.setdefault("profile",{})["exited_cleanly"]=True
    j.setdefault("session",{})["restore_on_startup"]=5
    pref.write_text(json.dumps(j,separators=(",",":")),encoding="utf-8")
except Exception:
    pass

# Non-secret cookie metadata only.
cookie_paths=[dp/"Network"/"Cookies",dp/"Cookies"]
cookie_meta=[{"path":str(p),"exists":p.exists(),"size":p.stat().st_size if p.exists() else 0} for p in cookie_paths]

if not PLIST.exists():
    print(json.dumps({"ok":False,"stage":"plist_missing","plist":str(PLIST),"cookie_meta":cookie_meta}))
    raise SystemExit(3)

run(["/bin/launchctl","bootstrap",f"gui/{uid}",str(PLIST)],30)
run(["/bin/launchctl","kickstart","-k",f"gui/{uid}/{LABEL}"],30)

alive=False
pages=[]
deadline=time.time()+30
while time.time()<deadline:
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:19498/json/list",timeout=3) as rr:
            pages=json.load(rr)
        alive=True; break
    except Exception:
        time.sleep(1)

print(json.dumps({
    "ok":alive,
    "killed":killed,
    "profile_name":PROFILE_NAME,
    "source":str(SRC),
    "dest":str(DEST),
    "cookie_meta":cookie_meta,
    "page_count":len(pages),
    "pages":[{"id":p.get("id"),"type":p.get("type"),"title":p.get("title"),"url":p.get("url")} for p in pages if p.get("type")=="page"][:20]
},ensure_ascii=False))
