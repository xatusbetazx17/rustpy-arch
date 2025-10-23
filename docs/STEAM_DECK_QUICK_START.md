# Steam Deck Quick Start (pacman + LibreOffice)

These steps integrate NovaOS (browser UI) with an Arch container via the tiny `nova_agent.py` bridge.

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
