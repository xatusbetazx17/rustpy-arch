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
from gi.repository import Gtk

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def run(cmd, check=True, cwd=None):
    """Run a command list, optionally in the background."""
    if check:
        subprocess.run(cmd, check=True, cwd=cwd)
    else:
        subprocess.Popen(cmd, cwd=cwd)

def pacman_installed(pkg):
    """Return True if pacman -Qi <pkg> succeeds."""
    return subprocess.run(
        ['pacman', '-Qi', pkg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

def detect_gpu_driver():
    """Return the correct mesa/amdgpu/nvidia pkg or None."""
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

def list_wifi_ssids():
    """Use nmcli to return a sorted list of visible SSIDs."""
    try:
        lines = subprocess.check_output(
            ['nmcli', '-t', '-f', 'SSID,SECURITY', 'dev', 'wifi']
        ).decode().splitlines()
        ssids = []
        for line in lines:
            ssid, sec = line.split(':', 1)
            if ssid and ssid not in ssids:
                ssids.append(ssid)
        return sorted(ssids)
    except subprocess.CalledProcessError:
        return []

# -----------------------------------------------------------------------------
# Installer GUI
# -----------------------------------------------------------------------------
class InstallerGUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Installer")
        self.set_default_size(600, 450)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=12)
        self.add(vbox)

        # Notebook
        self.nb = Gtk.Notebook()
        vbox.pack_start(self.nb, True, True, 0)
        self._build_network_page()
        self._build_components_page()
        self._build_graphics_page()

        # Start button
        btn = Gtk.Button(label="Start Installation")
        btn.connect("clicked", self.on_start)
        vbox.pack_start(btn, False, False, 0)

        self.show_all()

    # ----------------------------------------
    def _build_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Network"))

        # Refresh SSIDs
        btn_refresh = Gtk.Button(label="Scan Wi-Fi Networks")
        btn_refresh.connect("clicked", lambda w: self._refresh_ssids())
        page.pack_start(btn_refresh, False, False, 0)

        # SSID dropdown
        self.cb_ssid = Gtk.ComboBoxText()
        self._refresh_ssids()
        page.pack_start(Gtk.Label(label="Choose SSID:"), False, False, 0)
        page.pack_start(self.cb_ssid, False, False, 0)

        # Password entry
        self.ent_pwd = Gtk.Entry()
        self.ent_pwd.set_visibility(False)
        self.ent_pwd.set_placeholder_text("Password (if required)")
        page.pack_start(self.ent_pwd, False, False, 0)

        # Connect button
        btn_conn = Gtk.Button(label="Connect")
        btn_conn.connect("clicked", self.on_connect_wifi)
        page.pack_start(btn_conn, False, False, 0)

    def _refresh_ssids(self):
        self.cb_ssid.remove_all()
        for ssid in list_wifi_ssids():
            self.cb_ssid.append_text(ssid)
        if self.cb_ssid.get_active() < 0 and self.cb_ssid.get_row_count() > 0:
            self.cb_ssid.set_active(0)

    def on_connect_wifi(self, btn):
        ssid = self.cb_ssid.get_active_text()
        pwd  = self.ent_pwd.get_text().strip()
        if not ssid:
            return self._message("Please select a network first.")
        cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
        if pwd:
            cmd += ['password', pwd]
        try:
            run(cmd)
            self._message(f"Connected to {ssid}")
        except Exception as e:
            self._message(f"Failed to connect: {e}")

    # ----------------------------------------
    def _build_components_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Components"))

        self.ck = {}
        comps = {
            'rust':            'Rust compiler',
            'git':             'Git',
            'base':            'Base system',
            'rustpy-de-core':  'RustPyDE',
            'rustpy-gaming':   'Gaming profile',
            'rustpy-office':   'Office profile',
            'rustpy-dev':      'Development tools',
            'rustpy-multimedia':'Multimedia suite',
        }
        for pkg, label in comps.items():
            cb = Gtk.CheckButton(label=label)
            if pacman_installed(pkg):
                cb.set_sensitive(False)
                cb.set_label(f"{label} (installed)")
            self.ck[pkg] = cb
            page.pack_start(cb, False, False, 0)

    # ----------------------------------------
    def _build_graphics_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Graphics"))

        gpu = detect_gpu_driver()
        label = f"Install {gpu} driver" if gpu else "No GPU card detected"
        self.cb_gpu = Gtk.CheckButton(label=label)
        if not gpu:
            self.cb_gpu.set_sensitive(False)
        page.pack_start(self.cb_gpu, False, False, 0)

    # ----------------------------------------
    def on_start(self, btn):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 1) collect pkgs
        selected = [pkg for pkg, cb in self.ck.items() if cb.get_active() and cb.get_sensitive()]
        if self.cb_gpu.get_active() and detect_gpu_driver():
            selected.append(detect_gpu_driver())

        # 2) official vs local
        official  = [p for p in selected if not p.startswith('rustpy-')]
        local_meta = [p for p in selected if p.startswith('rustpy-')]

        # 3) install official
        if official:
            self._message("Installing: " + ", ".join(official))
            try:
                run(['pacman','-Sy','--noconfirm'] + official)
            except Exception as e:
                self._message(f"pacman error: {e}")

        # 4) build local meta
        for meta in local_meta:
            meta_dir = os.path.join(base_dir, meta)
            if not os.path.isdir(meta_dir):
                # generate skeleton
                os.makedirs(meta_dir, exist_ok=True)
                dep = os.environ.get('XDG_CURRENT_DESKTOP','').lower() or 'base'
                skeleton = f"""\
pkgname={meta}
pkgver=1.0.0
pkgrel=1
pkgdesc="RustPy-Arch meta-package: {meta}"
arch=('x86_64')
license=('MIT')
depends=('{dep}')
source=()
sha256sums=('SKIP')

package() {{
  # meta-package: no files
  :
}}
"""
                open(os.path.join(meta_dir,'PKGBUILD'),'w').write(skeleton)
                self._message(f"Generated PKGBUILD for {meta}")
            # now build
            self._message(f"Building {meta}…")
            try:
                run(['makepkg','-si','--noconfirm'], cwd=meta_dir)
            except Exception as e:
                self._message(f"makepkg failed: {e}")

        # 5) run full bootstrap
        bootstrap = os.path.join(base_dir, '..', 'rustpy-arch-bootstrap.sh')
        if not os.path.isfile(bootstrap):
            return self._message(f"Bootstrap script missing: {bootstrap}")
        self._message("Launching full bootstrap…")
        run(['bash', bootstrap], check=False)

        Gtk.main_quit()

    # ----------------------------------------
    def _message(self, text):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=text
        )
        dlg.run(); dlg.destroy()

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()


~~~
