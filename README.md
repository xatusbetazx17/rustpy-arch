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
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

# Helper to check if a pacman pkg is installed
def is_installed(pkg):
    r = subprocess.run(['pacman','-Qi',pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return (r.returncode == 0)

# Helper to run commands
def run(cmd_list, wait=True, cwd=None):
    try:
        if wait:
            subprocess.run(cmd_list, check=True, cwd=cwd)
        else:
            subprocess.Popen(cmd_list, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error running {cmd_list}: {e}")

# Detect GPU driver
def detect_gpu():
    out = subprocess.run("lspci -nn | grep -Ei 'VGA'", shell=True, capture_output=True)
    desc = out.stdout.decode()
    if 'NVIDIA' in desc:
        return 'nvidia'
    if 'AMD' in desc:
        return 'xf86-video-amdgpu'
    if 'Intel' in desc:
        return 'mesa'
    return None

# Scan available Wi-Fi networks using nmcli
def scan_wifi():
    result = subprocess.run(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'], capture_output=True)
    ssids = set(line for line in result.stdout.decode().splitlines() if line)
    return sorted(ssids)

class InstallerGUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Pre-Installer")
        self.set_border_width(10)
        self.set_default_size(600, 500)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(outer)

        # Notebook for pages
        self.notebook = Gtk.Notebook()
        outer.pack_start(self.notebook, True, True, 0)
        self._build_pages()

        # Install button
        btn_run = Gtk.Button(label="Start Installation")
        btn_run.connect("clicked", self.on_start)
        outer.pack_start(btn_run, False, False, 0)

        self.show_all()

    def _build_pages(self):
        # Page 1: Network
        page1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        self.notebook.append_page(page1, Gtk.Label(label="Network"))

        # Mirror refresh
        btn_mirror = Gtk.Button(label="Refresh Mirrors")
        btn_mirror.connect("clicked", self.refresh_mirrors)
        page1.pack_start(btn_mirror, False, False, 0)

        # Wi-Fi networks combo
        page1.pack_start(Gtk.Label(label="Select Wi-Fi Network:"), False, False, 0)
        self.wifi_combo = Gtk.ComboBoxText()
        for ssid in scan_wifi():
            self.wifi_combo.append_text(ssid)
        self.wifi_combo.set_active(0 if self.wifi_combo.get_model() else -1)
        page1.pack_start(self.wifi_combo, False, False, 0)

        # Password entry
        page1.pack_start(Gtk.Label(label="Password (if required):"), False, False, 0)
        self.pwd = Gtk.Entry(); self.pwd.set_visibility(False)
        page1.pack_start(self.pwd, False, False, 0)

        # Connect button
        btn_wifi = Gtk.Button(label="Connect Wi-Fi")
        btn_wifi.connect("clicked", self.connect_wifi)
        page1.pack_start(btn_wifi, False, False, 0)

        # Page 2: Disk sizes
        page2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        self.notebook.append_page(page2, Gtk.Label(label="Disk"))
        self.size_root = Gtk.SpinButton.new_with_range(10,500,5)
        self.size_home = Gtk.SpinButton.new_with_range(10,500,5)
        self.size_var  = Gtk.SpinButton.new_with_range(5,200,5)
        page2.pack_start(Gtk.Label(label="Root (GB):"), False, False, 0)
        page2.pack_start(self.size_root, False, False, 0)
        page2.pack_start(Gtk.Label(label="Home (GB):"), False, False, 0)
        page2.pack_start(self.size_home, False, False, 0)
        page2.pack_start(Gtk.Label(label="Var (GB):"), False, False, 0)
        page2.pack_start(self.size_var, False, False, 0)

        # Page 3: Components
        page3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        self.notebook.append_page(page3, Gtk.Label(label="Components"))
        self.checks = {}
        comps = {
            'rust': 'Rust compiler',
            'git': 'Git',
            'base': 'Base system',
            'rustpy-de-core': 'RustPyDE',
            'rustpy-gaming': 'Gaming profile',
            'rustpy-office': 'Office profile',
            'rustpy-dev': 'Dev profile',
            'rustpy-multimedia': 'Multimedia profile'
        }
        for pkg, label in comps.items():
            cb = Gtk.CheckButton(label=label)
            if is_installed(pkg):
                cb.set_sensitive(False)
                cb.set_label(f"{label} (installed)")
            self.checks[pkg] = cb
            page3.pack_start(cb, False, False, 0)

        # Page 4: GPU driver
        page4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        self.notebook.append_page(page4, Gtk.Label(label="Graphics"))
        gpu = detect_gpu()
        self.cb_gpu = Gtk.CheckButton(label=(f"Install {gpu}" if gpu else "No GPU detected"))
        if not gpu:
            self.cb_gpu.set_sensitive(False)
        page4.pack_start(self.cb_gpu, False, False, 0)

    def refresh_mirrors(self, btn):
        run(["reflector","--country","US","--latest","5","--sort","rate","--save","/etc/pacman.d/mirrorlist"])
        self._message("Mirrors refreshed")

    def connect_wifi(self, btn):
        ssid = self.wifi_combo.get_active_text()
        pwd = self.pwd.get_text()
        if ssid:
            cmd = ["nmcli", "dev", "wifi", "connect", ssid]
            if pwd:
                cmd += ["password", pwd]
            run(cmd)
            self._message(f"Connecting to {ssid}")
        else:
            self._message("No Wi-Fi network selected.")

    def _message(self, msg):
        dlg = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, msg)
        dlg.run(); dlg.destroy()

    def on_start(self, btn):
        # Determine repo root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Gather selected components
        selected = [pkg for pkg, cb in self.checks.items() if cb.get_active() and cb.get_sensitive()]
        if self.cb_gpu.get_active():
            gpu = detect_gpu()
            if gpu:
                selected.append(gpu)

        # Split official vs local
        official = [p for p in selected if not p.startswith('rustpy-')]
        local_pkgs = [p for p in selected if p.startswith('rustpy-')]

        if official:
            self._message(f"Installing: {', '.join(official)}")
            run(["pacman","-Sy","--noconfirm"] + official)

        for pkg in local_pkgs:
            pkg_dir = os.path.join(base_dir, pkg)
            if not os.path.isdir(pkg_dir):
                os.makedirs(pkg_dir, exist_ok=True)
                de = os.environ.get('XDG_CURRENT_DESKTOP','generic').lower()
                template = f"""
pkgname={pkg}
pkgver=1.0.0
pkgrel=1
pkgdesc="RustPy-Arch meta-package: {pkg}"
arch=('x86_64')
license=('MIT')
depends=("{de}")
source=()
sha256sums=('SKIP')
package() {{ :; }}
"""
                with open(os.path.join(pkg_dir,'PKGBUILD'),'w') as f:
                    f.write(template)
                self._message(f"Generated PKGBUILD for {pkg}")
            self._message(f"Building {pkg}...")
            run(["makepkg","-si","--noconfirm"], cwd=pkg_dir)

        bootstrap = os.path.join(base_dir,'rustpy-arch-bootstrap.sh')
        if os.path.isfile(bootstrap):
            self._message("Launching bootstrap...")
            run(["bash",bootstrap], wait=False)
        else:
            self._message("bootstrap script missing")

        Gtk.main_quit()

if __name__ == '__main__':
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

~~~
