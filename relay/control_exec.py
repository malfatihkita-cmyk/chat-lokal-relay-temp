#!/usr/bin/env python3
import os, sys, json, base64, time, subprocess, urllib.request, urllib.error
from pathlib import Path

REPO=os.environ.get("GITHUB_REPOSITORY","malfatihkita-cmyk/chat-lokal-relay-temp")
TOKEN=os.environ.get("GITHUB_TOKEN","")
APP=Path("/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal")
ROOT=Path("/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool")
RUN=Path.home()/".copytolive-chat-lokal"
LA=Path.home()/"Library/LaunchAgents"


def run(argv,timeout=120):
    return subprocess.run(argv,capture_output=True,text=True,timeout=timeout)

def under(p,root):
    p=Path(p).expanduser().resolve()
    r=Path(root).expanduser().resolve()
    return p==r or r in p.parents

def allowed_read(p):
    return any(under(p,r) for r in (ROOT,RUN,LA))

def allowed_write(p):
    q=Path(p).expanduser().resolve()
    if under(q,APP):
        return True
    return under(q,LA) and q.name.startswith("com.copytolive.")

def tail(path,n=30000):
    p=Path(path).expanduser()
    return p.read_text(errors="ignore")[-n:] if p.exists() else ""

def action(req):
    a=req.get("action","")
    if a=="browser_probe":
        script=r'''
tell application "Google Chrome"
 set outText to ""
 set wc to count of windows
 set outText to outText & "WINDOWS=" & wc & linefeed
 repeat with wi from 1 to wc
  set outText to outText & "WINDOW " & wi & " TABS=" & (count of tabs of window wi) & linefeed
  repeat with ti from 1 to count of tabs of window wi
   try
    set u to URL of tab ti of window wi
    set t to title of tab ti of window wi
    set outText to outText & "TAB " & wi & ":" & ti & " | " & t & " | " & u & linefeed
   on error errText
    set outText to outText & "TABERR " & wi & ":" & ti & " | " & errText & linefeed
   end try
  end repeat
 end repeat
 return outText
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-20000:],"stderr":p.stderr[-12000:]}

    if a=="diagnose":
        s=r'''
APP="/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal"
RUN="$HOME/.copytolive-chat-lokal"
echo "=== DATE ==="; date
echo "=== USER ==="; id
echo "=== CHAT-LOCAL DIR ==="; ls -la "$APP" 2>&1 || true
echo "=== PY FILES ==="; find "$APP" -maxdepth 1 -type f -name '*.py' -print 2>/dev/null | sort || true
echo "=== DAEMON ==="; launchctl print "gui/$(id -u)/com.copytolive.chat-lokal" 2>&1 | head -160 || true
echo "=== INJECTOR ==="; launchctl print "gui/$(id -u)/com.copytolive.chat-lokal-injector" 2>&1 | head -140 || true
echo "=== PORT 8765 ==="; lsof -nP -iTCP:8765 -sTCP:LISTEN 2>&1 || true
echo "=== HEALTH ==="; curl -sS --max-time 4 http://127.0.0.1:8765/health 2>&1 || true; echo
echo "=== DAEMON ERR ==="; tail -n 180 "$RUN/daemon.err.log" 2>&1 || true
echo "=== INJECTOR ERR ==="; tail -n 120 "$RUN/injector.err.log" 2>&1 || true
echo "=== V4 LOG ==="; tail -n 100 "$RUN/transport-v4.log" 2>&1 || true
echo "=== OLD GH RELAY LOG ==="; tail -n 100 "$RUN/github-relay-temp.log" 2>&1 || true
echo "=== SOURCE chat_local.py ==="; sed -n '1,240p' "$APP/chat_local.py" 2>&1 || true
echo "=== SOURCE injector.py ==="; sed -n '1,320p' "$APP/chat_local_injector.py" 2>&1 || true
echo "=== SOURCE bridge_v3.py ==="; sed -n '1,320p' "$APP/chat_local_main_bridge_v3.py" 2>&1 || true
echo "=== SOURCE transport_v4.py ==="; sed -n '1,320p' "$APP/chat_local_transport_v4.py" 2>&1 || true
echo "=== STATUS bridge ==="; cat "$APP/main_bridge_status.json" 2>&1 || true; echo
echo "=== STATUS bridge_v3 ==="; cat "$APP/main_bridge_v3_status.json" 2>&1 || true; echo
echo "=== AGENT38 CDP ==="; curl -sS --max-time 4 http://127.0.0.1:19438/json/list 2>&1 || true; echo
echo "=== AGENT38 VERSION ==="; curl -sS --max-time 4 http://127.0.0.1:19438/json/version 2>&1 || true; echo
echo "=== CHROME APPLESCRIPT TABS ==="
osascript <<'APPLESCRIPT' 2>&1 || true
tell application "Google Chrome"
 set outText to ""
 set wc to count of windows
 set outText to outText & "WINDOWS=" & wc & linefeed
 repeat with wi from 1 to wc
  set outText to outText & "WINDOW " & wi & " TABS=" & (count of tabs of window wi) & linefeed
  repeat with ti from 1 to count of tabs of window wi
   try
    set outText to outText & "TAB " & wi & ":" & ti & " | " & title of tab ti of window wi & " | " & URL of tab ti of window wi & linefeed
   on error errText
    set outText to outText & "TABERR " & wi & ":" & ti & " | " & errText & linefeed
   end try
  end repeat
 end repeat
 return outText
end tell
APPLESCRIPT
'''
        p=run(["/bin/bash","-lc",s],180)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "output":((p.stdout or "")+("\nSTDERR:\n"+p.stderr if p.stderr else ""))[-40000:]}

    if a=="read_file":
        path=str(req.get("path",""))
        if not allowed_read(path):
            return {"ok":False,"error":"READ_PATH_DENIED","path":path}
        return {"ok":True,"path":path,"content":tail(path,int(req.get("max_chars",40000)))}

    if a=="read_files":
        paths=[str(x) for x in req.get("paths",[])][:20]
        rows=[]
        for path in paths:
            if not allowed_read(path):
                rows.append({"path":path,"ok":False,"error":"READ_PATH_DENIED"})
                continue
            p=Path(path).expanduser()
            rows.append({
                "path":str(p),
                "ok":p.exists(),
                "content":tail(p,int(req.get("max_chars_each",30000))) if p.exists() else ""
            })
        return {"ok":True,"files":rows}

    if a=="list_dir":
        path=str(req.get("path",""))
        if not allowed_read(path):
            return {"ok":False,"error":"LIST_PATH_DENIED","path":path}
        rows=[]
        for x in sorted(Path(path).expanduser().iterdir(),key=lambda z:z.name)[:500]:
            try:
                st=x.stat()
                rows.append({"name":x.name,"dir":x.is_dir(),"size":st.st_size})
            except Exception as e:
                rows.append({"name":x.name,"error":str(e)})
        return {"ok":True,"path":path,"entries":rows}

    if a=="write_file":
        path=str(req.get("path",""))
        if not allowed_write(path):
            return {"ok":False,"error":"WRITE_PATH_DENIED","path":path}
        p=Path(path).expanduser()
        data=base64.b64decode(req.get("content_b64",""))
        p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists() and req.get("backup",True):
            b=p.with_name(p.name+".bak-"+time.strftime("%Y%m%d-%H%M%S"))
            b.write_bytes(p.read_bytes())
        p.write_bytes(data)
        if req.get("mode"):
            os.chmod(p,int(str(req["mode"]),8))
        return {"ok":True,"path":str(p),"bytes":len(data)}

    if a=="py_compile":
        files=[str(Path(x).expanduser()) for x in req.get("files",[])]
        if not files or not all(allowed_read(x) for x in files):
            return {"ok":False,"error":"COMPILE_PATH_DENIED"}
        p=run(["/usr/local/bin/python3","-m","py_compile"]+files,90)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-12000:],"stderr":p.stderr[-12000:]}

    if a=="restart_services":
        uid=str(os.getuid())
        labels=req.get("labels") or ["com.copytolive.chat-lokal","com.copytolive.chat-lokal-injector"]
        rows=[]
        for label in labels:
            if not str(label).startswith("com.copytolive."):
                rows.append({"label":label,"error":"LABEL_DENIED"})
                continue
            p=run(["launchctl","kickstart","-k","gui/%s/%s"%(uid,label)],45)
            rows.append({"label":label,"rc":p.returncode,
                         "stdout":p.stdout[-4000:],"stderr":p.stderr[-4000:]})
        time.sleep(float(req.get("wait",2)))
        h=run(["/usr/bin/curl","-sS","--max-time","4","http://127.0.0.1:8765/health"],15)
        return {"ok":h.returncode==0,"services":rows,
                "health_raw":h.stdout[-8000:],"health_err":h.stderr[-4000:]}

    if a=="run_python_file":
        path=str(req.get("path",""))
        rp=Path(path).expanduser().resolve()
        if not under(rp,APP):
            return {"ok":False,"error":"EXEC_PATH_DENIED","path":path}
        args=[str(x) for x in req.get("args",[])]
        p=run(["/usr/local/bin/python3",str(rp)]+args,int(req.get("timeout",240)))
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-30000:],"stderr":p.stderr[-30000:]}

    if a=="close_agent_pages_17_27":
        code=r'''
import urllib.request,json
out=[]
for port in range(19417,19428):
    row={"port":port,"closed":0,"alive_before":False,"alive_after":False}
    try:
        tabs=json.load(urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=3))
        row["alive_before"]=True
        for t in tabs:
            if t.get("type")=="page":
                try:
                    urllib.request.urlopen("http://127.0.0.1:%d/json/close/%s"%(port,t["id"]),timeout=3).read()
                    row["closed"]+=1
                except Exception as e:
                    row.setdefault("close_errors",[]).append(str(e))
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/json/version"%port,timeout=3).read()
            row["alive_after"]=True
        except Exception:
            pass
    except Exception as e:
        row["error"]=str(e)
    out.append(row)
print(json.dumps(out))
'''
        p=run(["/usr/local/bin/python3","-c",code],120)
        return {"ok":p.returncode==0,"output":p.stdout,"stderr":p.stderr}

    return {"ok":False,"error":"UNSUPPORTED_ACTION","action":a}

def gh_rest(method,path,payload=None,timeout=60):
    if not TOKEN:
        raise RuntimeError("missing_GITHUB_TOKEN")
    url="https://api.github.com/"+path.lstrip("/")
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(
        url,data=data,method=method,
        headers={
            "Authorization":"Bearer "+TOKEN,
            "Accept":"application/vnd.github+json",
            "X-GitHub-Api-Version":"2022-11-28",
            "User-Agent":"chat-lokal-temp-runner"
        }
    )
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body=e.read().decode(errors="ignore")
        raise RuntimeError("github_http_%s: %s"%(e.code,body))

def publish(envelope):
    out=Path("relay/result.json")
    out.write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"path":str(out)}

req=json.load(open(sys.argv[1]))
rid=str(req.get("id",""))
try:
    result=action(req)
except Exception as e:
    result={"ok":False,"error":type(e).__name__,"message":str(e)}

envelope={
    "schema":1,
    "id":rid,
    "action":req.get("action"),
    "completed_at":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
    "host":run(["hostname"],20).stdout.strip(),
    "result":result
}
publish(envelope)
print(json.dumps(envelope,ensure_ascii=False))
