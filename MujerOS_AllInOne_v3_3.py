#!/usr/bin/env python3
"""
MujerOS All-in-One (single file)

Run:
  python3 mujeros_allinone.py

This starts a local web app (UI) + a local installer bridge for Flatpak (Flathub).
The UI opens in your default browser automatically.

Security notes:
- Runs ONLY on 127.0.0.1 (localhost)
- Requires a random token for install/update requests (embedded into the UI it serves)
- Prompts you to confirm each install/update (kdialog/zenity or console)

Flatpak installs are done as user installs: flatpak --user install -y flathub <APPID>
"""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APPID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

def run_cmd(args):
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

def has_flatpak() -> bool:
    return shutil.which("flatpak") is not None

def flathub_configured() -> bool:
    if not has_flatpak():
        return False
    code, out, _ = run_cmd(["flatpak", "--user", "remotes"])
    if code != 0:
        return False
    for line in out.splitlines():
        if line.strip() == "flathub" or line.strip().startswith("flathub "):
            return True
    return False

def ensure_flathub_user():
    if not has_flatpak():
        return
    # One-time; safe to call repeatedly
    run_cmd([
        "flatpak", "--user", "remote-add", "--if-not-exists",
        "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo"
    ])


def list_flatpak_apps():
    """Return a list of installed Flatpak apps (user + system), best effort."""
    if not has_flatpak():
        return []

    # Try to include installation column (newer Flatpak). Fallback if unsupported.
    columns_sets = [
        ["application", "name", "version", "branch", "origin", "installation"],
        ["application", "name", "version", "branch", "origin"],
    ]
    last_err = ""
    for cols in columns_sets:
        code, out, err = run_cmd(["flatpak", "list", "--app", f"--columns={','.join(cols)}"])
        if code != 0:
            last_err = err or out
            continue

        apps = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            # Skip possible header line
            if parts and parts[0].strip().lower() in ("application", "application id"):
                continue
            while len(parts) < len(cols):
                parts.append("")
            row = dict(zip(cols, parts))
            app_id = (row.get("application") or "").strip()
            if not app_id:
                continue
            apps.append({
                "id": app_id,
                "name": (row.get("name") or "").strip(),
                "version": (row.get("version") or "").strip(),
                "branch": (row.get("branch") or "").strip(),
                "origin": (row.get("origin") or "").strip(),
                "installation": (row.get("installation") or "").strip() if "installation" in row else "",
            })

        apps.sort(key=lambda a: (a.get("name") or a.get("id") or "").lower())
        return apps

    raise RuntimeError("Could not list flatpaks: " + (last_err or "unknown error"))

def is_flatpak_installed(app_id: str) -> bool:
    if not has_flatpak():
        return False
    code, _, _ = run_cmd(["flatpak", "info", app_id])
    return code == 0

def launch_flatpak(app_id: str):
    """Launch a Flatpak app in the background (best effort)."""
    try:
        subprocess.Popen(["flatpak", "run", app_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True, ""
    except Exception as e:
        return False, str(e)
def gui_confirm(title: str, message: str) -> bool:
    # Try KDE then GNOME, else terminal.
    if os.environ.get("DISPLAY"):
        if shutil.which("kdialog"):
            code, _, _ = run_cmd(["kdialog", "--title", title, "--yesno", message])
            return code == 0
        if shutil.which("zenity"):
            code, _, _ = run_cmd(["zenity", "--question", "--title", title, "--text", message])
            return code == 0

    print(f"\n{title}\n{message}\nType YES to confirm:", flush=True)
    ans = sys.stdin.readline().strip()
    return ans.upper() == "YES"

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>MujerOS v__VERSION__</title>
<style>
:root{
  --accent:#ff4da6;
  --accent2:#7c4dff;
  --bg0:#070714;
  --bg1:#0a0a1f;
  --text: rgba(255,255,255,.92);
  --muted: rgba(255,255,255,.70);
  --shadow: 0 24px 70px rgba(0,0,0,.55);
  --radius: 18px;
  --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono","Courier New", monospace;
  --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji","Segoe UI Emoji";
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;
  font-family:var(--sans);
  color:var(--text);
  background:
    radial-gradient(1200px 800px at 20% 15%, rgba(255,77,166,.22), transparent 55%),
    radial-gradient(900px 700px at 80% 10%, rgba(124,77,255,.18), transparent 60%),
    radial-gradient(1200px 900px at 60% 90%, rgba(0,255,208,.10), transparent 55%),
    linear-gradient(160deg, var(--bg0), var(--bg1));
  overflow:hidden;
  user-select:none;
}
#desktop{ position:relative; width:100%; height:100%; overflow:hidden; background-position:center; background-size:cover; background-repeat:no-repeat; }
#silhouette{
  pointer-events:none; position:absolute; inset:-12%; opacity:.22;
  background-repeat:no-repeat; background-size:110% 110%; background-position:70% 40%;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 900'%3E%3Cdefs%3E%3CradialGradient id='g' cx='60%25' cy='40%25' r='70%25'%3E%3Cstop offset='0%25' stop-color='%23ff4da6' stop-opacity='.75'/%3E%3Cstop offset='55%25' stop-color='%237c4dff' stop-opacity='.45'/%3E%3Cstop offset='100%25' stop-color='%2300ffd0' stop-opacity='.12'/%3E%3C/radialGradient%3E%3C/defs%3E%3Cpath d='M760 120c80 30 130 110 100 190-25 70-105 90-120 165-12 60 45 120 72 170 42 78 10 180-80 220-110 48-230-22-255-140-18-82 35-150 60-220 30-82-22-150-25-230-3-85 58-160 140-180 42-10 72-3 108 25z' fill='url(%23g)'/%3E%3Cpath d='M615 210c-38 10-68 44-64 86 6 60 70 78 62 132-8 56-78 92-70 168 10 90 140 135 206 82 44-35 48-95 22-145-22-43-70-68-62-120 10-60 92-90 66-166-20-58-92-62-160-37z' fill='%23000000' fill-opacity='.35'/%3E%3C/svg%3E");;
}
#overlay{
  pointer-events:none; position:absolute; inset:0;
  background:
    radial-gradient(900px 700px at 70% 35%, rgba(255,77,166,.15), transparent 60%),
    radial-gradient(1200px 900px at 30% 75%, rgba(124,77,255,.14), transparent 55%),
    linear-gradient(180deg, rgba(0,0,0,.14), rgba(0,0,0,.62));
  mix-blend-mode: screen; opacity:.95;
}
#icons{
  position:absolute; top:16px; left:16px;
  display:grid; grid-template-columns:repeat(2, minmax(132px, 1fr));
  gap:12px; z-index:2; width:300px; max-width:calc(100% - 32px);
}
.icon{
  padding:10px; border-radius:16px;
  background: rgba(0,0,0,.18);
  border:1px solid rgba(255,255,255,.12);
  backdrop-filter: blur(10px);
  cursor:pointer;
  transition: transform .12s ease, background .12s ease;
  display:flex; gap:10px; align-items:center; min-height:64px;
}
.icon:hover{ transform: translateY(-1px); background: rgba(0,0,0,.26); }
.icon .glyph{
  width:44px; height:44px; border-radius:16px; display:grid; place-items:center;
  background: linear-gradient(135deg, rgba(255,77,166,.32), rgba(124,77,255,.24));
  border:1px solid rgba(255,255,255,.16);
  box-shadow: 0 10px 20px rgba(0,0,0,.28);
  overflow:hidden;
}
.icon .meta{ flex:1; min-width:0; }
.icon .label{ font-size:12.8px; font-weight:900; letter-spacing:.2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.icon .sub{ margin-top:4px; font-size:11px; color: rgba(255,255,255,.65); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.glyph svg{ width:26px; height:26px; opacity:.92; }

#taskbar{
  position:absolute; left:12px; right:12px; bottom:12px;
  height:54px; border-radius:20px;
  background: rgba(0,0,0,.35);
  border:1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(14px);
  display:flex; align-items:center; gap:10px; padding:8px;
  z-index:9999; box-shadow: var(--shadow);
}
#startBtn{
  height:38px; padding:0 14px; border-radius:14px;
  border:1px solid rgba(255,255,255,.14);
  background: linear-gradient(135deg, rgba(255,77,166,.30), rgba(124,77,255,.22));
  color: rgba(255,255,255,.92);
  cursor:pointer; font-weight:900; letter-spacing:.2px;
}
#startBtn:active{ transform: translateY(1px); }
#tasks{ flex:1; display:flex; gap:8px; overflow:auto; padding-bottom:2px; scrollbar-width:none; }
#tasks::-webkit-scrollbar{ display:none; }
.task{
  height:38px; max-width:260px; padding:0 12px;
  border-radius:14px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.07);
  cursor:pointer;
  display:flex; align-items:center; gap:10px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.task.active{ background: rgba(255,255,255,.11); border-color: rgba(255,255,255,.18); }
.dot{ width:10px; height:10px; border-radius:99px; background: var(--accent); box-shadow: 0 0 18px rgba(255,77,166,.55); }
#tray{ display:flex; align-items:center; gap:10px; padding-left:8px; border-left:1px solid rgba(255,255,255,.12); }
#clock{ font-family:var(--mono); font-size:12.5px; color: rgba(255,255,255,.78); padding:0 10px; }

#startMenu{
  position:absolute; left:12px; bottom:72px;
  width:380px; border-radius:20px;
  background: rgba(0,0,0,.50);
  border:1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(16px);
  box-shadow: var(--shadow);
  padding:12px;
  z-index:9998;
  display:none;
}
#startMenu.show{ display:block; }
.startTitle{ display:flex; align-items:baseline; justify-content:space-between; gap:10px; margin:4px 6px 10px; }
.startTitle .name{ font-weight:900; letter-spacing:.2px; font-size:16px; }
.startTitle .ver{ font-family: var(--mono); font-size:11px; color: rgba(255,255,255,.65); }
.startSearch{
  width:100%; margin:0 0 10px 0;
  border-radius:14px;
  border:1px solid rgba(255,255,255,.14);
  background: rgba(0,0,0,.22);
  color: rgba(255,255,255,.92);
  padding:10px 12px;
  outline:none;
}
.appBtn{
  width:100%;
  display:flex; align-items:center; gap:12px;
  padding:10px 10px;
  border-radius:16px;
  border:1px solid rgba(255,255,255,.10);
  background: rgba(255,255,255,.06);
  cursor:pointer;
  margin-bottom:8px;
  text-align:left;
}
.appBtn:hover{ background: rgba(255,255,255,.09); }
.badge{ margin-left:auto; font-size:11px; color: rgba(255,255,255,.65); font-family:var(--mono); }

#windows{ position:absolute; inset:0; z-index:10; }
.win{
  position:absolute;
  min-width:340px; min-height:240px;
  width:760px; height:520px;
  border-radius: var(--radius);
  background: rgba(0,0,0,.50);
  border:1px solid rgba(255,255,255,.14);
  backdrop-filter: blur(18px);
  box-shadow: var(--shadow);
  overflow:hidden;
  display:flex; flex-direction:column;
}
.win.maximized{
  left:12px !important; top:12px !important;
  width: calc(100% - 24px) !important;
  height: calc(100% - 84px) !important;
}
.titlebar{
  height:44px; padding:0 10px;
  display:flex; align-items:center; gap:10px;
  border-bottom:1px solid rgba(255,255,255,.12);
  background: linear-gradient(135deg, rgba(255,77,166,.14), rgba(124,77,255,.10));
  cursor:grab;
}
.titlebar:active{ cursor:grabbing; }
.wintitle{
  font-weight:900; font-size:13.5px; color: rgba(255,255,255,.90);
  flex:1; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;
  display:flex; align-items:center; gap:10px;
}
.winbtns{ display:flex; gap:6px; }
.wbtn{
  width:30px; height:30px;
  border-radius:10px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.18);
  cursor:pointer;
  display:grid; place-items:center;
  color: rgba(255,255,255,.82);
  font-size:14px;
}
.wbtn:hover{ background: rgba(0,0,0,.28); }
.content{ flex:1; padding:12px; overflow:auto; }
.resizer{
  position:absolute; right:10px; bottom:10px;
  width:18px; height:18px; cursor:nwse-resize; opacity:.65;
  background:
    linear-gradient(135deg, transparent 50%, rgba(255,255,255,.22) 50%),
    linear-gradient(135deg, transparent 60%, rgba(255,255,255,.18) 60%),
    linear-gradient(135deg, transparent 70%, rgba(255,255,255,.14) 70%);
  border-radius:6px;
}

/* Common */
.row{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
.pill{
  display:inline-flex; align-items:center; gap:8px;
  padding:10px 12px; border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.06);
}
.btn{
  padding:10px 12px; border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.08);
  color: rgba(255,255,255,.92);
  cursor:pointer; font-weight:900;
}
.btn:hover{ background: rgba(255,255,255,.11); }
.btn.primary{
  border-color: rgba(255,255,255,.18);
  background: linear-gradient(135deg, rgba(255,77,166,.28), rgba(124,77,255,.20));
}
.btn.danger{ background: rgba(255,60,80,.12); border-color: rgba(255,60,80,.25); }
input[type="text"], input[type="color"], textarea, select{
  border-radius:14px;
  border:1px solid rgba(255,255,255,.14);
  background: rgba(0,0,0,.22);
  color: rgba(255,255,255,.92);
  padding:10px 12px; outline:none; font-family:var(--sans);
}
textarea{
  width:100%; height:240px; resize:vertical;
  font-family: var(--mono); font-size:12.5px; line-height:1.35;
}
.small{ font-size:12.5px; color: var(--muted); }
.hr{ height:1px; background: rgba(255,255,255,.12); margin:10px 0; }
.tag{
  font-family: var(--mono); font-size:11px; color: rgba(255,255,255,.75);
  padding:4px 8px; border-radius:999px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.14);
  white-space:nowrap;
}

/* Browser */
.browserTop{
  display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  padding:10px;
  border-radius:18px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.06);
}
.logoChip{
  display:flex; align-items:center; gap:10px;
  padding:8px 10px; border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: linear-gradient(135deg, rgba(255,77,166,.20), rgba(124,77,255,.15));
  cursor:pointer;
}
.logoMark{
  width:30px; height:30px; border-radius:12px;
  display:grid; place-items:center;
  background: rgba(0,0,0,.20);
  border:1px solid rgba(255,255,255,.12);
  overflow:hidden;
}
.logoText{
  font-weight:900; letter-spacing:.2px;
  max-width:160px; overflow:hidden; white-space:nowrap; text-overflow:ellipsis;
}
.urlBar{ flex:1; min-width:240px; }
.browserFrameWrap{
  margin-top:10px;
  border-radius:18px;
  border:1px solid rgba(255,255,255,.12);
  overflow:hidden;
  background: rgba(0,0,0,.20);
  height:360px;
}
iframe.browserFrame{ width:100%; height:100%; border:0; background: rgba(0,0,0,.20); }
.hintBar{
  margin-top:10px;
  padding:10px 12px;
  border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.18);
  font-size:12.5px;
  color: rgba(255,255,255,.72);
}

/* Media */
.mediaGrid{ display:grid; grid-template-columns:1fr; gap:10px; }
.playlist{
  max-height:170px; overflow:auto;
  border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.18);
  padding:8px;
}
.track{
  padding:8px 10px;
  border-radius:14px;
  border:1px solid rgba(255,255,255,.10);
  background: rgba(255,255,255,.06);
  margin-bottom:8px;
  cursor:pointer;
  display:flex; align-items:center; gap:10px;
}
.track:hover{ background: rgba(255,255,255,.09); }
.track.active{ border-color: rgba(255,255,255,.20); background: rgba(255,255,255,.10); }
.trackName{ flex:1; overflow:hidden; white-space:nowrap; text-overflow:ellipsis; }

/* Calculator */
.calc{ display:grid; grid-template-columns:1fr; gap:10px; }
.calcDisplay{
  border-radius:18px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(0,0,0,.22);
  padding:12px;
  font-family: var(--mono);
  user-select:text;
}
.calcExpr{ color: rgba(255,255,255,.70); font-size:12.5px; }
.calcVal{ font-size:22px; font-weight:900; margin-top:6px; }
.calcKeys{ display:grid; grid-template-columns: repeat(4, 1fr); gap:8px; }
.key{
  padding:14px 10px;
  border-radius:16px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.07);
  cursor:pointer;
  font-weight:900;
  text-align:center;
}
.key:hover{ background: rgba(255,255,255,.11); }
.key.op{ background: rgba(255,255,255,.09); }
.key.eq{ background: linear-gradient(135deg, rgba(255,77,166,.26), rgba(124,77,255,.18)); }
.key.danger{ background: rgba(255,60,80,.12); border-color: rgba(255,60,80,.25); }

/* Store */
.cards{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap:10px; }
.card{
  border-radius:18px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.06);
  padding:12px;
}
.card h3{ margin:0 0 6px 0; font-size:14px; letter-spacing:.2px; }
.card p{ margin:0 0 10px 0; color: rgba(255,255,255,.72); font-size:12.5px; }
.mono{ font-family: var(--mono); user-select:text; font-size:12px; color: rgba(255,255,255,.82); line-height:1.35; white-space: pre-wrap; }

/* Toast */
.toast{
  position:absolute; right:16px; bottom:78px;
  padding:10px 12px; border-radius:16px;
  border:1px solid rgba(255,255,255,.14);
  background: rgba(0,0,0,.55);
  backdrop-filter: blur(12px);
  box-shadow: var(--shadow);
  z-index:10000;
  opacity:0;
  transform: translateY(10px);
  transition: opacity .18s ease, transform .18s ease;
  pointer-events:none;
  max-width:520px;
  font-size:12.5px;
  color: rgba(255,255,255,.88);
}
.toast.show{ opacity:1; transform: translateY(0); }

@media (max-width: 520px){
  #startMenu{ width: calc(100% - 24px); }
  #icons{ width: calc(100% - 32px); grid-template-columns: repeat(2, minmax(140px, 1fr)); }
}
</style>
</head>
<body>
<div id="desktop">
  <div id="silhouette"></div>
  <div id="overlay"></div>

  <div id="icons"></div>
  <div id="windows"></div>
  <div id="startMenu" aria-hidden="true"></div>

  <div id="taskbar">
    <button id="startBtn" title="Start (Ctrl+Space)">✨ Start</button>
    <div id="tasks"></div>
    <div id="tray"><div id="clock"></div></div>
  </div>

  <div id="toast" class="toast"></div>
</div>

<script>
(() => {
  const VERSION = "__VERSION__";
  const STORAGE_KEY = "mujeros_allinone_state";
  const EMBED_TOKEN = "__TOKEN__";
  const EMBED_BASE  = "__BASE__";

  function defaultState(){
    return {
      __bootedOnce:false,
      settings: {
        accent:"#ff4da6",
        accent2:"#7c4dff",
        wallpaperDataUrl:"",
        wallpaperMode:"cover",
        iconTheme:"femme",
        pinnedApps:["browser","music","video","calculator","store","myapps","settings","notes"],

        voiceEnabled:true,
        voiceRate:1.0,
        voicePitch:1.0,
        voiceVolume:1.0,

        touchLine:"Don’t touch me there, honey.",
        moneyLine:"That’s a lot of money!",

        useCustomAudio:false,
        customAudioDataUrl:"",

        browserLogoText:"MujerBrowser",
        browserHome:"mujeros:home",

        installerUrl: EMBED_BASE,
        installerToken: EMBED_TOKEN
      },
      notes: { "notes.txt": "Write anything here...\\n" },
      customIcons: {}
    };
  }

  const state = loadState();
  function loadState(){
    try{
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultState();
      const parsed = JSON.parse(raw);
      const base = defaultState();
      // Merge + ensure current embedded url/token (auto-ready)
      const merged = {
        ...base,
        ...parsed,
        settings: { ...base.settings, ...(parsed.settings||{}) },
        notes: { ...base.notes, ...(parsed.notes||{}) },
        customIcons: { ...base.customIcons, ...(parsed.customIcons||{}) }
      };
      merged.settings.installerUrl = EMBED_BASE;
      merged.settings.installerToken = EMBED_TOKEN;
      return merged;
    } catch { return defaultState(); }
  }
  function persist(){
    try{ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
    catch { toast("Save failed (storage full). Try smaller wallpaper/audio."); }
  }

  const desktop = document.getElementById("desktop");
  const iconsEl = document.getElementById("icons");
  const windowsRoot = document.getElementById("windows");
  const tasksEl = document.getElementById("tasks");
  const startBtn = document.getElementById("startBtn");
  const startMenu = document.getElementById("startMenu");
  const clockEl = document.getElementById("clock");
  const toastEl = document.getElementById("toast");

  window.addEventListener("error", (e) => toast("Error: " + (e?.message || "unknown")));
  window.addEventListener("unhandledrejection", (e) => toast("Error: " + (e?.reason?.message || e?.reason || "unknown")));

  let toastTimer = null;
  function toast(msg){
    toastEl.textContent = String(msg || "");
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(()=>toastEl.classList.remove("show"), 1800);
  }

  function applyTheme(){
    document.documentElement.style.setProperty("--accent", state.settings.accent || "#ff4da6");
    document.documentElement.style.setProperty("--accent2", state.settings.accent2 || "#7c4dff");
    applyWallpaper();
  }
  function applyWallpaper(){
    const url = state.settings.wallpaperDataUrl || "";
    if (url){
      desktop.style.backgroundImage = `url(${url})`;
      desktop.style.backgroundSize = state.settings.wallpaperMode || "cover";
      desktop.style.backgroundPosition = "center";
    } else {
      desktop.style.backgroundImage = "";
    }
  }
  applyTheme();

  // Voice
  function speak(text){
    if (!state.settings.voiceEnabled) return;

    if (state.settings.useCustomAudio && state.settings.customAudioDataUrl){
      try{
        const a = new Audio(state.settings.customAudioDataUrl);
        a.volume = clamp(state.settings.voiceVolume ?? 1, 0, 1);
        a.play().catch(()=>{});
        return;
      } catch {}
    }

    if (!("speechSynthesis" in window)) return;
    try{
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(String(text || ""));
      u.rate = clamp(state.settings.voiceRate ?? 1, 0.5, 2);
      u.pitch = clamp(state.settings.voicePitch ?? 1, 0, 2);
      u.volume = clamp(state.settings.voiceVolume ?? 1, 0, 1);
      window.speechSynthesis.speak(u);
    } catch {}
  }
  function sayTouchLine(){
    const line = state.settings.touchLine || "Don’t touch me there, honey.";
    speak(line);
    toast(line);
  }

  // Installer bridge
  function normBaseUrl(u){ return String(u || "").trim().replace(/\/+$/,""); }

  async function bridgeStatus(){
    const base = normBaseUrl(state.settings.installerUrl);
    const r = await fetch(base + "/status");
    const j = await r.json().catch(()=> ({}));
    if (!r.ok) throw new Error(j.error || r.statusText);
    return j;
  }
  async function bridgePost(path, body){
    const base = normBaseUrl(state.settings.installerUrl);
    const token = String(state.settings.installerToken || "").trim();
    const r = await fetch(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Installer-Token": token },
      body: JSON.stringify(body || {})
    });
    const j = await r.json().catch(()=> ({}));
    if (!r.ok || !j.ok) throw new Error(j.error || j.stderr || r.statusText);
    return j;
  }
  async function installFlatpak(appId){ return bridgePost("/install", { appId }); }
  async function updateFlatpaks(){ return bridgePost("/update", {}); }

  async function bridgeGet(path){
    const base = normBaseUrl(state.settings.installerUrl);
    const token = String(state.settings.installerToken || "").trim();
    const r = await fetch(base + path, { headers: { "X-Installer-Token": token } });
    const j = await r.json().catch(()=> ({}));
    if (!r.ok || !j.ok) throw new Error(j.error || r.statusText);
    return j;
  }
  async function listFlatpaks(){ return bridgeGet("/flatpak/list"); }
  async function runFlatpak(appId){ return bridgePost("/flatpak/run", { appId }); }

  // Icons
  const ICONS = {
    browser: { tag:"WEB" }, music:{tag:"MUS"}, video:{tag:"VID"}, calculator:{tag:"CALC"},
    store:{tag:"STORE"}, myapps:{tag:"APPS"}, settings:{tag:"⚙"}, notes:{tag:"TXT"}, about:{tag:"i"}
  };

  function svgIcon(appId){
    const pack = state.settings.iconTheme || "femme";
    const custom = state.customIcons?.[appId];
    if (custom){
      return `<img alt="" src="${escapeAttr(custom)}" style="width:44px;height:44px;object-fit:cover;border-radius:14px" />`;
    }

    const base = {
      browser: `<path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2Zm7.7 9H14.8c-.2-2.6-1.2-4.7-2.8-6.2A8.01 8.01 0 0 1 19.7 11ZM9.2 11H4.3A8.01 8.01 0 0 1 12 4.8C10.4 6.3 9.4 8.4 9.2 11Zm0 2c.2 2.6 1.2 4.7 2.8 6.2A8.01 8.01 0 0 1 4.3 13h4.9Zm1.9 0h1.8c-.2 2.1-.9 3.9-1.8 5.1-.9-1.2-1.6-3-1.8-5.1Zm1.8-2h-1.8c.2-2.1.9-3.9 1.8-5.1.9 1.2 1.6 3 1.8 5.1Zm.9 2h4.9a8.01 8.01 0 0 1-7.7 6.2c1.6-1.5 2.6-3.6 2.8-6.2Z"/>`,
      music: `<path d="M19 3v12.5a3.5 3.5 0 1 1-2-3.16V6.2L9 8v9.5a3.5 3.5 0 1 1-2-3.16V5l12-2Z"/>`,
      video: `<path d="M4 6a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2.3l3.3-2a1 1 0 0 1 1.5.86v5.62a1 1 0 0 1-1.5.86l-3.3-2V16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6Zm6 3.5v5l5-2.5-5-2.5Z"/>`,
      calculator: `<path d="M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm0 2v4h10V4H7Zm0 6v10h10V10H7Zm2 2h2v2H9v-2Zm0 3h2v2H9v-2Zm3-3h2v2h-2v-2Zm0 3h2v2h-2v-2Zm3-3h2v2h-2v-2Zm0 3h2v2h-2v-2Z"/>`,
      store: `<path d="M7 6h14l-2 14H9L7 6Zm2-4h10l1 4H8l1-4Zm3 9h2v2h-2v-2Zm0 4h2v2h-2v-2Z"/>`,
      myapps: `<path d="M4 4h7v7H4V4Zm9 0h7v7h-7V4ZM4 13h7v7H4v-7Zm9 0h7v7h-7v-7Z"/>`,
      settings: `<path d="M19.4 13a7.8 7.8 0 0 0 0-2l2-1.5-2-3.5-2.3 1a7.5 7.5 0 0 0-1.7-1l-.3-2.5h-4l-.3 2.5a7.5 7.5 0 0 0-1.7 1l-2.3-1-2 3.5L4.6 11a7.8 7.8 0 0 0 0 2L2.6 14.5l2 3.5 2.3-1a7.5 7.5 0 0 0 1.7 1l.3 2.5h4l.3-2.5a7.5 7.5 0 0 0 1.7-1l2.3 1 2-3.5L19.4 13ZM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7Z"/>`,
      notes: `<path d="M6 2h9l3 3v15a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm8 1.5V6h2.5L14 3.5ZM7 9h10v2H7V9Zm0 4h10v2H7v-2Zm0 4h7v2H7v-2Z"/>`,
      about: `<path d="M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z"/>`
    }[appId] || `<path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z"/>`;

    const femmeBack = `<path d="M8.2 20c3.6 0 6.5-2.4 6.5-5.4 0-2-1.3-3.4-2.3-4.7-.7-.9-1.2-1.8-.9-2.9.4-1.7 2.2-2.6 2.2-4.3 0-1.6-1.5-2.8-3.4-2.8-2.2 0-4.1 1.4-4.3 3.3-.2 1.6.9 2.7 1.4 3.7.6 1.2.2 2.2-.6 3.4-1.2 1.7-2.6 3.3-2.6 5.3 0 2.9 1.8 4.4 4 4.4Z" fill="rgba(255,255,255,.10)"/>`;
    const minimalBack = `<circle cx="12" cy="12" r="9" fill="rgba(0,0,0,.18)"/>`;
    const neonBack = `<circle cx="12" cy="12" r="9" fill="rgba(255,255,255,.06)"/>`;
    const back = (pack === "femme") ? femmeBack : (pack === "minimal") ? minimalBack : neonBack;

    return `<svg viewBox="0 0 24 24" fill="rgba(255,255,255,.92)" aria-hidden="true">${back}${base}</svg>`;
  }

  const APPS = {
    browser: { title:"Browser", badge:"Custom logo + iframe", open: openBrowser },
    music: { title:"Music Player", badge:"Local audio playlist", open: openMusic },
    video: { title:"Video Player", badge:"Local video playback", open: openVideo },
    calculator: { title:"Calculator", badge:"Big numbers talk", open: openCalculator },
    store: { title:"App Store", badge:"Install Flatpaks (localhost)", open: openStore },
    myapps: { title:"My Apps", badge:"Launch installed Flatpaks", open: openMyApps },
    settings: { title:"Settings", badge:"Theme + sound + bridge", open: openSettings },
    notes: { title:"Notes", badge:"Local notes", open: openNotes },
    about: { title:"About", badge:"Readme", open: openAbout }
  };

  // Window manager
  let zTop = 50;
  const wins = new Map();

  function openApp(appId, opts={}){
    const def = APPS[appId];
    if (!def) return;

    const id = "win_" + Math.random().toString(16).slice(2);
    const w = document.createElement("div");
    w.className = "win";
    w.style.left = (opts.left ?? (90 + Math.random()*120)) + "px";
    w.style.top  = (opts.top  ?? (80 + Math.random()*90)) + "px";
    w.style.width  = (opts.width ?? 760) + "px";
    w.style.height = (opts.height ?? 520) + "px";
    w.style.zIndex = (++zTop).toString();

    const titlebar = document.createElement("div");
    titlebar.className = "titlebar";

    const title = document.createElement("div");
    title.className = "wintitle";
    title.innerHTML = `<span class="tag">${escapeHtml(ICONS[appId]?.tag || appId.toUpperCase())}</span><span>${escapeHtml(def.title)}</span>`;

    const btns = document.createElement("div");
    btns.className = "winbtns";
    const bMin = mkBtn("–", "Minimize");
    const bMax = mkBtn("□", "Maximize");
    const bX   = mkBtn("×", "Close");
    btns.append(bMin,bMax,bX);

    titlebar.append(title, btns);

    const content = document.createElement("div");
    content.className = "content";

    const resizer = document.createElement("div");
    resizer.className = "resizer";

    w.append(titlebar, content, resizer);
    windowsRoot.appendChild(w);

    const task = document.createElement("div");
    task.className = "task active";
    task.innerHTML = `<span class="dot"></span><span>${escapeHtml(def.title)}</span>`;
    tasksEl.appendChild(task);

    const win = { id, appId, el:w, content, taskEl:task, minimized:false, maximized:false, restoreRect:null };
    wins.set(id, win);

    focusWindow(id);

    bMin.onclick = () => minimizeWindow(id);
    bMax.onclick = () => toggleMaximize(id);
    bX.onclick = () => closeWindow(id);
    task.onclick = () => { if (win.minimized) restoreWindow(id); focusWindow(id); };

    w.addEventListener("pointerdown", () => focusWindow(id));
    makeDraggable(win, titlebar);
    makeResizable(win, resizer);

    def.open({ id, content, opts, openApp, toast, speak, state, persist, applyTheme, renderDesktopIcons, installFlatpak, updateFlatpaks, bridgeStatus });
    return id;
  }

  function focusWindow(id){
    for (const [,w] of wins) w.taskEl.classList.remove("active");
    const win = wins.get(id);
    if (!win) return;
    win.el.style.zIndex = (++zTop).toString();
    win.taskEl.classList.add("active");
  }
  function minimizeWindow(id){
    const win = wins.get(id); if (!win) return;
    win.minimized = true;
    win.el.style.display = "none";
    win.taskEl.classList.remove("active");
  }
  function restoreWindow(id){
    const win = wins.get(id); if (!win) return;
    win.minimized = false;
    win.el.style.display = "flex";
    focusWindow(id);
  }
  function toggleMaximize(id){
    const win = wins.get(id); if (!win) return;
    if (!win.maximized){
      win.restoreRect = { left: win.el.style.left, top: win.el.style.top, width: win.el.style.width, height: win.el.style.height };
      win.maximized = true;
      win.el.classList.add("maximized");
    } else {
      win.maximized = false;
      win.el.classList.remove("maximized");
      if (win.restoreRect){
        win.el.style.left = win.restoreRect.left;
        win.el.style.top  = win.restoreRect.top;
        win.el.style.width = win.restoreRect.width;
        win.el.style.height= win.restoreRect.height;
      }
    }
    focusWindow(id);
  }
  function closeWindow(id){
    const win = wins.get(id); if (!win) return;
    win.el.remove();
    win.taskEl.remove();
    wins.delete(id);
  }
  function mkBtn(txt, aria){
    const b = document.createElement("button");
    b.className = "wbtn";
    b.type = "button";
    b.textContent = txt;
    b.setAttribute("aria-label", aria);
    return b;
  }
  function makeDraggable(win, handle){
    let startX=0, startY=0, startL=0, startT=0, dragging=false;

    handle.addEventListener("pointerdown", (e) => {
      if (e.target.closest(".wbtn")) return;
      dragging = true;
      focusWindow(win.id);
      handle.setPointerCapture(e.pointerId);
      startX = e.clientX; startY = e.clientY;
      startL = parseInt(win.el.style.left,10) || 0;
      startT = parseInt(win.el.style.top,10) || 0;
    });

    handle.addEventListener("pointermove", (e) => {
      if (!dragging || win.maximized) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      win.el.style.left = clamp(startL + dx, 0, window.innerWidth - 120) + "px";
      win.el.style.top  = clamp(startT + dy, 0, window.innerHeight - 140) + "px";
    });

    handle.addEventListener("pointerup", (e) => {
      dragging = false;
      try { handle.releasePointerCapture(e.pointerId); } catch {}
    });
  }
  function makeResizable(win, grip){
    let startX=0, startY=0, startW=0, startH=0, resizing=false;

    grip.addEventListener("pointerdown", (e) => {
      resizing = true;
      focusWindow(win.id);
      grip.setPointerCapture(e.pointerId);
      startX = e.clientX; startY = e.clientY;
      startW = parseInt(win.el.style.width,10) || 760;
      startH = parseInt(win.el.style.height,10) || 520;
      e.preventDefault();
    });

    grip.addEventListener("pointermove", (e) => {
      if (!resizing || win.maximized) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      win.el.style.width  = Math.max(340, startW + dx) + "px";
      win.el.style.height = Math.max(240, startH + dy) + "px";
    });

    grip.addEventListener("pointerup", (e) => {
      resizing = false;
      try { grip.releasePointerCapture(e.pointerId); } catch {}
    });
  }

  // Desktop icons
  function renderDesktopIcons(){
    iconsEl.innerHTML = "";
    const pinned = Array.isArray(state.settings.pinnedApps) ? state.settings.pinnedApps : [];
    for (const appId of pinned){
      const def = APPS[appId];
      if (!def) continue;

      const el = document.createElement("div");
      el.className = "icon";
      el.innerHTML = `
        <div class="glyph">${svgIcon(appId)}</div>
        <div class="meta">
          <div class="label">${escapeHtml(def.title)}</div>
          <div class="sub">${escapeHtml(def.badge)}</div>
        </div>
      `;
      el.ondblclick = () => openApp(appId);
      el.onclick = () => toast("Double-click to open: " + def.title);
      iconsEl.appendChild(el);
    }
  }
  renderDesktopIcons();

  // Start menu
  function renderStartMenu(filter=""){
    const q = String(filter||"").toLowerCase().trim();
    const list = Object.entries(APPS)
      .filter(([id,def]) => !q || id.includes(q) || def.title.toLowerCase().includes(q) || def.badge.toLowerCase().includes(q))
      .sort((a,b) => a[1].title.localeCompare(b[1].title));

    startMenu.innerHTML = `
      <div class="startTitle">
        <div class="name">MujerOS</div>
        <div class="ver">v${escapeHtml(VERSION)}</div>
      </div>
      <input class="startSearch" id="startSearch" placeholder="Search apps…" value="${escapeAttr(filter)}" />
      <div id="startList"></div>
      <div class="hr"></div>
      <div class="small">Ctrl+Space opens Start. ESC closes Start.</div>
    `;

    const listEl = startMenu.querySelector("#startList");
    for (const [id,def] of list){
      const btn = document.createElement("button");
      btn.className = "appBtn";
      btn.type = "button";
      btn.innerHTML = `
        <span class="tag">${escapeHtml(ICONS[id]?.tag || id.toUpperCase())}</span>
        <span>${escapeHtml(def.title)}</span>
        <span class="badge">${escapeHtml(def.badge)}</span>
      `;
      btn.onclick = () => { openApp(id); hideStart(); };
      listEl.appendChild(btn);
    }

    const search = startMenu.querySelector("#startSearch");
    search.oninput = () => renderStartMenu(search.value);
    setTimeout(() => search.focus(), 0);
  }

  function showStart(){ renderStartMenu(""); startMenu.classList.add("show"); startMenu.setAttribute("aria-hidden","false"); }
  function hideStart(){ startMenu.classList.remove("show"); startMenu.setAttribute("aria-hidden","true"); }
  function toggleStart(){ startMenu.classList.contains("show") ? hideStart() : showStart(); }
  startBtn.onclick = toggleStart;

  document.addEventListener("pointerdown", (e) => {
    if (!startMenu.classList.contains("show")) return;
    const inside = startMenu.contains(e.target) || startBtn.contains(e.target);
    if (!inside) hideStart();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") hideStart();
    if (e.ctrlKey && (e.code === "Space" || e.key === " ")){
      e.preventDefault();
      toggleStart();
    }
  });

  // Clock
  setInterval(() => {
    const d = new Date();
    const t = d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
    const dt = d.toLocaleDateString([], {year:"numeric", month:"2-digit", day:"2-digit"});
    clockEl.textContent = `${dt}  ${t}`;
  }, 500);

  // First boot: open settings/store so it's ready
  if (!state.__bootedOnce){
    state.__bootedOnce = true;
    persist();
    openApp("about", { width: 600, height: 380, left: 120, top: 90 });
    openApp("store", { width: 980, height: 640, left: 220, top: 120 });
    toast("Ready ✅ (Store can install Flatpaks on this machine)");
  }

  // ===================== APPS =====================
  function openAbout(ctx){
    const { content, openApp } = ctx;
    content.innerHTML = `
      <div class="pill" style="display:block">
        <div style="font-weight:900;font-size:18px;">MujerOS v${escapeHtml(VERSION)}</div>
        <div class="small">All-in-one: UI + Flatpak installer bridge on localhost.</div>
        <div class="hr"></div>
        <div class="small">
          • App Store → Install uses <span class="tag">flatpak --user</span> and asks you to confirm each install.<br>
          • Settings lets you change wallpaper, sound, and icons.
        </div>
      </div>
      <div class="hr"></div>
      <div class="row">
        <button class="btn primary" id="st">Open Store</button>
        <button class="btn" id="se">Open Settings</button>
        <button class="btn" id="br">Open Browser</button>
        <button class="btn" id="say">Say line</button>
      </div>
    `;
    content.querySelector("#st").onclick = () => openApp("store");
    content.querySelector("#se").onclick = () => openApp("settings");
    content.querySelector("#br").onclick = () => openApp("browser");
    content.querySelector("#say").onclick = () => sayTouchLine();
  }

  function openNotes(ctx){
    const { content } = ctx;
    const file = "notes.txt";
    content.innerHTML = `
      <div class="row">
        <span class="tag">LOCAL</span>
        <span class="pill" style="padding:8px 10px">${escapeHtml(file)}</span>
        <button class="btn primary" id="save">Save</button>
      </div>
      <div class="hr"></div>
      <textarea id="ta" spellcheck="false"></textarea>
      <div class="hr"></div>
      <div class="small">Saved locally in your browser.</div>
    `;
    const ta = content.querySelector("#ta");
    ta.value = state.notes[file] ?? "";
    content.querySelector("#save").onclick = () => {
      state.notes[file] = ta.value;
      persist();
      toast("Saved notes.");
    };
  }

  function openBrowser(ctx){
    const { content, opts } = ctx;
    const startUrl = (opts && opts.url) ? String(opts.url) : (state.settings.browserHome || "mujeros:home");

    content.innerHTML = `
      <div class="browserTop">
        <div class="logoChip" id="logoChip" title="Click for voice line">
          <div class="logoMark">${svgIcon("browser")}</div>
          <div class="logoText" id="logoText"></div>
        </div>

        <input class="urlBar" id="url" type="text" placeholder="Type a URL (example: https://wikipedia.org) or mujéros:home" />
        <button class="btn" id="go">Go</button>
        <button class="btn" id="home">Home</button>
        <button class="btn" id="newtab">Open in new tab</button>
        <button class="btn primary" id="say">Say line</button>
      </div>

      <div class="browserFrameWrap">
        <iframe class="browserFrame" id="frame" sandbox="allow-forms allow-scripts allow-popups allow-same-origin"></iframe>
      </div>

      <div class="hintBar">
        Some sites block embedding inside iframes. If it fails, click <b>Open in new tab</b>.
      </div>
    `;

    const logoText = content.querySelector("#logoText");
    const logoChip = content.querySelector("#logoChip");
    const url = content.querySelector("#url");
    const frame = content.querySelector("#frame");

    logoText.textContent = state.settings.browserLogoText || "MujerBrowser";

    function normalize(u){
      u = String(u || "").trim();
      if (!u) return "mujeros:home";
      if (u === "mujeros:home") return u;
      if (u.startsWith("http://") || u.startsWith("https://")) return u;
      return "https://" + u.replace(/^\/+/, "");
    }

    function homeDoc(){
      const accent = state.settings.accent || "#ff4da6";
      const accent2 = state.settings.accent2 || "#7c4dff";
      const logo = escapeHtml(state.settings.browserLogoText || "MujerBrowser");
      return `<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial;color:rgba(255,255,255,.92);
background: radial-gradient(900px 600px at 20% 20%, ${accent}33, transparent 60%),
radial-gradient(900px 600px at 80% 10%, ${accent2}2b, transparent 60%),
linear-gradient(160deg,#070714,#0a0a1f);height:100vh;display:flex;align-items:center;justify-content:center;}
.box{width:min(820px,92vw);border-radius:20px;border:1px solid rgba(255,255,255,.16);
background: rgba(255,255,255,.07);backdrop-filter: blur(10px);padding:18px;box-shadow: 0 24px 70px rgba(0,0,0,.55);}
h1{margin:0 0 8px 0; font-size:22px;}
p{margin:0 0 14px 0; color:rgba(255,255,255,.72); font-size:13px; line-height:1.45;}
.grid{display:grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap:10px;}
a{text-decoration:none;color:rgba(255,255,255,.92);border-radius:16px;border:1px solid rgba(255,255,255,.14);
background: rgba(0,0,0,.18);padding:12px;display:block;}
a:hover{background: rgba(0,0,0,.28);}
.tag{font-family: ui-monospace, Menlo, Consolas, monospace; font-size:11px; color:rgba(255,255,255,.75);}
.name{font-weight:800; margin-top:6px;}
</style></head>
<body><div class="box">
<h1>${logo} — Home</h1>
<p>Type a URL in the address bar. If a site blocks embedding, use “Open in new tab”.</p>
<div class="grid">
<a href="https://wikipedia.org" target="_blank"><div class="tag">INFO</div><div class="name">Wikipedia</div></a>
<a href="https://duckduckgo.com" target="_blank"><div class="tag">SEARCH</div><div class="name">DuckDuckGo</div></a>
<a href="https://github.com" target="_blank"><div class="tag">CODE</div><div class="name">GitHub</div></a>
<a href="https://flathub.org" target="_blank"><div class="tag">LINUX</div><div class="name">Flathub</div></a>
</div></div></body></html>`;
    }

    function loadToFrame(target){
      const t = String(target || "mujeros:home");
      url.value = t;

      if (t === "mujeros:home"){
        frame.removeAttribute("src");
        frame.srcdoc = homeDoc();
        toast("Loaded MujerOS home.");
        return;
      }

      const real = normalize(t);
      frame.removeAttribute("srcdoc");
      frame.src = real;
      toast("Loading: " + real);
    }

    content.querySelector("#go").onclick = () => loadToFrame(url.value);
    content.querySelector("#home").onclick = () => loadToFrame("mujeros:home");
    content.querySelector("#newtab").onclick = () => {
      const t = String(url.value || "mujeros:home");
      if (t === "mujeros:home") {
        const blob = new Blob([homeDoc()], {type:"text/html"});
        const u = URL.createObjectURL(blob);
        window.open(u, "_blank", "noopener,noreferrer");
        return;
      }
      window.open(normalize(t), "_blank", "noopener,noreferrer");
    };
    content.querySelector("#say").onclick = () => sayTouchLine();
    logoChip.onclick = () => sayTouchLine();
    url.addEventListener("keydown", (e)=>{ if (e.key === "Enter") loadToFrame(url.value); });
    loadToFrame(startUrl);
  }

  function openMusic(ctx){
    const { content } = ctx;
    let tracks = [];
    let cur = -1;
    let audioUrl = null;

    content.innerHTML = `
      <div class="row">
        <span class="tag">LOCAL</span>
        <input id="pick" type="file" accept="audio/*" multiple />
        <button class="btn" id="clear">Clear</button>
        <button class="btn primary" id="say">Say line</button>
        <div class="pill"><span class="tag">VOL</span><input id="vol" type="range" min="0" max="1" step="0.01" value="1" /></div>
      </div>
      <div class="hr"></div>
      <div class="mediaGrid">
        <audio id="player" controls style="width:100%"></audio>
        <div class="playlist" id="list"></div>
        <div class="row">
          <button class="btn" id="prev">⟵ Prev</button>
          <button class="btn primary" id="play">Play/Pause</button>
          <button class="btn" id="next">Next ⟶</button>
        </div>
        <div class="small">Pick local audio files. Playlist stays in this session.</div>
      </div>
    `;

    const pick = content.querySelector("#pick");
    const clear = content.querySelector("#clear");
    const say = content.querySelector("#say");
    const vol = content.querySelector("#vol");
    const player = content.querySelector("#player");
    const list = content.querySelector("#list");
    const prev = content.querySelector("#prev");
    const play = content.querySelector("#play");
    const next = content.querySelector("#next");

    function renderList(){
      list.innerHTML = "";
      tracks.forEach((t, i)=>{
        const row = document.createElement("div");
        row.className = "track" + (i===cur ? " active" : "");
        row.innerHTML = `<span class="tag">♪</span><span class="trackName">${escapeHtml(t.name)}</span><span class="tag">${Math.ceil(t.size/1024)}KB</span>`;
        row.onclick = ()=>loadIndex(i, true);
        list.appendChild(row);
      });
      if (!tracks.length) list.innerHTML = `<div class="small" style="padding:8px 10px">No tracks loaded.</div>`;
    }

    function loadIndex(i, autoplay){
      if (i<0 || i>=tracks.length) return;
      cur = i;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = URL.createObjectURL(tracks[cur]);
      player.src = audioUrl;
      player.load();
      player.volume = Number(vol.value || 1);
      if (autoplay) player.play().catch(()=>{});
      renderList();
      toast("Now playing: " + tracks[cur].name);
    }

    pick.onchange = () => {
      const files = Array.from(pick.files || []);
      if (!files.length) return;
      tracks = files;
      cur = 0;
      renderList();
      loadIndex(0, false);
    };
    clear.onclick = () => {
      tracks = [];
      cur = -1;
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = null;
      player.removeAttribute("src");
      renderList();
      toast("Cleared playlist.");
    };
    vol.oninput = () => player.volume = Number(vol.value || 1);
    prev.onclick = () => loadIndex(cur-1, true);
    next.onclick = () => loadIndex(cur+1, true);
    play.onclick = () => { player.paused ? player.play().catch(()=>{}) : player.pause(); };
    say.onclick = () => sayTouchLine();
    renderList();
  }

  function openVideo(ctx){
    const { content } = ctx;
    let vUrl = null;

    content.innerHTML = `
      <div class="row">
        <span class="tag">LOCAL</span>
        <input id="pick" type="file" accept="video/*" />
        <button class="btn" id="clear">Clear</button>
        <button class="btn primary" id="say">Say line</button>
      </div>
      <div class="hr"></div>
      <video id="v" controls style="width:100%; border-radius:18px; border:1px solid rgba(255,255,255,.12); background:rgba(0,0,0,.22)"></video>
      <div class="hr"></div>
      <div class="small">Pick a local video file. It plays inside this window.</div>
    `;

    const pick = content.querySelector("#pick");
    const clear = content.querySelector("#clear");
    const say = content.querySelector("#say");
    const v = content.querySelector("#v");

    pick.onchange = () => {
      const f = pick.files?.[0];
      if (!f) return;
      if (vUrl) URL.revokeObjectURL(vUrl);
      vUrl = URL.createObjectURL(f);
      v.src = vUrl;
      v.load();
      v.play().catch(()=>{});
      toast("Loaded video: " + f.name);
    };
    clear.onclick = () => {
      if (vUrl) URL.revokeObjectURL(vUrl);
      vUrl = null;
      v.removeAttribute("src");
      v.load();
      toast("Cleared video.");
    };
    say.onclick = () => sayTouchLine();
  }

  function openCalculator(ctx){
    const { content } = ctx;
    let expr = "";
    let val = "0";

    content.innerHTML = `
      <div class="calc">
        <div class="calcDisplay">
          <div class="calcExpr" id="expr"></div>
          <div class="calcVal" id="val">0</div>
        </div>
        <div class="calcKeys" id="keys"></div>
        <div class="small">Huge results trigger the “money line”.</div>
      </div>
    `;

    const exprEl = content.querySelector("#expr");
    const valEl  = content.querySelector("#val");
    const keysEl = content.querySelector("#keys");

    const keys = [
      {t:"C", cls:"danger", a:"C"},
      {t:"⌫", cls:"op", a:"BS"},
      {t:"(", cls:"op", a:"("},
      {t:")", cls:"op", a:")"},
      {t:"7", a:"7"},{t:"8", a:"8"},{t:"9", a:"9"},{t:"÷", cls:"op", a:"/"},
      {t:"4", a:"4"},{t:"5", a:"5"},{t:"6", a:"6"},{t:"×", cls:"op", a:"*"},
      {t:"1", a:"1"},{t:"2", a:"2"},{t:"3", a:"3"},{t:"−", cls:"op", a:"-"},
      {t:"0", a:"0"},{t:".", a:"."},{t:"=", cls:"eq", a:"="},{t:"+", cls:"op", a:"+"},
    ];

    function render(){ exprEl.textContent = expr; valEl.textContent = val; }

    function safeEval(expression){
      const cleaned = expression.replace(/\s+/g,"");
      if (!/^[0-9+\-*/().]*$/.test(cleaned)) throw new Error("Bad characters");
      if (!cleaned) return 0;
      const result = Function(`"use strict"; return (${cleaned});`)();
      if (typeof result !== "number" || !isFinite(result)) throw new Error("Invalid math");
      return result;
    }

    function press(a){
      if (a === "C"){ expr=""; val="0"; render(); return; }
      if (a === "BS"){ expr = expr.slice(0,-1); render(); return; }

      if (a === "="){
        try{
          const r = safeEval(expr);
          val = formatNumber(r);
          expr = String(r);
          render();
          if (Math.abs(r) >= 1_000_000){
            const line = state.settings.moneyLine || "That’s a lot of money!";
            speak(line);
            toast(line);
          }
        } catch { val = "Error"; render(); }
        return;
      }

      expr += a;
      try{ val = formatNumber(safeEval(expr)); } catch {}
      render();
    }

    keys.forEach(k=>{
      const b = document.createElement("div");
      b.className = "key" + (k.cls ? " " + k.cls : "");
      b.textContent = k.t;
      b.onclick = () => press(k.a);
      keysEl.appendChild(b);
    });

    render();
  }

  function openStore(ctx){
    const { content, openApp } = ctx;

    const linuxApps = [
      { name:"VLC", id:"org.videolan.VLC", site:"https://www.videolan.org/vlc/", flathub:"https://flathub.org/apps/org.videolan.VLC" },
      { name:"OBS Studio", id:"com.obsproject.Studio", site:"https://obsproject.com/", flathub:"https://flathub.org/apps/com.obsproject.Studio" },
      { name:"Wireshark", id:"org.wireshark.Wireshark", site:"https://www.wireshark.org/", flathub:"https://flathub.org/apps/org.wireshark.Wireshark" },
      { name:"GIMP", id:"org.gimp.GIMP", site:"https://www.gimp.org/", flathub:"https://flathub.org/apps/org.gimp.GIMP" },
      { name:"LibreOffice", id:"org.libreoffice.LibreOffice", site:"https://www.libreoffice.org/", flathub:"https://flathub.org/apps/org.libreoffice.LibreOffice" },
      { name:"VS Code", id:"com.visualstudio.code", site:"https://code.visualstudio.com/", flathub:"https://flathub.org/apps/com.visualstudio.code" }
    ];

    content.innerHTML = `
      <div class="pill" style="display:block">
        <div style="font-weight:900;font-size:16px">App Store</div>
        <div class="small">This Store installs Flatpaks on <span class="tag">this</span> machine (localhost).</div>
      </div>

      <div class="hr"></div>

      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Installer status</div>
        <div class="row">
          <button class="btn" id="test">Test</button>
          <button class="btn primary" id="upd">Update Flatpaks</button>
          <button class="btn" id="settings">Settings</button>
          <button class="btn" id="myapps">My Apps</button>
        </div>
        <div class="small" id="status" style="margin-top:8px">Status: unknown</div>
      </div>

      <div class="hr"></div>

      <div style="font-weight:900; margin-bottom:8px;">Linux Apps (Flatpak / Flathub)</div>
      <div class="cards" id="cardsLinux"></div>

      <div class="hr"></div>
      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Last output</div>
        <div class="mono" id="log">(nothing yet)</div>
      </div>
    `;

    const statusEl = content.querySelector("#status");
    const logEl = content.querySelector("#log");
    const cardsLinux = content.querySelector("#cardsLinux");

    function log(txt){ logEl.textContent = String(txt || ""); }

    content.querySelector("#settings").onclick = () => openApp("settings");
    content.querySelector("#myapps").onclick = () => openApp("myapps");

    content.querySelector("#test").onclick = async () => {
      statusEl.textContent = "Status: testing…";
      try{
        const s = await bridgeStatus();
        statusEl.textContent = `Status: connected ✅ (flatpak=${s.flatpak}, flathub=${s.flathub})`;
        toast("Installer OK ✅");
      }catch(e){
        statusEl.textContent = "Status: NOT ready ❌ (" + (e?.message || e) + ")";
        toast("Installer not ready ❌");
      }
    };

    content.querySelector("#upd").onclick = async () => {
      toast("Update requested…");
      try{
        const r = await updateFlatpaks();
        toast("Update done ✅");
        log((r.stdout || "") + (r.stderr ? "\\n\\n[stderr]\\n" + r.stderr : ""));
      }catch(e){
        toast("Update failed ❌");
        log(String(e?.message || e));
      }
    };

    linuxApps.forEach(app=>{
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <h3>${escapeHtml(app.name)}</h3>
        <p class="small">App ID: <span class="tag">${escapeHtml(app.id)}</span></p>
        <div class="pill" style="display:block; margin-bottom:10px;">
          <div class="small" style="margin-bottom:6px;"><b>Command</b> (copy/paste):</div>
          <div class="mono">flatpak install flathub ${escapeHtml(app.id)}</div>
        </div>
        <div class="row">
          <button class="btn primary" data-act="install">Install</button>
          <button class="btn" data-act="launch">Launch</button>
          <button class="btn" data-act="flathub">Flathub</button>
          <button class="btn" data-act="site">Official</button>
        </div>
      `;

      card.querySelector('[data-act="install"]').onclick = async () => {
        toast("Install requested… " + app.id);
        try{
          const r = await installFlatpak(app.id);
          toast("Installed ✅ " + app.id);
          log((r.stdout || "") + (r.stderr ? "\\n\\n[stderr]\\n" + r.stderr : ""));
        }catch(e){
          toast("Install failed ❌");
          log(String(e?.message || e));
        }

      card.querySelector('[data-act="launch"]').onclick = async () => {
        toast("Launching… " + app.id);
        try{
          const r = await runFlatpak(app.id);
          toast("Launched ✅ " + app.id);
          log((r.stdout || "") + (r.stderr ? "\n\n[stderr]\n" + r.stderr : ""));
        }catch(e){
          toast("Launch failed ❌");
          log(String(e?.message || e));
        }
      };

      };

      card.querySelector('[data-act="flathub"]').onclick = () => window.open(app.flathub, "_blank", "noopener,noreferrer");
      card.querySelector('[data-act="site"]').onclick = () => window.open(app.site, "_blank", "noopener,noreferrer");

      cardsLinux.appendChild(card);
    });

    // Auto-test once
    content.querySelector("#test").click();
  }

  function openMyApps(ctx){
    const { content, openApp } = ctx;

    content.innerHTML = `
      <div class="pill" style="display:block">
        <div style="font-weight:900;font-size:16px">My Apps</div>
        <div class="small">Installed Flatpak apps on this machine. Click <b>Launch</b> to open.</div>
      </div>

      <div class="hr"></div>

      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Bridge</div>
        <div class="row">
          <button class="btn" id="refresh">Refresh list</button>
          <button class="btn primary" id="upd">Update Flatpaks</button>
          <button class="btn" id="store">Open Store</button>
          <button class="btn" id="test">Test</button>
        </div>
        <div class="small" id="status" style="margin-top:8px">Status: unknown</div>
      </div>

      <div class="hr"></div>

      <div class="row">
        <span class="tag">SEARCH</span>
        <input id="q" type="text" style="flex:1; min-width:240px" placeholder="Search installed apps (name or id)..." />
      </div>

      <div class="hr"></div>

      <div class="cards" id="apps"></div>

      <div class="hr"></div>
      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Last output</div>
        <div class="mono" id="log">(nothing yet)</div>
      </div>
    `;

    const statusEl = content.querySelector("#status");
    const logEl = content.querySelector("#log");
    const appsEl = content.querySelector("#apps");
    const qEl = content.querySelector("#q");

    function log(txt){ logEl.textContent = String(txt || ""); }

    content.querySelector("#store").onclick = () => openApp("store");

    let cached = [];

    async function test(){
      statusEl.textContent = "Status: testing…";
      try{
        const s = await bridgeStatus();
        statusEl.textContent = `Status: connected ✅ (flatpak=${s.flatpak}, flathub=${s.flathub})`;
        return true;
      }catch(e){
        statusEl.textContent = "Status: NOT ready ❌ (" + (e?.message || e) + ")";
        return false;
      }
    }

    function render(apps){
      const q = String(qEl.value || "").toLowerCase().trim();
      const filtered = apps.filter(a => {
        const id = String(a.id||"").toLowerCase();
        const name = String(a.name||"").toLowerCase();
        return !q || id.includes(q) || name.includes(q);
      });

      appsEl.innerHTML = "";
      if (!filtered.length){
        appsEl.innerHTML = `<div class="small">No apps found.</div>`;
        return;
      }

      filtered.forEach(a=>{
        const id = a.id || "";
        const name = a.name || id;
        const ver = a.version || "";
        const branch = a.branch || "";
        const origin = a.origin || "";
        const inst = a.installation || "";

        const flathubUrl = "https://flathub.org/apps/" + encodeURIComponent(id);

        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `
          <h3>${escapeHtml(name)}</h3>
          <p class="small">ID: <span class="tag">${escapeHtml(id)}</span></p>
          <p class="small">Version: ${escapeHtml(ver)} ${branch ? "(" + escapeHtml(branch) + ")" : ""}</p>
          <p class="small">Origin: ${escapeHtml(origin)} ${inst ? "• " + escapeHtml(inst) : ""}</p>
          <div class="row">
            <button class="btn primary" data-act="launch">Launch</button>
            <button class="btn" data-act="copy">Copy ID</button>
            <button class="btn" data-act="flathub">Flathub</button>
          </div>
        `;

        card.querySelector('[data-act="launch"]').onclick = async () => {
          toast("Launching… " + id);
          try{
            const r = await runFlatpak(id);
            toast("Launched ✅ " + id);
            log((r.stdout || "") + (r.stderr ? "\\n\\n[stderr]\\n" + r.stderr : ""));
          }catch(e){
            toast("Launch failed ❌");
            log(String(e?.message || e));
          }
        };

        card.querySelector('[data-act="copy"]').onclick = async () => {
          await copyText(id);
          toast("Copied ID");
        };

        card.querySelector('[data-act="flathub"]').onclick = () => window.open(flathubUrl, "_blank", "noopener,noreferrer");

        appsEl.appendChild(card);
      });
    }

    async function refresh(){
      appsEl.innerHTML = `<div class="small">Loading…</div>`;
      log("");
      const ok = await test();
      if (!ok){
        appsEl.innerHTML = `<div class="small">Installer bridge not ready. Keep the Python terminal open, then refresh.</div>`;
        return;
      }

      try{
        const res = await listFlatpaks(); // { ok, apps }
        cached = Array.isArray(res.apps) ? res.apps : [];
        render(cached);
      }catch(e){
        appsEl.innerHTML = `<div class="small">Failed to list apps: ${escapeHtml(e?.message || e)}</div>`;
      }
    }

    content.querySelector("#test").onclick = async () => {
      const ok = await test();
      toast(ok ? "Installer OK ✅" : "Installer not ready ❌");
    };
    content.querySelector("#refresh").onclick = refresh;

    content.querySelector("#upd").onclick = async () => {
      toast("Update requested…");
      try{
        const r = await updateFlatpaks();
        toast("Update done ✅");
        log((r.stdout || "") + (r.stderr ? "\\n\\n[stderr]\\n" + r.stderr : ""));
      }catch(e){
        toast("Update failed ❌");
        log(String(e?.message || e));
      }
    };

    qEl.oninput = () => render(cached);

    // initial load
    refresh();
  }

  function openSettings(ctx){
    const { content, renderDesktopIcons } = ctx;

    content.innerHTML = `
      <div class="pill" style="display:block">
        <div style="font-weight:900;font-size:16px">Settings</div>
        <div class="small">Wallpaper • Icon theme • Voice • Custom icons/audio</div>
        <div class="hr"></div>
        <div class="small">Installer is built-in and locked to: <span class="tag">${escapeHtml(EMBED_BASE)}</span></div>
      </div>

      <div class="hr"></div>

      <div class="row">
        <div class="pill"><span class="tag">ACCENT</span><input id="accent" type="color" value="${escapeAttr(state.settings.accent)}" /></div>
        <div class="pill">
          <span class="tag">WALL MODE</span>
          <select id="mode"><option value="cover">cover</option><option value="contain">contain</option></select>
        </div>
        <div class="pill">
          <span class="tag">ICON THEME</span>
          <select id="iconTheme"><option value="femme">femme</option><option value="neon">neon</option><option value="minimal">minimal</option></select>
        </div>
        <button class="btn" id="resetTheme">Reset Theme</button>
      </div>

      <div class="hr"></div>

      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Wallpaper</div>
        <div class="row"><input id="wall" type="file" accept="image/*" /><button class="btn" id="clearWall">Clear</button></div>
      </div>

      <div class="hr"></div>

      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Sound / Voice</div>
        <div class="row">
          <label class="pill" style="gap:10px"><span class="tag">VOICE</span><input id="voiceOn" type="checkbox" ${state.settings.voiceEnabled ? "checked" : ""} /><span class="small">Enabled</span></label>
          <div class="pill"><span class="tag">RATE</span><input id="rate" type="range" min="0.5" max="2" step="0.1" value="${escapeAttr(state.settings.voiceRate)}" /></div>
          <div class="pill"><span class="tag">PITCH</span><input id="pitch" type="range" min="0" max="2" step="0.1" value="${escapeAttr(state.settings.voicePitch)}" /></div>
          <div class="pill"><span class="tag">VOL</span><input id="vol" type="range" min="0" max="1" step="0.05" value="${escapeAttr(state.settings.voiceVolume)}" /></div>
          <button class="btn primary" id="testTouch">Test touch line</button>
          <button class="btn" id="testMoney">Test money line</button>
        </div>

        <div class="hr"></div>

        <div class="row" style="align-items:flex-start">
          <div style="flex:1; min-width:260px">
            <div class="small" style="margin-bottom:6px"><b>Touch line</b></div>
            <input id="touchLine" type="text" style="width:100%" value="${escapeAttr(state.settings.touchLine)}" />
          </div>
          <div style="flex:1; min-width:260px">
            <div class="small" style="margin-bottom:6px"><b>Money line</b></div>
            <input id="moneyLine" type="text" style="width:100%" value="${escapeAttr(state.settings.moneyLine)}" />
          </div>
        </div>

        <div class="row" style="margin-top:10px">
          <button class="btn primary" id="saveLines">Save lines</button>
          <button class="btn" id="resetLines">Reset lines</button>
        </div>

        <div class="hr"></div>

        <div class="row">
          <label class="pill" style="gap:10px">
            <span class="tag">CUSTOM AUDIO</span>
            <input id="useAudio" type="checkbox" ${state.settings.useCustomAudio ? "checked" : ""} />
            <span class="small">Use uploaded audio</span>
          </label>
          <input id="audioFile" type="file" accept="audio/*" />
          <button class="btn" id="clearAudio">Clear audio</button>
        </div>
      </div>

      <div class="hr"></div>

      <div class="pill" style="display:block">
        <div style="font-weight:900;margin-bottom:6px;">Custom Icons (upload per app)</div>
        <div class="small" style="margin-bottom:10px">Upload PNG/JPG icons. Stored locally.</div>
        <div id="iconUploads"></div>
        <div class="row" style="margin-top:10px">
          <button class="btn" id="clearIcons">Clear all custom icons</button>
          <button class="btn primary" id="refreshDesktop">Refresh Desktop</button>
        </div>
      </div>

      <div class="hr"></div>
      <div class="row">
        <button class="btn danger" id="factoryReset">Factory Reset (clears all)</button>
      </div>
    `;

    const accent = content.querySelector("#accent");
    const wall = content.querySelector("#wall");
    const mode = content.querySelector("#mode");
    const iconTheme = content.querySelector("#iconTheme");

    mode.value = state.settings.wallpaperMode || "cover";
    iconTheme.value = state.settings.iconTheme || "femme";

    accent.oninput = () => { state.settings.accent = accent.value; applyTheme(); persist(); };
    mode.onchange = () => { state.settings.wallpaperMode = mode.value; applyWallpaper(); persist(); };
    iconTheme.onchange = () => { state.settings.iconTheme = iconTheme.value; renderDesktopIcons(); persist(); toast("Icon theme: " + iconTheme.value); };

    wall.onchange = async () => {
      const f = wall.files?.[0]; if (!f) return;
      state.settings.wallpaperDataUrl = await fileToDataUrl(f);
      applyWallpaper(); persist(); toast("Wallpaper set.");
    };
    content.querySelector("#clearWall").onclick = () => { state.settings.wallpaperDataUrl=""; applyWallpaper(); persist(); toast("Wallpaper cleared."); };

    content.querySelector("#resetTheme").onclick = () => {
      state.settings.accent="#ff4da6";
      state.settings.accent2="#7c4dff";
      state.settings.wallpaperMode="cover";
      state.settings.iconTheme="femme";
      applyTheme(); renderDesktopIcons(); persist(); toast("Theme reset.");
    };

    const voiceOn = content.querySelector("#voiceOn");
    const rate  = content.querySelector("#rate");
    const pitch = content.querySelector("#pitch");
    const vol   = content.querySelector("#vol");

    voiceOn.onchange = () => { state.settings.voiceEnabled = voiceOn.checked; persist(); };
    rate.oninput = () => { state.settings.voiceRate = Number(rate.value); persist(); };
    pitch.oninput = () => { state.settings.voicePitch = Number(pitch.value); persist(); };
    vol.oninput = () => { state.settings.voiceVolume = Number(vol.value); persist(); };

    content.querySelector("#testTouch").onclick = () => sayTouchLine();
    content.querySelector("#testMoney").onclick = () => { const line = state.settings.moneyLine || "That’s a lot of money!"; speak(line); toast(line); };

    content.querySelector("#saveLines").onclick = () => {
      state.settings.touchLine = content.querySelector("#touchLine").value.trim() || "Don’t touch me there, honey.";
      state.settings.moneyLine = content.querySelector("#moneyLine").value.trim() || "That’s a lot of money!";
      persist(); toast("Lines saved.");
    };
    content.querySelector("#resetLines").onclick = () => {
      state.settings.touchLine = "Don’t touch me there, honey.";
      state.settings.moneyLine = "That’s a lot of money!";
      content.querySelector("#touchLine").value = state.settings.touchLine;
      content.querySelector("#moneyLine").value = state.settings.moneyLine;
      persist(); toast("Lines reset.");
    };

    const useAudio = content.querySelector("#useAudio");
    const audioFile = content.querySelector("#audioFile");

    useAudio.onchange = () => { state.settings.useCustomAudio = useAudio.checked; persist(); };

    audioFile.onchange = async () => {
      const f = audioFile.files?.[0]; if (!f) return;
      state.settings.customAudioDataUrl = await fileToDataUrl(f);
      state.settings.useCustomAudio = true;
      useAudio.checked = true;
      persist();
      toast("Custom audio uploaded.");
    };
    content.querySelector("#clearAudio").onclick = () => {
      state.settings.customAudioDataUrl = "";
      state.settings.useCustomAudio = false;
      useAudio.checked = false;
      persist();
      toast("Custom audio cleared.");
    };

    // Custom icons
    const uploads = content.querySelector("#iconUploads");
    uploads.innerHTML = "";
    for (const appId of Object.keys(APPS)){
      const row = document.createElement("div");
      row.className = "row";
      row.style.marginBottom = "10px";
      row.innerHTML = `
        <span class="tag">${escapeHtml(APPS[appId].title)}</span>
        <input type="file" accept="image/*" data-app="${escapeAttr(appId)}" />
        <button class="btn" data-clear="${escapeAttr(appId)}">Clear</button>
      `;
      const input = row.querySelector('input[type="file"]');
      input.onchange = async () => {
        const f = input.files?.[0]; if (!f) return;
        state.customIcons[appId] = await fileToDataUrl(f);
        persist(); renderDesktopIcons(); toast("Custom icon set: " + APPS[appId].title);
      };
      row.querySelector('button[data-clear]').onclick = () => {
        delete state.customIcons[appId];
        persist(); renderDesktopIcons(); toast("Custom icon cleared: " + APPS[appId].title);
      };
      uploads.appendChild(row);
    }

    content.querySelector("#clearIcons").onclick = () => { state.customIcons = {}; persist(); renderDesktopIcons(); toast("All custom icons cleared."); };
    content.querySelector("#refreshDesktop").onclick = () => { renderDesktopIcons(); toast("Desktop refreshed."); };

    content.querySelector("#factoryReset").onclick = () => {
      if (!confirm("This clears wallpaper, icons, audio, settings, notes — everything. Continue?")) return;
      localStorage.removeItem(STORAGE_KEY);
      location.reload();
    };
  }

  // Utilities
  function clamp(n, a, b){ return Math.max(a, Math.min(b, n)); }
  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, ch => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[ch]));
  }
  function escapeAttr(s){ return escapeHtml(s).replace(/"/g,"&quot;"); }
  function formatNumber(n){
    if (!isFinite(n)) return "Error";
    const abs = Math.abs(n);
    if (abs >= 1e12) return n.toExponential(6);
    if (abs >= 1e6) return n.toLocaleString(undefined, {maximumFractionDigits: 6});
    return String(Number(n.toFixed(10))).replace(/\.0+$/,"").replace(/(\.\d*?)0+$/,"$1");
  }

  async function copyText(t){
    try{
      await navigator.clipboard.writeText(String(t));
    }catch{
      const ta = document.createElement("textarea");
      ta.value = String(t);
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
  }

  function fileToDataUrl(file){
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result));
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
  }
})();
</script>
</body>
</html>
"""

def pick_port() -> int:
    # Try to bind to 8765; if taken, use an ephemeral port.
    preferred = 8765
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

class MujerOSHandler(BaseHTTPRequestHandler):
    server_version = "MujerOSBridge/1.0"

    def log_message(self, format, *args):
        # quiet (comment this out if you want logs)
        return

    def _send_json(self, code: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = self.server.rendered_html  # type: ignore
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/status":
            self._send_json(200, {
                "ok": True,
                "flatpak": has_flatpak(),
                "flathub": flathub_configured(),
                "version": "all-in-one"
            })
            return

        if path == "/flatpak/list":
            token = self.headers.get("X-Installer-Token", "")
            if token != self.server.token:  # type: ignore
                self._send_json(401, {"ok": False, "error": "Bad token"})
                return

            if not has_flatpak():
                self._send_json(500, {"ok": False, "error": "flatpak not installed"})
                return

            try:
                apps = list_flatpak_apps()
                self._send_json(200, {"ok": True, "apps": apps})
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)})
            return

        self._send_json(404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        token = self.headers.get("X-Installer-Token", "")
        if token != self.server.token:  # type: ignore
            self._send_json(401, {"ok": False, "error": "Bad token"})
            return

        if path == "/install":
            payload = self._read_json()
            app_id = str(payload.get("appId", "")).strip()
            if not APPID_RE.match(app_id):
                self._send_json(400, {"ok": False, "error": "Invalid appId"})
                return

            if not has_flatpak():
                self._send_json(500, {"ok": False, "error": "flatpak not installed"})
                return

            ensure_flathub_user()

            if not gui_confirm("MujerOS Installer", f"Install Flatpak (user):\n\n{app_id}\n\nRemote: flathub"):
                self._send_json(200, {"ok": False, "error": "User cancelled"})
                return

            code, out, err = run_cmd(["flatpak", "--user", "install", "-y", "flathub", app_id])
            self._send_json(200 if code == 0 else 500, {
                "ok": code == 0,
                "appId": app_id,
                "stdout": out,
                "stderr": err
            })
            return

        if path == "/update":
            if not has_flatpak():
                self._send_json(500, {"ok": False, "error": "flatpak not installed"})
                return

            ensure_flathub_user()

            if not gui_confirm("MujerOS Installer", "Update ALL user Flatpaks now?"):
                self._send_json(200, {"ok": False, "error": "User cancelled"})
                return

            code, out, err = run_cmd(["flatpak", "--user", "update", "-y"])
            self._send_json(200 if code == 0 else 500, {
                "ok": code == 0,
                "stdout": out,
                "stderr": err
            })
            return


        if path == "/flatpak/run":
            payload = self._read_json()
            app_id = str(payload.get("appId", "")).strip()
            if not APPID_RE.match(app_id):
                self._send_json(400, {"ok": False, "error": "Invalid appId"})
                return

            if not has_flatpak():
                self._send_json(500, {"ok": False, "error": "flatpak not installed"})
                return

            if not is_flatpak_installed(app_id):
                self._send_json(400, {"ok": False, "error": "App not installed"})
                return

            ok, err = launch_flatpak(app_id)
            if ok:
                self._send_json(200, {"ok": True, "appId": app_id})
            else:
                self._send_json(500, {"ok": False, "error": err or "Failed to launch"})
            return
        self._send_json(404, {"ok": False, "error": "Not found"})

def main():
    version = "3.3-allinone"
    token = secrets.token_urlsafe(24)
    port = pick_port()
    base = f"http://127.0.0.1:{port}"

    rendered_html = (HTML_TEMPLATE
        .replace("__VERSION__", version)
        .replace("__TOKEN__", token)
        .replace("__BASE__", base)
    )

    httpd = ThreadingHTTPServer(("127.0.0.1", port), MujerOSHandler)
    httpd.token = token  # type: ignore
    httpd.rendered_html = rendered_html  # type: ignore

    # Warm up flathub (best effort)
    if has_flatpak():
        ensure_flathub_user()

    print("\n=== MujerOS All-in-One ===")
    print("UI + Flatpak installer bridge (localhost)")
    print(f"URL:   {base}")
    print(f"Token: {token} (auto-injected into UI)")
    if not has_flatpak():
        print("\nNOTE: flatpak is not installed; Store install buttons will fail.")
        print("Arch:   sudo pacman -S flatpak")
        print("Ubuntu: sudo apt install flatpak")
    print("\nClose this terminal to stop MujerOS.\n")

    # Auto-open browser
    try:
        webbrowser.open(base, new=1, autoraise=True)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main()