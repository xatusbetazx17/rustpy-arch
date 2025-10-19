# NovaOS & RustPy‑Arch — Monorepo

**NovaOS** is a single‑file WebOS that runs entirely in the browser with a full window manager, apps (Browser, File Explorer, Code Editor, Terminal with Python, Paint, Video/Audio, Notes, Image Viewer, Calculator, Snake game) and a persistent virtual file system.

**RustPy‑Arch** is an Arch‑based customization script and docs to set up a Linux system that mixes Rust tools and Python (GTK) utilities, including an optional custom kernel build and a small desktop layer.

## 🚀 Quick Start (NovaOS)
1. Open **`novaos/index.html`** directly in any modern browser (Chrome/Edge/Firefox/Safari).  
   - Mobile works too — the window manager adapts to small screens.
2. Use the **Start** button to launch apps; taskbar shows running windows.
3. Data you save via the File Explorer persists in the browser’s storage (per origin).

> Tip: host the `novaos/` folder with any static server and open `index.html`.  
> Example (Python 3): `python -m http.server -d novaos 8080` then visit http://localhost:8080

## 🧠 Highlights
- Pro window manager: drag, resize (8 handles), Alt‑Tab, snap (halves/quarters), minimize, maximize, multi‑desktop, context menus, spotlight search, and screenshot tool.
- Rich built‑in apps: code editor (Ace), notepad, terminal (with Python via Pyodide), paint, video editor (trim/merge basics), image viewer, calculator, music player, and a simple game.
- **Ultra/Hyper/Pro variants** are included; `UltraPlus` is mapped to `index.html` by default.
- Persistent virtual file system (localStorage) with folders like Documents/Pictures/Music.
- Theming (Aurora, Sunset, Emerald, Noir), notifications, widgets, and keyboard shortcuts.

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
│  └─ WORKFLOWS.md
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

## 🌐 Publish to GitHub Pages
1. Create a new repo on GitHub (e.g., `novaos`).
2. Initialize and push:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: NovaOS + RustPy-Arch monorepo"
   git branch -M main
   git remote add origin <YOUR_GITHUB_REPO_URL>
   git push -u origin main
   ```
3. In GitHub → **Settings → Pages**: Source = **Deploy from a branch**, Branch = **`main`**, Folder = **`/novaos`**.  
   Your site will serve `novaos/index.html`.

## 🗃 Git Workflow (Gitflow‑style)
- Long‑lived branches: `main` (stable) and `develop` (integration).  
- Short‑lived branches: `feature/*`, `release/*`, `hotfix/*`.
- Example:
  ```bash
  # New feature
  git checkout -b feature/window-shadows develop
  git commit -m "wm: add drop-shadow animation"
  git push -u origin feature/window-shadows

  # Finish feature
  git checkout develop && git merge --no-ff feature/window-shadows
  git branch -d feature/window-shadows

  # Prepare release
  git checkout -b release/1.0.0 develop
  # bump versions, docs, changelog
  git commit -m "chore(release): 1.0.0"
  git checkout main && git merge --no-ff release/1.0.0
  git tag -a v1.0.0 -m "NovaOS 1.0.0"
  git checkout develop && git merge --no-ff release/1.0.0
  git push --follow-tags

  # Hotfix on production
  git checkout -b hotfix/1.0.1 main
  # fixes...
  git commit -m "fix: crash on maximize"
  git checkout main && git merge --no-ff hotfix/1.0.1
  git tag -a v1.0.1 -m "Hotfix"
  git checkout develop && git merge --no-ff hotfix/1.0.1
  git push --follow-tags
  ```

## ⚠️ Known Limitations
- Runs inside the browser sandbox: **no direct Wi‑Fi device control, no raw filesystem access, no native EXE/ELF execution**. DOS apps are possible via web emulators; modern Win32/Posix binaries are not.
- Networking inside the embedded terminal is limited by CORS and the browser environment.
- Storage is per‑browser and per‑origin; clearing site data resets the virtual FS.

## 📦 RustPy‑Arch (Linux side)
See `distro/rustpy-arch/README.md` for full details and the bootstrap script.  
The script can install Rust‑centric tools, Python GTK utilities, and optionally build a custom kernel for your hardware using Arch sources.

## 📝 License
This repository ships with the original LICENSE if provided. If not, consider using MIT.

---
_Generated on 2025-10-18_
