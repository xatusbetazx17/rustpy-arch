# NovaOS & RustPy‑Arch — Monorepo

NovaOS is a single‑file WebOS that runs entirely in the browser with a full window manager, apps (Browser, File Explorer, Code Editor, Terminal with Python, Paint, Video/Audio, Notes, Image Viewer, Calculator, Snake game) and a persistent virtual file system.

RustPy‑Arch is an Arch‑based customization script and docs to set up a Linux system that mixes Rust tools and Python (GTK) utilities, including an optional custom kernel build and a small desktop layer.

## 🚀 Quick Start (NovaOS)
Open `novaos/index.html` directly in any modern browser (Chrome/Edge/Firefox/Safari).
Mobile works too — the window manager adapts to small screens.
Use the Start button to launch apps; taskbar shows running windows.
Data you save via the File Explorer persists in the browser’s storage (per origin).

Tip: host the `novaos/` folder with any static server and open `index.html`.
Example (Python 3):
```bash
python -m http.server -d novaos 8080
```
then visit http://localhost:8080

## 🕹️ Steam Deck Quick Steps (Full pacman + LibreOffice)

**Get Agent** → you’ll receive `nova_agent.py` and `nova-agent.service`.

**On the Deck (Desktop Mode):**
```bash
sudo pacman -S python python-pip podman
pip install "uvicorn[standard]" fastapi
python ~/nova_agent.py
# Optional security:
# NOVA_AGENT_TOKEN=changeme python ~/nova_agent.py
```

**In NovaOS → Terminal Pro MAX:**
- Engine = **Arch Container (pacman)** → **Connect**
- Use **Quick pacman** → “LibreOffice (fresh)”, or type your own `pacman` commands
- Use **Upload → /root** to drop configs/files into the container home

**Auto‑start on boot (user service):**
```bash
mkdir -p ~/.config/systemd/user
cp ~/nova-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nova-agent.service
```

### GUI apps from inside your Web‑OS (LibreOffice, etc.)
There’s a pinned **Arch Desktop (noVNC)** tile (client). For a browser‑based desktop:

**Fast path:**
```bash
podman run -d --name webtop -p 3000:3000 ghcr.io/linuxserver/webtop:arch-xfce
```

In NovaOS → **Web Browser** → open `http://localhost:3000` (built‑in noVNC).

Or use the **Arch Desktop (noVNC)** app to connect to your own VNC server (`host:port/path`).

## New file added if you wan to try the store now work with bridge need a main linux machine but can launch and install apps now need giv epermission and execut eit on terminal.

Give permision to this file MujerOS_AllInOne_v3_3.py with this command  chmod +x MujerOS_AllInOne_v3_3.py ,and them open it on the terminal with this command. ./MujerOS_AllInOne_v3_3.py be warned the computer can be little slow when this happends but will works as charm in working on this.


## 🧠 Highlights
- Pro window manager: drag, resize (8 handles), Alt‑Tab, snap (halves/quarters), minimize, maximize, multi‑desktop, context menus, spotlight search, and screenshot tool.
- Rich built‑in apps: code editor (Ace), notepad, terminal (with Python via Pyodide), paint, video editor (trim/merge basics), image viewer, calculator, music player, and a simple game.
- Ultra/Hyper/Pro variants are included; UltraPlus is mapped to `index.html` by default.
- Persistent virtual file system (localStorage) with folders like Documents/Pictures/Music.
- Theming (Aurora, Sunset, Emerald, Noir), notifications, widgets, and keyboard shortcuts.

> Feature set mirrors the current HTML build shipped in `novaos/`. See the About/Info in the running OS for details.

## 📂 Repository Layout
```text
NovaOS-monorepo/
├─ README.md
├─ LICENSE
├─ novaos/
│  ├─ index.html                # UltraPlus mapped for GitHub Pages/live demo
│  ├─ NovaOS_UltraPlus.html     # Other builds also kept
│  ├─ NovaOS_Ultra.html
│  ├─ NovaOS_Hyper.html
│  └─ NovaOS_Pro_Windowing.html
├─ distro/
│  └─ rustpy-arch/
│     ├─ README.md
│     └─ rustpy-arch-bootstrap.sh
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ INSTALL.md
│  ├─ WORKFLOWS.md
│  └─ STEAM_DECK_QUICK_START.md
├─ .github/
│  └─ ISSUE_TEMPLATE/
│     ├─ bug_report.md
│     └─ feature_request.md
├─ .gitignore
├─ CONTRIBUTING.md
├─ CODE_OF_CONDUCT.md
├─ SECURITY.md
├─ ROADMAP.md
└─ CHANGELOG.md
```

## 🔧 Run a Local Dev Server
Any static server will work. Two examples:

```bash
# Python
python -m http.server -d novaos 8080

# Node (if you have it)
npx serve novaos
```

## ⚠️ Known Limitations
- Runs inside the browser sandbox: no direct Wi‑Fi device control, no raw filesystem access, no native EXE/ELF execution.
- DOS apps are possible via web emulators; modern Win32/Posix binaries are not.
- Networking inside the embedded terminal is limited by CORS and the browser environment.
- Storage is per‑browser and per‑origin; clearing site data resets the virtual FS.

## 📦 RustPy‑Arch (Linux side)
See `distro/rustpy-arch/README.md` for full details and the bootstrap script.
The script can install Rust‑centric tools, Python GTK utilities, and optionally build a custom kernel for your hardware using Arch sources.

## 📝 License
This repository ships with the original LICENSE if provided. If not, consider using MIT.

_Generated on 2025-10-18_
