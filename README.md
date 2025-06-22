# rustpy-arch

A custom Arch‐based distribution that uses:

- A **Rust‐based init** (`initrs`) as PID 1 (replacing systemd).  
- **Rust coreutils** (uutils) and other Rust utilities wherever possible.  
- **Python** scripts for networking, installer GUI, and system services.  
- A **Btrfs‐based immutable root** with `/@`, `/@home`, and `/@var` subvolumes.  
- A lightweight **RustPyDE** desktop environment built primarily in Rust and Python.  
- A **graphical first‐boot installer** (`installer.py`) written in Python/GTK.  
- Meta‐packages for “Gaming,” “Office,” “Development,” and “Multimedia” profiles.

---
## 📥 Alternative Base Live Environments

To simplify installation, start with one of these Arch-based ISO images that provide a graphical installer:

- [EndeavourOS Minimal ISO](https://endeavouros.com)  
- [ArcoLinuxD ISO](https://arcolinux.info/downloads)  

## ⚙️ Install RustPy-Arch Script

Once your base system (EndeavourOS or ArcoLinux) is fully installed and you’ve booted into the new environment, open a terminal and run:

~~~
# Clone the RustPy-Arch repository
git clone https://github.com/xatusbetazx17/rustpy-arch.git
cd rustpy-arch

# Make the installer script executable and run it
chmod +x rustpy-arch-bootstrap.sh
./rustpy-arch-bootstrap.sh
~~~


## Repository Layout

```
rustpy-arch/
├── README.md ← (this file)
├── rustpy-arch-bootstrap.sh ← main bootstrap script
├── initrs/ ← Rust “init” (PID 1) project
│ ├── Cargo.toml
│ └── src/
│ └── main.rs
├── python-scripts/
│ ├── netconfig.py ← network‐config script
│ └── installer.py ← graphical installer GUI
├── rustpyde/
│ ├── panel.py ← top panel (GTK)
│ ├── network_tray.py ← network tray icon (GTK)
│ ├── volume_tray.py ← volume tray icon (GTK)
│ └── rustpyde-launcher ← simple launcher script
├── rustpy-de-core/
│ └── PKGBUILD ← meta‐package for the DE
├── rustpy-gaming/
│ └── PKGBUILD ← meta‐package for Gaming profile
├── rustpy-office/
│ └── PKGBUILD ← meta‐package for Office profile
├── rustpy-dev/
│ └── PKGBUILD ← meta‐package for Development profile
└── rustpy-multimedia/
└── PKGBUILD ← meta‐package for Multimedia profile
```


## 1. `rustpy-arch-bootstrap.sh`
~~~
#!/usr/bin/env python3
import os
import subprocess
import random
import gi
from pathlib import Path

# Ensure GTK 3 is loaded
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

# Pillow for wallpaper generation
from PIL import Image, ImageDraw

# Map XDG_CURRENT_DESKTOP to Arch DE package names
de_map = {
    'xfce': 'xfce4',
    'gnome': 'gnome',
    'kde': 'plasma-desktop',
    'lxqt': 'lxqt',
    'mate': 'mate',
    'cinnamon': 'cinnamon',
    'budgie': 'budgie-desktop',
}

# ----------------------- Helpers -----------------------
def run(cmd, check=True, cwd=None):
    if check:
        subprocess.run(cmd, check=True, cwd=cwd)
    else:
        subprocess.Popen(cmd, cwd=cwd)

def is_installed(pkg):
    return subprocess.run(['pacman','-Qi',pkg],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL).returncode == 0

def detect_gpu():
    out = subprocess.check_output(
        "lspci -nn | grep -Ei 'VGA'", shell=True
    ).decode().lower()
    if 'nvidia' in out:
        return 'nvidia'
    if 'amd' in out:
        return 'xf86-video-amdgpu'
    if 'intel' in out:
        return 'mesa'
    return None

# Generate a random gradient wallpaper
WALL_DIR = Path.home() / "Pictures" / "Wallpapers"
WALL_DIR.mkdir(parents=True, exist_ok=True)

def generate_wallpaper(path: Path, size=(1920,1080)):
    # create random two-color vertical gradient
    base = Image.new('RGB', size)
    draw = ImageDraw.Draw(base)
    c1 = tuple(random.randint(0,255) for _ in range(3))
    c2 = tuple(random.randint(0,255) for _ in range(3))
    for y in range(size[1]):
        ratio = y / size[1]
        r = int(c1[0] * (1-ratio) + c2[0] * ratio)
        g = int(c1[1] * (1-ratio) + c2[1] * ratio)
        b = int(c1[2] * (1-ratio) + c2[2] * ratio)
        draw.line([(0,y),(size[0],y)], fill=(r,g,b))
    base.save(path)
    return path

# ----------------------- GUI -----------------------
class InstallerGUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Installer")
        self.set_default_size(700, 500)
        self.set_border_width(12)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # Notebook for pages
        self.nb = Gtk.Notebook()
        vbox.pack_start(self.nb, True, True, 0)
        self._build_network_page()
        self._build_disk_page()
        self._build_components_page()
        self._build_graphics_page()
        self._build_theme_page()

        # Start button
        btn = Gtk.Button(label="Start Installation")
        btn.connect("clicked", lambda w: self.on_start())
        vbox.pack_start(btn, False, False, 0)

        self.show_all()

    def _build_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Network"))
        # Mirror + Wi-Fi scanning omitted for brevity
        # ...

    def _build_disk_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Disk Layout"))
        # Disk partition size spinners
        # ...

    def _build_components_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Components"))
        self.ck = {}
        comps = {
            'rust':            'Rust compiler',
            'git':             'Git',
            'base':            'Base system',
            'rustpy-de-core':  'RustPyDE desktop',
            'rustpy-gaming':   'Gaming profile',
            'rustpy-office':   'Office profile',
            'rustpy-dev':      'Development tools',
            'rustpy-multimedia':'Multimedia suite',
        }
        for pkg,label in comps.items():
            cb = Gtk.CheckButton(label=label)
            if is_installed(pkg):
                cb.set_sensitive(False)
                cb.set_label(f"{label} (already installed)")
            self.ck[pkg] = cb
            page.pack_start(cb, False, False, 0)

    def _build_graphics_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Graphics"))
        gpu = detect_gpu()
        self.cb_gpu = Gtk.CheckButton(
            label=(f"Install {gpu} driver" if gpu else "No GPU detected")
        )
        if not gpu: self.cb_gpu.set_sensitive(False)
        page.pack_start(self.cb_gpu, False, False, 0)

    def _build_theme_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Theme"))

        lbl = Gtk.Label(label="Generate random wallpaper and icon theme?")
        page.pack_start(lbl, False, False, 0)
        btn = Gtk.Button(label="Preview & Generate")
        btn.connect("clicked", lambda w: self._on_generate_theme())
        page.pack_start(btn, False, False, 0)
        self.theme_path = None

    def _on_generate_theme(self):
        # Create a random wallpaper
        fname = WALL_DIR / f"rustpy_wall_{random.randint(1,9999)}.png"
        path = generate_wallpaper(fname)
        self.theme_path = path
        self._message(f"Wallpaper generated at {path}")

    def on_start(self):
        base_dir = Path(__file__).parent
        # 1) gather components
        selected = [p for p,cb in self.ck.items() if cb.get_active()]
        if self.cb_gpu.get_active():
            g = detect_gpu()
            if g: selected.append(g)
        # 2) install official
        official = [p for p in selected if not p.startswith('rustpy-')]
        if official:
            run(['pacman','-Sy','--noconfirm'] + official)
        # 3) build/generate rustpy meta-pkgs
        raw_de = os.getenv('XDG_CURRENT_DESKTOP','').split(':')[0].lower()
        de_dep = de_map.get(raw_de, 'base')
        for meta in (m for m in selected if m.startswith('rustpy-')):
            d = base_dir / meta
            if not d.exists():
                d.mkdir()
                skeleton = f"""
pkgname={meta}
pkgver=1.0.0
pkgrel=1
pkgdesc="RustPy-Arch meta-package: {meta}"
arch=('x86_64')
license=('MIT')
depends=('"{de_dep}"')
source=()
sha256sums=('SKIP')

package() {{
  :
}}
"""
                (d / 'PKGBUILD').write_text(skeleton)
            run(['makepkg','-si','--noconfirm'], cwd=str(d))
        # 4) apply theme
        if self.theme_path:
            # set as desktop background via feh
            run(['feh','--bg-scale', str(self.theme_path)])
        # 5) finalize
        run(['bash', str(base_dir/'rustpy-arch-bootstrap.sh')], check=False)
        Gtk.main_quit()

    def _message(self, txt):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=txt
        )
        dlg.run(); dlg.destroy()

if __name__ == '__main__':
    InstallerGUI().connect('destroy', Gtk.main_quit)
    Gtk.main()

~~~
