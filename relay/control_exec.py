#!/usr/bin/env python3
import os, sys, json, base64, time, subprocess, urllib.request, urllib.error, urllib.parse
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

    if a=="main_chrome_state":
        out={}
        p=run(["/bin/ps","-p","482","-o","pid=,ppid=,command="],15)
        out["pid482"]=p.stdout.strip()
        p2=run(["/bin/ps","-axo","pid=,ppid=,command="],20)
        roots=[]
        for line in p2.stdout.splitlines():
            if "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" in line and "Helper" not in line:
                roots.append(line.strip())
        out["chrome_roots"]=roots
        try:
            ls=Path.home()/"Library/Application Support/Google/Chrome/Local State"
            j=json.loads(ls.read_text(errors="ignore"))
            prof=j.get("profile") or {}
            out["profile_state"]={
              "last_used":prof.get("last_used"),
              "last_active_profiles":prof.get("last_active_profiles"),
              "profiles_order":prof.get("profiles_order")
            }
        except Exception as e:
            out["profile_state_error"]=str(e)
        for prof in ["Default","Profile 33"]:
            try:
                pref=Path.home()/"Library/Application Support/Google/Chrome"/prof/"Preferences"
                if pref.exists():
                    j=json.loads(pref.read_text(errors="ignore"))
                    out[prof]={
                      "profile_name":(j.get("profile") or {}).get("name"),
                      "exit_type":(j.get("profile") or {}).get("exit_type"),
                      "exited_cleanly":(j.get("profile") or {}).get("exited_cleanly"),
                      "account_info_count":len(j.get("account_info") or []),
                      "has_network_cookies":(Path.home()/"Library/Application Support/Google/Chrome"/prof/"Network"/"Cookies").exists()
                    }
            except Exception as e:
                out[prof+"_error"]=str(e)
        return {"ok":True,"state":out}

    if a=="browser_inventory":
        out={}
        p=run(["/bin/ps","-axo","pid=,ppid=,command="],30)
        keep=[]
        for line in p.stdout.splitlines():
            low=line.lower()
            if any(k in low for k in [
                "google chrome","chromium","opera","microsoft edge","brave browser",
                "arc.app","safari.app","chatgpt.app","electron"
            ]):
                keep.append(line)
        out["processes"]="\n".join(keep)[-50000:]
        scripts={
          "visible_apps":'''tell application "System Events" to get name of every process whose visible is true''',
          "chrome":'''tell application "Google Chrome"
set outText to "windows=" & (count of windows) & linefeed
repeat with wi from 1 to count of windows
 set outText to outText & "window " & wi & " tabs=" & (count of tabs of window wi) & linefeed
 repeat with ti from 1 to count of tabs of window wi
  try
   set outText to outText & "TAB|" & wi & "|" & ti & "|" & title of tab ti of window wi & "|" & URL of tab ti of window wi & linefeed
  end try
 end repeat
end repeat
return outText
end tell''',
          "safari":'''tell application "Safari"
set outText to "windows=" & (count of windows) & linefeed
repeat with wi from 1 to count of windows
 repeat with ti from 1 to count of tabs of window wi
  try
   set outText to outText & "TAB|" & wi & "|" & ti & "|" & name of tab ti of window wi & "|" & URL of tab ti of window wi & linefeed
  end try
 end repeat
end repeat
return outText
end tell'''
        }
        for k,s in scripts.items():
            try:
                q=run(["/usr/bin/osascript","-e",s],25)
                out[k]={"rc":q.returncode,"stdout":q.stdout[-30000:],"stderr":q.stderr[-12000:]}
            except Exception as e:
                out[k]={"error":type(e).__name__,"message":str(e)}
        # Non-secret profile metadata only.
        try:
            ls=Path.home()/"Library/Application Support/Google/Chrome/Local State"
            if ls.exists():
                j=json.loads(ls.read_text(errors="ignore"))
                info=(j.get("profile") or {}).get("info_cache") or {}
                out["chrome_profiles"]={k:{
                    "name":v.get("name"),"user_name":v.get("user_name"),
                    "gaia_name":v.get("gaia_name"),"is_using_default_name":v.get("is_using_default_name")
                } for k,v in info.items()}
        except Exception as e:
            out["chrome_profiles_error"]=str(e)
        return {"ok":True,"inventory":out}

    if a=="conversation_api_probe":
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        cid=target.rstrip("/").split("/")[-1]
        start_js=f'''(() => {{
 window.__CHATLOCAL_API_PROBE__={{done:false,status:null,len:0,error:null,text:""}};
 fetch("/backend-api/conversation/{cid}",{{credentials:"include"}})
  .then(async r=>{{
    const t=await r.text();
    window.__CHATLOCAL_API_PROBE__={{done:true,status:r.status,len:t.length,error:null,text:t.slice(-25000)}};
  }})
  .catch(e=>{{window.__CHATLOCAL_API_PROBE__={{done:true,status:null,len:0,error:String(e),text:""}};}});
 return "STARTED";
}})()'''
        read_js=r'''(() => {
 const x=window.__CHATLOCAL_API_PROBE__||{};
 const t=x.text||"";
 return JSON.stringify({
   done:!!x.done,status:x.status,len:x.len||0,error:x.error||null,
   has_current_user:t.includes("lanjutkan sampai tuntas"),
   has_112:t.includes("chatlokal-rendered-proof-20260920-112"),
   has_117:t.includes("chatlokal-v4-proof-20260920-117"),
   has_bootstrap107:t.includes("chatlokal-bootstrap-final-20260920-107"),
   tail:t.slice(-4000)
 });
})()'''
        def osa_for(code):
            b=base64.b64encode(code.encode()).decode()
            uq=target.replace("\\","\\\\").replace('"','\\"')
            sc=f'''
tell application "Google Chrome"
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    if URL of tab ti of window wi is "{uq}" then
     return execute tab ti of window wi javascript "eval(atob('{b}'))"
    end if
   end try
  end repeat
 end repeat
 return "__TARGET_NOT_FOUND__"
end tell
'''
            return run(["/usr/bin/osascript","-e",sc],35)
        p1=osa_for(start_js)
        time.sleep(float(req.get("wait",5)))
        p2=osa_for(read_js)
        raw=(p2.stdout or "").strip()
        try:
            data=json.loads(raw)
        except Exception:
            data={"raw":raw,"stderr":p2.stderr[-12000:],"returncode":p2.returncode}
        return {"ok":p1.returncode==0 and p2.returncode==0,"start":(p1.stdout or "").strip(),"probe":data}

    if a=="conversation_probe_osa":
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        # Keep only the requested page in the dedicated CDP profile.
        closed=[]
        try:
            with urllib.request.urlopen("http://127.0.0.1:19498/json/list",timeout=10) as r:
                pages=json.load(r)
            for p in pages:
                if p.get("type")=="page" and (p.get("url") or "")!=target:
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:19498/json/close/"+p["id"],timeout=3) as rr:
                            rr.read()
                        closed.append({"id":p.get("id"),"url":p.get("url")})
                    except Exception:
                        pass
        except Exception:
            pass
        js=r'''(() => {
 const A=[...document.querySelectorAll('[data-message-author-role="assistant"]')];
 const U=[...document.querySelectorAll('[data-message-author-role="user"]')];
 const body=document.body?.innerText||"";
 return JSON.stringify({
   url:location.href,title:document.title,ready:document.readyState,
   assistants:A.length,users:U.length,
   composer:!!document.querySelector('#prompt-textarea,[contenteditable="true"][data-virtualkeyboard],[contenteditable="true"][data-testid="prompt-textarea"]'),
   last_assistant:(A.at(-1)?.innerText||A.at(-1)?.textContent||"").slice(-5000),
   last_user:(U.at(-1)?.innerText||U.at(-1)?.textContent||"").slice(-3000),
   has_current_user:body.includes("lanjutkan sampai tuntas"),
   has_112:body.includes("chatlokal-rendered-proof-20260920-112"),
   has_117:body.includes("chatlokal-v4-proof-20260920-117"),
   body_tail:body.slice(-8000)
 });
})()'''
        b64=base64.b64encode(js.encode()).decode()
        uq=target.replace("\\","\\\\").replace('"','\\"')
        script=f'''
tell application "Google Chrome"
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    if URL of tab ti of window wi is "{uq}" then
     return execute tab ti of window wi javascript "eval(atob('{b64}'))"
    end if
   end try
  end repeat
 end repeat
 return "__TARGET_NOT_FOUND__"
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],35)
        raw=(p.stdout or "").strip()
        try:
            dom=json.loads(raw)
        except Exception:
            dom={"raw":raw,"stderr":p.stderr[-12000:],"returncode":p.returncode}
        return {"ok":p.returncode==0 and raw!="__TARGET_NOT_FOUND__","closed":closed,"dom":dom}

    if a=="conversation_probe":
        port=int(req.get("port",19498))
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=10) as r:
                pages=json.load(r)
        except Exception as e:
            return {"ok":False,"error":type(e).__name__,"message":str(e)}
        page=None
        for p in pages:
            if p.get("type")=="page" and (p.get("url") or "").startswith(target):
                page=p; break
        if not page:
            return {"ok":False,"error":"TARGET_NOT_FOUND","page_count":len(pages),
                    "chat_pages":[{"title":p.get("title"),"url":p.get("url")} for p in pages if p.get("type")=="page" and "chatgpt.com" in (p.get("url") or "")]}
        py=r'''
import sys,json
sys.path.insert(0,"/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal")
from cdp_ws import WSClient
p=json.loads(sys.stdin.read())
wsurl=p["webSocketDebuggerUrl"]
expr="""(() => {
 const A=[...document.querySelectorAll('[data-message-author-role="assistant"]')];
 const U=[...document.querySelectorAll('[data-message-author-role="user"]')];
 const body=document.body?.innerText||"";
 return JSON.stringify({
   url:location.href,
   title:document.title,
   ready:document.readyState,
   assistants:A.length,
   users:U.length,
   composer:!!document.querySelector('#prompt-textarea,[contenteditable="true"][data-virtualkeyboard],[contenteditable="true"][data-testid="prompt-textarea"]'),
   last_assistant:(A.at(-1)?.innerText||A.at(-1)?.textContent||"").slice(-5000),
   last_user:(U.at(-1)?.innerText||U.at(-1)?.textContent||"").slice(-3000),
   has_current_user:body.includes("lanjutkan sampai tuntas"),
   has_112:body.includes("chatlokal-rendered-proof-20260920-112"),
   has_117:body.includes("chatlokal-v4-proof-20260920-117"),
   body_tail:body.slice(-8000)
 });
})()"""
with WSClient(wsurl,timeout=8) as ws:
    ws.send_json({"id":1,"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True,"userGesture":True}})
    while True:
        x=ws.recv_json()
        if x.get("id")==1:
            print(x.get("result",{}).get("result",{}).get("value",""))
            break
'''
        p2=subprocess.run(["/usr/local/bin/python3","-c",py],input=json.dumps(page),capture_output=True,text=True,timeout=30)
        try:
            data=json.loads(p2.stdout)
        except Exception:
            data={"raw":p2.stdout[-12000:],"stderr":p2.stderr[-12000:]}
        return {"ok":p2.returncode==0,"page":{"id":page.get("id"),"url":page.get("url"),"title":page.get("title")},"dom":data}

    if a=="control_browser_open":
        port=19498
        url=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        endpoint="http://127.0.0.1:%d/json/new?%s"%(port,urllib.parse.quote(url,safe=":/?=&"))
        q=urllib.request.Request(endpoint,method="PUT")
        created=None
        try:
            with urllib.request.urlopen(q,timeout=5) as r:
                created=json.load(r)
        except Exception as e:
            created={"error":type(e).__name__,"message":str(e)}
        time.sleep(float(req.get("wait",8)))
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=5) as r:
                pages=json.load(r)
        except Exception as e:
            return {"ok":False,"created":created,"error":type(e).__name__,"message":str(e)}
        probe=[]
        py=r'''
import sys,json
sys.path.insert(0,"/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal")
from cdp_ws import WSClient
pages=json.loads(sys.stdin.read())
out=[]
for p in pages:
    wsurl=p.get("webSocketDebuggerUrl")
    row={"id":p.get("id"),"url":p.get("url"),"title":p.get("title")}
    if not wsurl:
        out.append(row); continue
    try:
        with WSClient(wsurl,timeout=5) as ws:
            ws.send_json({"id":1,"method":"Runtime.evaluate","params":{
                "expression":"""(() => JSON.stringify({
                  url:location.href,
                  title:document.title,
                  ready:document.readyState,
                  assistants:document.querySelectorAll('[data-message-author-role="assistant"]').length,
                  users:document.querySelectorAll('[data-message-author-role="user"]').length,
                  composer:!!document.querySelector('#prompt-textarea,[contenteditable="true"][data-virtualkeyboard],[contenteditable="true"][data-testid="prompt-textarea"]'),
                  body:(document.body?.innerText||"").slice(-5000)
                }))()""",
                "returnByValue":True
            }})
            while True:
                x=ws.recv_json()
                if x.get("id")==1:
                    row["eval"]=x.get("result",{}).get("result",{}).get("value")
                    break
    except Exception as e:
        row["eval_error"]=type(e).__name__+": "+str(e)
    out.append(row)
print(json.dumps(out,ensure_ascii=False))
'''
        p2=subprocess.run(["/usr/local/bin/python3","-c",py],input=json.dumps(pages),capture_output=True,text=True,timeout=30)
        try:
            probe=json.loads(p2.stdout)
        except Exception:
            probe=[{"stdout":p2.stdout[-12000:],"stderr":p2.stderr[-12000:]}]
        return {"ok":True,"created":created,"pages":pages,"probe":probe}

    if a=="quick_status":
        out={}
        try:
            h=run(["/usr/bin/curl","-sS","--max-time","4","http://127.0.0.1:8765/health"],10)
            out["health_raw"]=h.stdout
            out["health_rc"]=h.returncode
        except Exception as e:
            out["health_error"]=str(e)
        for name,path in {
            "injector_main_status": APP/"injector_main_status.json",
            "main_bridge_status": APP/"main_bridge_status.json",
            "main_bridge_v3_status": APP/"main_bridge_v3_status.json",
            "daemon_err": RUN/"daemon.err.log",
            "injector_err": RUN/"injector.err.log",
            "requests_tail": RUN/"requests.jsonl",
            "results_tail": RUN/"results.jsonl"
        }.items():
            try:
                out[name]=tail(path,12000)
            except Exception as e:
                out[name+"_error"]=str(e)
        try:
            with urllib.request.urlopen("http://127.0.0.1:19498/json/list",timeout=3) as r:
                out["control_pages"]=json.load(r)
        except Exception as e:
            out["control_pages_error"]=str(e)
        p=run(["/bin/ps","-axo","pid=,ppid=,command="],20)
        out["processes"]="\n".join(line for line in p.stdout.splitlines()
            if "chat_local" in line or "chat-lokal" in line or "actions.runner" in line)[-20000:]
        return {"ok":True,"status":out}

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
echo "=== CONTROL BROWSER INSTALL ==="; /usr/local/bin/python3 relay/install_control_browser.py 2>&1 || true; echo
echo "=== CONTROL BROWSER CDP ==="; curl -sS --max-time 4 http://127.0.0.1:19498/json/list 2>&1 || true; echo
echo "=== CLUSTER ALIVE PROBE ==="; /usr/local/bin/python3 "$APP/cluster_alive_probe.py" 2>&1 || true; echo
echo "=== SOURCE cluster_alive_probe.py ==="; sed -n '1,220p' "$APP/cluster_alive_probe.py" 2>&1 || true; echo
echo "=== SOURCE launch_cluster.py ==="; sed -n '1,320p' "/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/launch_cluster.py" 2>&1 || true; echo
echo "=== LIVE AGENT17-27 PAGES ==="
for p in $(seq 19417 19427); do
  echo "--- PORT $p ---"
  curl -sS --max-time 3 "http://127.0.0.1:$p/json/list" 2>&1 || true
  echo
done
echo "=== MAIN CHROME PROBE ==="; /usr/local/bin/python3 "$APP/main_chrome_probe.py" 2>&1 || true; echo
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
