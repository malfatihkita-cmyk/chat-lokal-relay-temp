#!/usr/bin/env python3
import os, time, subprocess, shutil, urllib.request, json
from pathlib import Path

ROOT=Path("/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool")
APP=ROOT/"Chat-Lokal"
RUN=Path.home()/".copytolive-chat-lokal"
LA=Path.home()/"Library/LaunchAgents"
SEED=ROOT/"profiles"/"seed-userdata"
PROFILE=ROOT/"chat-local-control-profile"
SCRIPT=APP/"chat_local_control_browser.py"
PLIST=LA/"com.copytolive.chat-lokal-control-browser.plist"
LABEL="com.copytolive.chat-lokal-control-browser"
PORT=19498
CHAT_URL="https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b"

APP.mkdir(parents=True,exist_ok=True)
RUN.mkdir(parents=True,exist_ok=True)
LA.mkdir(parents=True,exist_ok=True)

browser=r'''#!/usr/local/bin/python3
import os,time,subprocess,shutil,urllib.request
from pathlib import Path

ROOT=Path("/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool")
SEED=ROOT/"profiles"/"seed-userdata"
PROFILE=ROOT/"chat-local-control-profile"
RUN=Path.home()/".copytolive-chat-lokal"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT=19498
URL="https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b"
LOG=RUN/"control-browser.log"

def log(*x):
    s=time.strftime("%Y-%m-%d %H:%M:%S")+" "+" ".join(map(str,x))
    with LOG.open("a",encoding="utf-8") as f:f.write(s+"\n")

def ready():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version",timeout=2) as r:
            return r.status==200
    except Exception:
        return False

def root_pid():
    needle=f"--user-data-dir={PROFILE}"
    p=subprocess.run(["/bin/ps","-axo","pid=,command="],capture_output=True,text=True)
    for line in p.stdout.splitlines():
        try:
            pid_s,cmd=line.strip().split(None,1)
            if cmd.startswith(CHROME+" ") and needle in cmd:
                return int(pid_s)
        except Exception:
            pass
    return None

def prepare():
    if not (PROFILE/"Local State").exists():
        shutil.rmtree(PROFILE,ignore_errors=True)
        subprocess.run(["/bin/cp","-cR",str(SEED),str(PROFILE)],check=True)
    for p in PROFILE.glob("Singleton*"):
        try:p.unlink()
        except Exception:pass

def launch():
    prepare()
    args=[
        CHROME,
        f"--user-data-dir={PROFILE}",
        "--profile-directory=Profile 33",
        "--remote-debugging-address=127.0.0.1",
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-notifications",
        "--disable-session-crashed-bubble",
        "--disable-background-mode",
        "--mute-audio",
        "--window-size=900,900",
        URL
    ]
    lf=open(RUN/"control-browser.chrome.log","ab",buffering=0)
    p=subprocess.Popen(args,stdout=lf,stderr=lf,start_new_session=True)
    log("LAUNCHED",p.pid)
    return p.pid

log("SUPERVISOR_START",os.getpid())
while True:
    try:
        if not ready():
            pid=root_pid()
            if not pid:
                launch()
            end=time.time()+20
            while time.time()<end and not ready():
                time.sleep(.5)
            log("READY",ready())
    except Exception as e:
        log("ERROR",type(e).__name__,str(e))
    time.sleep(3)
'''
SCRIPT.write_text(browser,encoding="utf-8")
os.chmod(SCRIPT,0o700)

plist=f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{LABEL}</string>
<key>ProgramArguments</key><array>
<string>/usr/local/bin/python3</string>
<string>{SCRIPT}</string>
</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>{RUN/"control-browser.out.log"}</string>
<key>StandardErrorPath</key><string>{RUN/"control-browser.err.log"}</string>
</dict></plist>
'''
PLIST.write_text(plist,encoding="utf-8")
subprocess.run(["/usr/bin/plutil","-lint",str(PLIST)],check=True)
uid=str(os.getuid())
subprocess.run(["/bin/launchctl","bootout",f"gui/{uid}/{LABEL}"],capture_output=True,text=True)
subprocess.run(["/bin/launchctl","bootstrap",f"gui/{uid}",str(PLIST)],check=True)
subprocess.run(["/bin/launchctl","kickstart","-k",f"gui/{uid}/{LABEL}"],check=True)

deadline=time.time()+25
while time.time()<deadline:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list",timeout=2) as r:
            pages=json.load(r)
        print(json.dumps({"ok":True,"port":PORT,"pages":pages},ensure_ascii=False))
        break
    except Exception:
        time.sleep(.5)
else:
    print(json.dumps({"ok":False,"port":PORT,"error":"control_browser_not_ready"}))
