# Architecture (High Level)

NovaOS is a single-file WebOS. Each edition bundles:
- **Window Manager** (drag, resize, maximize/minimize, snap, Alt-Tab)
- **Taskbar/Start Menu** with Spotlight-like search
- **Apps** (Editor, Code, Terminal (Pyodide), Paint, Video, Music, Image, Notes, Calculator, Game)
- **Virtual File System** stored in `localStorage`

RustPy‑Arch is a separate Linux-side bootstrap that configures an Arch base with Rust tools and Python GTK utilities.
