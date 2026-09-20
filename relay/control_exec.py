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
    if a=="open_profile_via_menu":
        profile_menu=str(req.get("menu_name") or "Copy")
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        # Use Chrome's profile menu to open the requested existing user profile without killing Main Chrome.
        script=f'''
tell application "Google Chrome" to activate
delay 0.7
tell application "System Events"
 tell process "Google Chrome"
  set prof to missing value
  try
   set prof to menu bar item "Profil" of menu bar 1
  on error
   try
    set prof to menu bar item "Profile" of menu bar 1
   end try
  end try
  if prof is missing value then return "PROFILE_MENU_NOT_FOUND"
  click prof
  delay 0.5
  set it to missing value
  try
   set it to menu item "{profile_menu.replace('"','\\"')}" of menu 1 of prof
  end try
  if it is missing value then
   key code 53
   return "PROFILE_ITEM_NOT_FOUND"
  end if
  click it
  return "PROFILE_CLICKED"
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        time.sleep(float(req.get("wait",3)))
        # Ask Chrome to create a window in the now-selected profile if none exists.
        mk=r'''tell application "Google Chrome"
 activate
 if (count of windows) is 0 then
  make new window
 end if
 return count of windows
end tell'''
        m=run(["/usr/bin/osascript","-e",mk],35)
        time.sleep(1)
        nav_target=target.replace("\\","\\\\").replace('"','\\"')
        nav=f'''tell application "Google Chrome"
 if (count of windows) is 0 then return "__NO_WINDOWS__"
 set URL of active tab of front window to "{nav_target}"
 return URL of active tab of front window
end tell'''
        n=run(["/usr/bin/osascript","-e",nav],35)
        time.sleep(float(req.get("nav_wait",6)))
        # Now JS is enabled, so inspect all ChatGPT tabs.
        js=r'''(() => JSON.stringify({
 url:location.href,title:document.title,ready:document.readyState,
 body:(document.body?.innerText||'').slice(-5000),
 composer:!!document.querySelector('#prompt-textarea,[contenteditable="true"][data-virtualkeyboard],[contenteditable="true"][data-testid="prompt-textarea"]')
}))()'''
        b=base64.b64encode(js.encode()).decode()
        probe=f'''tell application "Google Chrome"
 set outText to ""
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    set u to URL of tab ti of window wi
    if u starts with "https://chatgpt.com/" then
     set r to execute tab ti of window wi javascript "eval(atob('{b}'))"
     set outText to outText & wi & ":" & ti & "|" & u & "|" & r & linefeed
    end if
   end try
  end repeat
 end repeat
 return outText
end tell'''
        q=run(["/usr/bin/osascript","-e",probe],45)
        return {"ok":p.returncode==0 and m.returncode==0 and n.returncode==0 and q.returncode==0,
                "profile":(p.stdout or "").strip(),"profile_err":p.stderr[-4000:],
                "windows":(m.stdout or "").strip(),"windows_err":m.stderr[-4000:],
                "nav":(n.stdout or "").strip(),"nav_err":n.stderr[-4000:],
                "probe":q.stdout[-20000:],"probe_err":q.stderr[-8000:]}

    if a=="open_profile_window":
        profile=str(req.get("profile") or "Profile 33")
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        # Ask the existing Chrome singleton to open an additional window in this profile.
        # This does not stop, replace, or relaunch Main Chrome.
        chrome="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        p=run([chrome,"--profile-directory="+profile,"--new-window",target],30)
        if p.returncode!=0:
            p=run(["/usr/bin/open","-a","Google Chrome","--args","--profile-directory="+profile,"--new-window",target],30)
        time.sleep(float(req.get("wait",6)))
        js=r'''(() => {
 const cid=location.pathname.split('/').pop();
 window.__CTL_PROFILE_PROBE__={done:false};
 Promise.all([
   fetch('/backend-api/me',{credentials:'include'}).then(async r=>({name:'me',status:r.status,text:(await r.text()).slice(0,8000)})).catch(e=>({name:'me',error:String(e)})),
   fetch('/backend-api/conversation/'+cid,{credentials:'include'}).then(async r=>({name:'conversation',status:r.status,text:(await r.text()).slice(-12000)})).catch(e=>({name:'conversation',error:String(e)}))
 ]).then(x=>window.__CTL_PROFILE_PROBE__={done:true,data:x}).catch(e=>window.__CTL_PROFILE_PROBE__={done:true,error:String(e)});
 return JSON.stringify({url:location.href,title:document.title,ready:document.readyState,body:(document.body?.innerText||'').slice(-5000)});
})()'''
        b=base64.b64encode(js.encode()).decode()
        uq=target.replace("\\","\\\\").replace('"','\\"')
        sc=f'''
tell application "Google Chrome"
 set outText to ""
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    set u to URL of tab ti of window wi
    set outText to outText & wi & ":" & ti & "|" & u & linefeed
    if u is "{uq}" then
     set r to execute tab ti of window wi javascript "eval(atob('{b}'))"
     return "FOUND|" & wi & "|" & ti & "|" & r
    end if
   end try
  end repeat
 end repeat
 return "NOT_FOUND|" & outText
end tell
'''
        s1=run(["/usr/bin/osascript","-e",sc],45)
        time.sleep(3)
        read_js=r'''(() => JSON.stringify(window.__CTL_PROFILE_PROBE__||{}))()'''
        rb=base64.b64encode(read_js.encode()).decode()
        sc2=f'''
tell application "Google Chrome"
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    if URL of tab ti of window wi is "{uq}" then
     return execute tab ti of window wi javascript "eval(atob('{rb}'))"
    end if
   end try
  end repeat
 end repeat
 return "__TARGET_NOT_FOUND__"
end tell
'''
        s2=run(["/usr/bin/osascript","-e",sc2],45)
        raw=(s2.stdout or "").strip()
        try:
            probe=json.loads(raw)
        except Exception:
            probe={"raw":raw,"stderr":s2.stderr[-8000:],"rc":s2.returncode}
        return {"ok":s1.returncode==0 and s2.returncode==0,"open_rc":p.returncode,
                "open_stderr":p.stderr[-4000:],"start":(s1.stdout or "")[-12000:],"probe":probe}

    if a=="chrome_developer_menu_inventory":
        script=r'''
tell application "Google Chrome" to activate
delay 1
tell application "System Events"
 tell process "Google Chrome"
  set v to menu bar item "Lihat" of menu bar 1
  click v
  delay 0.4
  set d to menu item "Pengembang" of menu 1 of v
  set outText to ""
  repeat with mi in every menu item of menu 1 of d
   try
    set outText to outText & "|" & (name of mi)
   end try
  end repeat
  key code 53
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-12000:],"stderr":p.stderr[-8000:]}

    if a=="chrome_menu_inventory":
        script=r'''
tell application "Google Chrome" to activate
delay 1
tell application "System Events"
 tell process "Google Chrome"
  set outText to "MENUBAR:"
  repeat with mbi in every menu bar item of menu bar 1
   try
    set outText to outText & "|" & (name of mbi)
   end try
  end repeat
  set outText to outText & linefeed
  repeat with mbi in every menu bar item of menu bar 1
   try
    set nm to name of mbi
    click mbi
    delay 0.2
    set outText to outText & "MENU[" & nm & "]:"
    repeat with mi in every menu item of menu 1 of mbi
     try
      set outText to outText & "|" & (name of mi)
     end try
    end repeat
    set outText to outText & linefeed
    key code 53
   end try
  end repeat
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],60)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-30000:],"stderr":p.stderr[-12000:]}

    if a=="chrome_developer_submenu":
        script=r'''
tell application "Google Chrome" to activate
delay 1
tell application "System Events"
 tell process "Google Chrome"
  set viewItem to missing value
  try
   set viewItem to menu bar item "Lihat" of menu bar 1
  on error
   try
    set viewItem to menu bar item "View" of menu bar 1
   end try
  end try
  if viewItem is missing value then return "VIEW_MENU_NOT_FOUND"
  click viewItem
  delay 0.4
  set devItem to missing value
  try
   set devItem to menu item "Pengembang" of menu 1 of viewItem
  on error
   try
    set devItem to menu item "Developer" of menu 1 of viewItem
   end try
  end try
  if devItem is missing value then
   key code 53
   return "DEVELOPER_MENU_NOT_FOUND"
  end if
  set outText to "DEVSUB:"
  try
   repeat with mi in every menu item of menu 1 of devItem
    try
     set outText to outText & "|" & (name of mi)
    end try
   end repeat
  on error errText
   set outText to outText & "|ERR:" & errText
  end try
  key code 53
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-12000:],"stderr":p.stderr[-8000:]}

    if a=="chrome_ax_deep_probe":
        wi=int(req.get("window",3))
        limit=int(req.get("limit",700))
        script=f'''
tell application "Google Chrome" to activate
delay 0.5
tell application "System Events"
 tell process "Google Chrome"
  if (count of windows) < {wi} then return "WINDOW_NOT_FOUND"
  set w to window {wi}
  set outText to "WINDOW|" & {wi} & "|"
  try
   set outText to outText & (name of w)
  end try
  set outText to outText & linefeed
  set els to entire contents of w
  set n to count of els
  set outText to outText & "COUNT|" & n & linefeed
  set lim to {limit}
  if n < lim then set lim to n
  repeat with i from 1 to lim
   set e to item i of els
   set r to ""
   set sr to ""
   set nm to ""
   set ds to ""
   set vl to ""
   try
    set r to role of e as text
   end try
   try
    set sr to subrole of e as text
   end try
   try
    set nm to name of e as text
   end try
   try
    set ds to description of e as text
   end try
   try
    set vl to value of e as text
   end try
   if (r contains "Web") or (r contains "Text") or (r contains "Button") or (r contains "Group") or (nm is not "") or (ds is not "") or (vl is not "") then
    set outText to outText & "E|" & i & "|r=" & r & "|sr=" & sr & "|n=" & nm & "|d=" & ds & "|v=" & vl & linefeed
   end if
  end repeat
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],90)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-60000:],"stderr":p.stderr[-12000:]}

    if a=="chrome_ui_inventory":
        script=r'''
tell application "Google Chrome" to activate
delay 0.5
tell application "System Events"
 tell process "Google Chrome"
  set outText to "WINDOW_COUNT|" & (count of windows) & linefeed
  repeat with wi from 1 to count of windows
   set w to window wi
   try
    set outText to outText & "WINDOW|" & wi & "|" & (name of w) & linefeed
   on error
    set outText to outText & "WINDOW|" & wi & "|<noname>" & linefeed
   end try
   try
    set outText to outText & "BUTTONS|"
    repeat with btn in every button of w
     try
      set outText to outText & (name of btn) & "|"
     end try
    end repeat
    set outText to outText & linefeed
   end try
   try
    set sc to count of sheets of w
    set outText to outText & "SHEETS|" & sc & linefeed
    repeat with sh in every sheet of w
     set outText to outText & "SHEET_BUTTONS|"
     try
      repeat with btn in every button of sh
       try
        set outText to outText & (name of btn) & "|"
       end try
      end repeat
     end try
     set outText to outText & linefeed
     set outText to outText & "SHEET_TEXT|"
     try
      repeat with txtItem in every static text of sh
       try
        set outText to outText & (value of txtItem as text) & "|"
       end try
      end repeat
     end try
     set outText to outText & linefeed
    end repeat
   end try
  end repeat
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-20000:],"stderr":p.stderr[-8000:]}


    if a=="chrome_js_menu_item_state":
        script=r'''
tell application "Google Chrome" to activate
delay 0.5
tell application "System Events"
 tell process "Google Chrome"
  set viewItem to menu bar item "Lihat" of menu bar 1
  click viewItem
  delay 0.3
  set devItem to menu item "Pengembang" of menu 1 of viewItem
  click devItem
  delay 0.4
  set targetItem to menu item "Izinkan JavaScript dari Apple Events" of menu 1 of devItem
  set en to enabled of targetItem
  set mk to ""
  try
   set mk to value of attribute "AXMenuItemMarkChar" of targetItem
  end try
  set posText to ""
  set sizeText to ""
  try
   set p to position of targetItem
   set posText to (item 1 of p as text) & "," & (item 2 of p as text)
  end try
  try
   set s to size of targetItem
   set sizeText to (item 1 of s as text) & "," & (item 2 of s as text)
  end try
  key code 53
  return "enabled=" & en & "|mark=" & mk & "|pos=" & posText & "|size=" & sizeText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":p.stdout[-8000:],"stderr":p.stderr[-8000:]}

    if a=="developer_menu_inventory":
        script=r'''
tell application "Google Chrome" to activate
delay 1
tell application "System Events"
 tell process "Google Chrome"
  set viewItem to missing value
  try
   set viewItem to menu bar item "Lihat" of menu bar 1
  on error
   try
    set viewItem to menu bar item "View" of menu bar 1
   end try
  end try
  if viewItem is missing value then return "VIEW_MENU_NOT_FOUND"
  click viewItem
  delay 0.5
  set devItem to missing value
  try
   set devItem to menu item "Pengembang" of menu 1 of viewItem
  on error
   try
    set devItem to menu item "Developer" of menu 1 of viewItem
   end try
  end try
  if devItem is missing value then
   key code 53
   return "DEVELOPER_MENU_NOT_FOUND"
  end if
  set outText to ""
  try
   set outText to name of every menu item of menu 1 of devItem as text
  on error errText
   set outText to "ERR|" & errText
  end try
  key code 53
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-20000:],"stderr":p.stderr[-12000:]}

    if a=="select_chrome_window_by_title":
        wanted=str(req.get("title") or "Bootstrap Final Berhasil")
        esc=wanted.replace("\\","\\\\").replace('"','\\"')
        script=f'''
tell application "Google Chrome" to activate
delay 1
tell application "System Events"
 tell process "Google Chrome"
  try
   click menu bar item "Jendela" of menu bar 1
  on error
   click menu bar item "Window" of menu bar 1
  end try
  delay 0.5
  set m to menu 1 of (menu bar item "Jendela" of menu bar 1)
  set targetItem to missing value
  repeat with mi in every menu item of m
   try
    if name of mi is "{esc}" then
     set targetItem to mi
     exit repeat
    end if
   end try
  end repeat
  if targetItem is missing value then
   key code 53
   return "WINDOW_ITEM_NOT_FOUND"
  end if
  click targetItem
  delay 1
  return "SELECTED"
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        probe=r'''tell application "Google Chrome"
 set outText to "windows=" & (count of windows) & linefeed
 repeat with wi from 1 to count of windows
  repeat with ti from 1 to count of tabs of window wi
   try
    set outText to outText & wi & ":" & ti & "|" & title of tab ti of window wi & "|" & URL of tab ti of window wi & linefeed
   end try
  end repeat
 end repeat
 return outText
end tell'''
        q=run(["/usr/bin/osascript","-e",probe],35)
        return {"ok":p.returncode==0,"select":(p.stdout or "").strip(),"select_err":p.stderr[-8000:],
                "probe_rc":q.returncode,"probe":q.stdout[-20000:],"probe_err":q.stderr[-8000:]}

    if a=="chrome_dev_submenu_inventory":
        script=r'''
tell application "Google Chrome" to activate
delay 0.7
tell application "System Events"
 tell process "Google Chrome"
  set outText to ""
  set viewItem to missing value
  try
   set viewItem to menu bar item "Lihat" of menu bar 1
  on error
   try
    set viewItem to menu bar item "View" of menu bar 1
   end try
  end try
  if viewItem is missing value then return "VIEW_NOT_FOUND"
  click viewItem
  delay 0.4
  set devItem to missing value
  try
   set devItem to menu item "Pengembang" of menu 1 of viewItem
  on error
   try
    set devItem to menu item "Developer" of menu 1 of viewItem
   end try
  end try
  if devItem is missing value then
   key code 53
   return "DEV_NOT_FOUND"
  end if
  try
   set outText to "DEVSUB|" & (name of every menu item of menu 1 of devItem as text)
  on error errText
   try
    perform action "AXShowMenu" of devItem
    delay 0.4
    set outText to "DEVSUB_AFTER_SHOW|" & (name of every menu item of menu 1 of devItem as text)
   on error err2
    set outText to "DEVSUBERR|" & errText & "|" & err2
   end try
  end try
  key code 53
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        return {"ok":p.returncode==0,"returncode":p.returncode,
                "stdout":(p.stdout or "")[-30000:],"stderr":p.stderr[-12000:]}

    if a=="enable_chrome_js_apple_events":
        script=r'''
tell application "Google Chrome" to activate
delay 0.7
tell application "System Events"
 tell process "Google Chrome"
  set viewItem to missing value
  repeat with nm in {"Lihat","View","Tampilan"}
   try
    set viewItem to menu bar item nm of menu bar 1
    exit repeat
   end try
  end repeat
  if viewItem is missing value then return "VIEW_MENU_NOT_FOUND"
  click viewItem
  delay 0.4
  set devItem to missing value
  repeat with nm in {"Pengembang","Developer"}
   try
    set devItem to menu item nm of menu 1 of viewItem
    exit repeat
   end try
  end repeat
  if devItem is missing value then
   key code 53
   return "DEVELOPER_MENU_NOT_FOUND"
  end if
  try
   perform action "AXShowMenu" of devItem
  on error
   try
    click devItem
   end try
  end try
  delay 0.5
  set targetItem to missing value
  repeat with nm in {"Izinkan JavaScript dari Apple Events","Allow JavaScript from Apple Events"}
   try
    set targetItem to menu item nm of menu 1 of devItem
    exit repeat
   end try
  end repeat
  if targetItem is missing value then
   key code 53
   return "TARGET_ITEM_NOT_FOUND"
  end if
  set markChar to ""
  try
   set markChar to value of attribute "AXMenuItemMarkChar" of targetItem
  end try
  if markChar is not missing value and markChar is not "" then
   key code 53
   return "ALREADY_ENABLED|" & markChar
  end if
  click targetItem
  delay 0.8
  return "CLICKED"
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],45)
        time.sleep(1)
        test=r'''tell application "Google Chrome"
 if (count of windows) is 0 then return "__NO_WINDOWS__"
 return execute active tab of front window javascript "JSON.stringify({url:location.href,title:document.title,ok:true})"
end tell'''
        q=run(["/usr/bin/osascript","-e",test],35)
        return {"ok":q.returncode==0,"toggle_rc":p.returncode,
                "toggle":(p.stdout or "").strip(),"toggle_err":p.stderr[-8000:],
                "test_rc":q.returncode,"test":(q.stdout or "").strip(),"test_err":q.stderr[-8000:]}

    if a=="main_tab_api_probe":
        start_js=r'''(() => {
 window.__CTL_MAIN_PROBE__={done:false};
 Promise.all([
   fetch('/backend-api/me',{credentials:'include'}).then(async r=>({name:'me',status:r.status,text:(await r.text()).slice(0,8000)})).catch(e=>({name:'me',error:String(e)})),
   fetch('/backend-api/conversations?offset=0&limit=5',{credentials:'include'}).then(async r=>({name:'conversations',status:r.status,text:(await r.text()).slice(0,16000)})).catch(e=>({name:'conversations',error:String(e)}))
 ]).then(x=>window.__CTL_MAIN_PROBE__={done:true,data:x}).catch(e=>window.__CTL_MAIN_PROBE__={done:true,error:String(e)});
 return JSON.stringify({url:location.href,title:document.title,body:(document.body?.innerText||'').slice(-5000)});
})()'''
        b=base64.b64encode(start_js.encode()).decode()
        s1=f'''tell application "Google Chrome"
 if (count of windows) is 0 then return "__NO_WINDOWS__"
 return execute active tab of front window javascript "eval(atob('{b}'))"
end tell'''
        p1=run(["/usr/bin/osascript","-e",s1],35)
        time.sleep(3)
        read_js=r'''(() => JSON.stringify(window.__CTL_MAIN_PROBE__||{}))()'''
        rb=base64.b64encode(read_js.encode()).decode()
        s2=f'''tell application "Google Chrome"
 if (count of windows) is 0 then return "__NO_WINDOWS__"
 return execute active tab of front window javascript "eval(atob('{rb}'))"
end tell'''
        p2=run(["/usr/bin/osascript","-e",s2],35)
        raw=(p2.stdout or "").strip()
        try:data=json.loads(raw)
        except Exception:data={"raw":raw,"stderr":p2.stderr[-8000:],"rc":p2.returncode}
        return {"ok":p1.returncode==0 and p2.returncode==0,
                "start":(p1.stdout or "")[-8000:],"probe":data,
                "stderr":(p1.stderr+p2.stderr)[-8000:]}

    if a=="chrome_window_menu_inventory":
        script=r'''
tell application "System Events"
 set cp to first process whose name is "Google Chrome"
 tell cp
  set winMB to missing value
  try
   set winMB to menu bar item "Jendela" of menu bar 1
  on error
   try
    set winMB to menu bar item "Window" of menu bar 1
   end try
  end try
  if winMB is missing value then return "WINDOW_MENU_NOT_FOUND"
  click winMB
  delay 0.4
  set outText to ""
  set idx to 0
  repeat with mi in every menu item of menu 1 of winMB
   set idx to idx + 1
   set nm to ""
   set en to ""
   set mk to ""
   set posText to ""
   try
    set nm to name of mi as text
   end try
   try
    set en to enabled of mi as text
   end try
   try
    set mk to value of attribute "AXMenuItemMarkChar" of mi as text
   end try
   try
    set pp to position of mi
    set posText to (item 1 of pp as text) & "," & (item 2 of pp as text)
   end try
   set outText to outText & idx & "|" & nm & "|enabled=" & en & "|mark=" & mk & "|pos=" & posText & linefeed
  end repeat
  key code 53
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],60)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-40000:],"stderr":p.stderr[-12000:]}

    if a=="press_window_menu_item":
        wanted=str(req.get("title") or "Bootstrap Final Berhasil")
        esc=wanted.replace("\\","\\\\").replace('"','\\"')
        script=f'''
tell application "System Events"
 set cp to first process whose name is "Google Chrome"
 tell cp
  set winMB to missing value
  try
   set winMB to menu bar item "Jendela" of menu bar 1
  on error
   set winMB to menu bar item "Window" of menu bar 1
  end try
  click winMB
  delay 0.4
  set mi to menu item "{esc}" of menu 1 of winMB
  set beforeEn to enabled of mi
  set beforeMark to ""
  try
   set beforeMark to value of attribute "AXMenuItemMarkChar" of mi as text
  end try
  try
   perform action "AXPress" of mi
  on error
   click mi
  end try
 end tell
 delay 1
 set fp to first process whose frontmost is true
 set outText to "before_enabled=" & beforeEn & "|before_mark=" & beforeMark & "|frontmost=" & (name of fp) & "|pid=" & (unix id of fp) & "|windows=" & (count of windows of fp) & linefeed
 repeat with wi from 1 to count of windows of fp
  set w to window wi of fp
  set wn to ""
  set doc to ""
  try
   set wn to name of w as text
  end try
  try
   set doc to value of attribute "AXDocument" of w as text
  end try
  set outText to outText & "WINDOW|" & wi & "|name=" & wn & "|doc=" & doc & linefeed
 end repeat
 return outText
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],60)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-40000:],"stderr":p.stderr[-12000:]}

    if a=="select_window_frontmost_probe":
        wanted=str(req.get("title") or "Bootstrap Final Berhasil")
        esc=wanted.replace("\\","\\\\").replace('"','\\"')
        script=f'''
tell application "System Events"
 set chromePs to every process whose name is "Google Chrome"
 set clicked to false
 repeat with cp in chromePs
  try
   tell cp
    if exists menu bar 1 then
     set winMB to missing value
     try
      set winMB to menu bar item "Jendela" of menu bar 1
     on error
      try
       set winMB to menu bar item "Window" of menu bar 1
      end try
     end try
     if winMB is not missing value then
      click winMB
      delay 0.2
      try
       set mi to menu item "{esc}" of menu 1 of winMB
       if exists mi then
        click mi
        set clicked to true
        exit repeat
       end if
      end try
      key code 53
     end if
    end if
   end tell
  end try
 end repeat
 delay 1
 set fp to first process whose frontmost is true
 set outText to "clicked=" & clicked & "|frontmost_name=" & (name of fp) & "|pid=" & (unix id of fp) & "|windows=" & (count of windows of fp) & linefeed
 repeat with wi from 1 to count of windows of fp
  set w to window wi of fp
  set wn to ""
  set doc to ""
  try
   set wn to name of w as text
  end try
  try
   set doc to value of attribute "AXDocument" of w as text
  end try
  set outText to outText & "WINDOW|" & wi & "|name=" & wn & "|doc=" & doc & linefeed
 end repeat
 return outText
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],60)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-40000:],"stderr":p.stderr[-12000:]}

    if a=="chrome_process_inventory":
        script=r'''
tell application "System Events"
 set outText to ""
 set ps to every process whose name is "Google Chrome"
 set outText to "processes=" & (count of ps) & linefeed
 repeat with p in ps
  set pidText to ""
  set fm to ""
  try
   set pidText to unix id of p as text
  end try
  try
   set fm to frontmost of p as text
  end try
  set outText to outText & "PROCESS|pid=" & pidText & "|frontmost=" & fm & "|windows=" & (count of windows of p) & linefeed
  repeat with wi from 1 to count of windows of p
   set w to window wi of p
   set wn to ""
   set doc to ""
   try
    set wn to name of w as text
   end try
   try
    set doc to value of attribute "AXDocument" of w as text
   end try
   set outText to outText & "WINDOW|pid=" & pidText & "|i=" & wi & "|name=" & wn & "|doc=" & doc & linefeed
  end repeat
 end repeat
 return outText
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],60)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-50000:],"stderr":p.stderr[-12000:]}

    if a=="chrome_ax_probe":
        script=r'''
tell application "Google Chrome" to activate
delay 0.7
tell application "System Events"
 tell process "Google Chrome"
  set outText to "frontmost=" & frontmost & linefeed
  set outText to outText & "windows=" & (count of windows) & linefeed
  repeat with wi from 1 to count of windows
   set w to window wi
   set outText to outText & "WINDOW|" & wi & "|name=" & (name of w) & linefeed
   try
    set outText to outText & "AXDocument=" & (value of attribute "AXDocument" of w as text) & linefeed
   end try
   try
    set outText to outText & "AXRole=" & (value of attribute "AXRole" of w as text) & "|AXSubrole=" & (value of attribute "AXSubrole" of w as text) & linefeed
   end try
   try
    set kids to UI elements of w
    set outText to outText & "children=" & (count of kids) & linefeed
    set lim to count of kids
    if lim > 80 then set lim to 80
    repeat with i from 1 to lim
     set e to item i of kids
     set rn to ""
     set nm to ""
     set ds to ""
     set vl to ""
     try
      set rn to role of e as text
     end try
     try
      set nm to name of e as text
     end try
     try
      set ds to description of e as text
     end try
     try
      set vl to value of e as text
      if (length of vl) > 500 then set vl to text 1 thru 500 of vl
     end try
     set outText to outText & "E|" & i & "|role=" & rn & "|name=" & nm & "|desc=" & ds & "|value=" & vl & linefeed
    end repeat
   end try
  end repeat
  return outText
 end tell
end tell
'''
        p=run(["/usr/bin/osascript","-e",script],50)
        return {"ok":p.returncode==0,"returncode":p.returncode,"stdout":p.stdout[-40000:],"stderr":p.stderr[-12000:]}

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

    if a=="refresh_control_profile":
        p=run(["/usr/local/bin/python3","relay/refresh_control_profile.py"],700)
        raw=(p.stdout or "").strip()
        try:
            data=json.loads(raw.splitlines()[-1]) if raw else {}
        except Exception:
            data={"raw":raw[-20000:],"stderr":p.stderr[-12000:]}
        return {"ok":p.returncode==0 and bool(data.get("ok")),"returncode":p.returncode,"data":data,"stderr":p.stderr[-12000:]}

    if a=="profile_http_probe":
        import sqlite3, hashlib, http.cookiejar
        profile=str(req.get("profile") or "Profile 33")
        cid=str(req.get("conversation_id") or "6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        base=Path.home()/"Library/Application Support/Google/Chrome"/profile
        cp=None
        for cand in (base/"Network"/"Cookies",base/"Cookies"):
            if cand.exists():
                cp=cand; break
        if not cp:
            return {"ok":False,"error":"COOKIE_DB_NOT_FOUND","profile":profile}
        keypass=None
        key_attempts=[
          ["/usr/bin/security","find-generic-password","-w","-s","Chrome Safe Storage"],
          ["/usr/bin/security","find-generic-password","-w","-a","Chrome","-s","Chrome Safe Storage"]
        ]
        key_error=[]
        for cmd in key_attempts:
            q=run(cmd,20)
            if q.returncode==0 and (q.stdout or "").strip():
                keypass=(q.stdout or "").strip()
                break
            key_error.append((q.stderr or q.stdout or "").strip()[-1000:])
        if not keypass:
            return {"ok":False,"error":"KEYCHAIN_KEY_UNAVAILABLE","details":key_error}
        key=hashlib.pbkdf2_hmac("sha1",keypass.encode(),b"saltysalt",1003,16)
        iv=b" "*16
        def dec(host,enc):
            if enc is None:return ""
            if isinstance(enc,memoryview):enc=enc.tobytes()
            if enc.startswith((b"v10",b"v11")):
                raw=enc[3:]
                q=subprocess.run(
                    ["/usr/bin/openssl","enc","-d","-aes-128-cbc","-K",key.hex(),"-iv",iv.hex(),"-nopad"],
                    input=raw,capture_output=True,timeout=10
                )
                if q.returncode!=0:return ""
                pt=q.stdout
                if not pt:return ""
                pad=pt[-1]
                if 1<=pad<=16 and pt.endswith(bytes([pad])*pad):
                    pt=pt[:-pad]
                hh=hashlib.sha256(host.encode()).digest()
                if pt.startswith(hh):
                    pt=pt[32:]
                try:return pt.decode()
                except Exception:return pt.decode("utf-8","ignore")
            try:return enc.decode()
            except Exception:return ""
        cookies=[]
        bad=0
        con=sqlite3.connect("file:"+str(cp)+"?mode=ro",uri=True,timeout=3)
        cur=con.cursor()
        cur.execute("""select host_key,name,value,encrypted_value,path,is_secure,expires_utc
                       from cookies
                       where host_key like '%chatgpt.com' or host_key like '%openai.com'""")
        for host,name,value,enc,path0,secure,exp in cur.fetchall():
            val=value or dec(host,enc)
            if not val:
                bad+=1; continue
            # Only cookies applicable to chatgpt.com request host.
            h=host.lstrip(".")
            if h!="chatgpt.com" and not "chatgpt.com".endswith("."+h):
                continue
            cookies.append((name,val))
        con.close()
        header="; ".join(k+"="+v for k,v in cookies)
        ua="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        def get(url):
            q=urllib.request.Request(url,headers={
                "User-Agent":ua,"Accept":"application/json,text/plain,*/*",
                "Cookie":header,"Referer":"https://chatgpt.com/"
            })
            try:
                with urllib.request.urlopen(q,timeout=20) as r:
                    body=r.read().decode(errors="ignore")
                    return {"status":r.status,"len":len(body),"body":body}
            except urllib.error.HTTPError as e:
                body=e.read().decode(errors="ignore")
                return {"status":e.code,"len":len(body),"body":body}
            except Exception as e:
                return {"status":None,"error":type(e).__name__,"message":str(e),"body":""}
        me=get("https://chatgpt.com/backend-api/me")
        conv=get("https://chatgpt.com/backend-api/conversation/"+cid)
        def summarize(x):
            b=x.get("body") or ""
            return {
                "status":x.get("status"),"len":x.get("len"),"error":x.get("error"),
                "logged_out":("Log in to" in b or "conversation_inaccessible" in b),
                "has_current_user":"lanjutkan sampai tuntas" in b,
                "has_107":"chatlokal-bootstrap-final-20260920-107" in b,
                "has_117":"chatlokal-v4-proof-20260920-117" in b,
                "tail":b[-1200:] if x.get("status") not in (200,) else ""
            }
        return {"ok":True,"profile":profile,"keychain_ok":True,
                "cookie_count_used":len(cookies),"decrypt_failures":bad,
                "me":summarize(me),"conversation":summarize(conv)}

    if a=="chrome_profile_cookie_names":
        import sqlite3
        profile=str(req.get("profile") or "Profile 33")
        base=Path.home()/"Library/Application Support/Google/Chrome"/profile
        cp=None
        for cand in (base/"Network"/"Cookies",base/"Cookies"):
            if cand.exists():
                cp=cand; break
        if not cp:
            return {"ok":False,"error":"COOKIE_DB_NOT_FOUND","profile":profile}
        rows=[]
        try:
            con=sqlite3.connect("file:"+str(cp)+"?mode=ro",uri=True,timeout=3)
            cur=con.cursor()
            cur.execute("""select host_key,name,expires_utc,is_persistent,length(encrypted_value)
                           from cookies
                           where host_key like '%chatgpt.com' or host_key like '%openai.com'
                           order by host_key,name""")
            for host,name,exp,persist,enc_len in cur.fetchall():
                rows.append({"host":host,"name":name,"expires_utc":exp,
                             "persistent":persist,"encrypted_len":enc_len})
            con.close()
        except Exception as e:
            return {"ok":False,"error":type(e).__name__,"message":str(e),"profile":profile}
        return {"ok":True,"profile":profile,"cookie_db":str(cp),"cookies":rows}

    if a=="chrome_profile_inventory":
        import sqlite3
        base=Path.home()/"Library/Application Support/Google/Chrome"
        out={}
        try:
            ls=json.loads((base/"Local State").read_text(errors="ignore"))
            prof=(ls.get("profile") or {})
            out["last_used"]=prof.get("last_used")
            out["last_active_profiles"]=prof.get("last_active_profiles")
            info=prof.get("info_cache") or {}
        except Exception as e:
            info={}
            out["local_state_error"]=str(e)
        rows=[]
        for p in sorted([x for x in base.iterdir() if x.is_dir() and (x.name=="Default" or x.name.startswith("Profile "))],key=lambda x:x.name):
            row={"profile":p.name}
            try:
                pref=p/"Preferences"
                if pref.exists():
                    j=json.loads(pref.read_text(errors="ignore"))
                    row["name"]=(j.get("profile") or {}).get("name")
                    row["account_info_count"]=len(j.get("account_info") or [])
            except Exception as e:
                row["pref_error"]=str(e)
            try:
                inf=info.get(p.name) or {}
                row["user_name"]=inf.get("user_name")
                row["gaia_name"]=inf.get("gaia_name")
            except Exception:
                pass
            cp=None
            for cand in (p/"Network"/"Cookies",p/"Cookies"):
                if cand.exists():
                    cp=cand; break
            row["cookies_path"]=str(cp) if cp else None
            row["cookies_size"]=cp.stat().st_size if cp else 0
            if cp:
                try:
                    con=sqlite3.connect("file:"+str(cp)+"?mode=ro",uri=True,timeout=2)
                    cur=con.cursor()
                    for label,pat in [
                        ("chatgpt","%chatgpt.com"),
                        ("openai","%openai.com"),
                        ("auth0","%auth0.com")
                    ]:
                        cur.execute("select count(*), coalesce(sum(length(encrypted_value)),0) from cookies where host_key like ?",(pat,))
                        n,s=cur.fetchone()
                        row[label+"_cookie_count"]=n
                        row[label+"_encrypted_bytes"]=s
                    con.close()
                except Exception as e:
                    row["cookie_query_error"]=type(e).__name__+": "+str(e)
            rows.append(row)
        out["profiles"]=rows
        return {"ok":True,"inventory":out}

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

    if a=="cdp_port_inventory":
        rows=[]
        for port in range(int(req.get("start",19417)),int(req.get("end",19438))+1):
            row={"port":port,"alive":False,"pages":[]}
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=2) as r:
                    pages=json.load(r)
                row["alive"]=True
                row["pages"]=[{"id":p.get("id"),"type":p.get("type"),"title":p.get("title"),"url":p.get("url")} for p in pages if p.get("type")=="page"][:8]
            except Exception as e:
                row["error"]=type(e).__name__+": "+str(e)
            rows.append(row)
        return {"ok":True,"rows":rows}

    if a=="cdp_open_chat_probe":
        port=int(req.get("port",19438))
        target=str(req.get("url") or "https://chatgpt.com/c/6aaf2627-1e20-83ec-b0c8-77bc60da329b")
        try:
            q=urllib.request.Request(
                "http://127.0.0.1:%d/json/new?%s"%(port,urllib.parse.quote(target,safe=":/?=&")),
                method="PUT"
            )
            with urllib.request.urlopen(q,timeout=8) as r:
                created=json.load(r)
        except Exception as e:
            created={"error":type(e).__name__,"message":str(e)}
        time.sleep(float(req.get("wait",8)))
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=8) as r:
                pages=json.load(r)
        except Exception as e:
            return {"ok":False,"created":created,"error":type(e).__name__,"message":str(e)}
        page=None
        for p in pages:
            if p.get("type")=="page" and (p.get("url") or "").startswith(target):
                page=p; break
        if not page:
            for p in pages:
                if p.get("type")=="page" and "chatgpt.com" in (p.get("url") or ""):
                    page=p; break
        if not page:
            return {"ok":False,"created":created,"pages":[{"title":p.get("title"),"url":p.get("url")} for p in pages]}
        py=r'''
import sys,json,time
sys.path.insert(0,"/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal")
from cdp_ws import WSClient
p=json.loads(sys.stdin.read())
expr="""(() => {
 window.__CTL_AGENT_PROBE__={done:false};
 const cid=location.pathname.split('/').pop();
 Promise.all([
  fetch('/backend-api/me',{credentials:'include'}).then(async r=>({name:'me',status:r.status,text:(await r.text()).slice(0,6000)})).catch(e=>({name:'me',error:String(e)})),
  fetch('/backend-api/conversation/'+cid,{credentials:'include'}).then(async r=>({name:'conversation',status:r.status,text:(await r.text()).slice(-18000)})).catch(e=>({name:'conversation',error:String(e)}))
 ]).then(x=>window.__CTL_AGENT_PROBE__={done:true,data:x}).catch(e=>window.__CTL_AGENT_PROBE__={done:true,error:String(e)});
 return JSON.stringify({url:location.href,title:document.title,ready:document.readyState,body:(document.body?.innerText||'').slice(-6000)});
})()"""
with WSClient(p["webSocketDebuggerUrl"],timeout=8) as ws:
    ws.send_json({"id":1,"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True,"userGesture":True}})
    first=""
    while True:
        x=ws.recv_json()
        if x.get("id")==1:
            first=x.get("result",{}).get("result",{}).get("value","")
            break
time.sleep(3)
with WSClient(p["webSocketDebuggerUrl"],timeout=8) as ws:
    ws.send_json({"id":2,"method":"Runtime.evaluate","params":{"expression":"JSON.stringify(window.__CTL_AGENT_PROBE__||{})","returnByValue":True}})
    second=""
    while True:
        x=ws.recv_json()
        if x.get("id")==2:
            second=x.get("result",{}).get("result",{}).get("value","")
            break
print(json.dumps({"first":first,"second":second}))
'''
        p2=subprocess.run(["/usr/local/bin/python3","-c",py],input=json.dumps(page),capture_output=True,text=True,timeout=45)
        try:
            data=json.loads(p2.stdout)
            for k in ("first","second"):
                if isinstance(data.get(k),str) and data[k]:
                    try:data[k]=json.loads(data[k])
                    except Exception:pass
        except Exception:
            data={"raw":p2.stdout[-20000:],"stderr":p2.stderr[-12000:]}
        return {"ok":p2.returncode==0,"port":port,"created":created,
                "page":{"id":page.get("id"),"url":page.get("url"),"title":page.get("title")},
                "probe":data}

    if a=="cdp_session_probe":
        port=int(req.get("port",19498))
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json/list"%port,timeout=10) as r:
                pages=json.load(r)
        except Exception as e:
            return {"ok":False,"error":type(e).__name__,"message":str(e)}
        page=None
        for p in pages:
            if p.get("type")=="page" and "chatgpt.com" in (p.get("url") or ""):
                page=p; break
        if not page:
            return {"ok":False,"error":"CHATGPT_PAGE_NOT_FOUND","pages":[{"title":p.get("title"),"url":p.get("url")} for p in pages]}
        py=r'''
import sys,json,time
sys.path.insert(0,"/Users/Shared/WorkspaceBersama/ChatGPTHeadlessPool/Chat-Lokal")
from cdp_ws import WSClient
p=json.loads(sys.stdin.read())
expr="""(() => {
 window.__CTL_SESSION__={done:false};
 Promise.all([
   fetch('/backend-api/me',{credentials:'include'}).then(async r=>({name:'me',status:r.status,text:(await r.text()).slice(0,12000)})).catch(e=>({name:'me',error:String(e)})),
   fetch('/backend-api/conversations?offset=0&limit=5',{credentials:'include'}).then(async r=>({name:'conversations',status:r.status,text:(await r.text()).slice(0,16000)})).catch(e=>({name:'conversations',error:String(e)}))
 ]).then(x=>window.__CTL_SESSION__={done:true,data:x}).catch(e=>window.__CTL_SESSION__={done:true,error:String(e)});
 return JSON.stringify({url:location.href,title:document.title,ready:document.readyState,body:(document.body?.innerText||'').slice(-6000)});
})()"""
with WSClient(p["webSocketDebuggerUrl"],timeout=8) as ws:
    ws.send_json({"id":1,"method":"Runtime.evaluate","params":{"expression":expr,"returnByValue":True,"userGesture":True}})
    first=""
    while True:
        x=ws.recv_json()
        if x.get("id")==1:
            first=x.get("result",{}).get("result",{}).get("value","")
            break
time.sleep(3)
with WSClient(p["webSocketDebuggerUrl"],timeout=8) as ws:
    ws.send_json({"id":2,"method":"Runtime.evaluate","params":{"expression":"JSON.stringify(window.__CTL_SESSION__||{})","returnByValue":True}})
    second=""
    while True:
        x=ws.recv_json()
        if x.get("id")==2:
            second=x.get("result",{}).get("result",{}).get("value","")
            break
print(json.dumps({"first":first,"second":second}))
'''
        p2=subprocess.run(["/usr/local/bin/python3","-c",py],input=json.dumps(page),capture_output=True,text=True,timeout=40)
        try:
            data=json.loads(p2.stdout)
            if data.get("first"):
                try:data["first"]=json.loads(data["first"])
                except Exception:pass
            if data.get("second"):
                try:data["second"]=json.loads(data["second"])
                except Exception:pass
        except Exception:
            data={"raw":p2.stdout[-16000:],"stderr":p2.stderr[-12000:]}
        return {"ok":p2.returncode==0,"page":{"id":page.get("id"),"url":page.get("url"),"title":page.get("title")},"probe":data}

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
