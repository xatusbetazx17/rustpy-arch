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

def is_installed(pkg):
    """Return True if pacman -Qi <pkg> succeeds."""
    return subprocess.run(
        ['pacman', '-Qi', pkg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

def detect_gpu():
    """Return the correct GPU driver package name or None."""
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

def scan_wifi():
    """Return a sorted list of SSIDs visible via nmcli."""
    try:
        raw = subprocess.check_output(
            ['nmcli','-t','-f','SSID','dev','wifi']
        ).decode().splitlines()
        return sorted({s for s in raw if s})
    except subprocess.CalledProcessError:
        return []

# -----------------------------------------------------------------------------
# Installer GUI
# -----------------------------------------------------------------------------
class InstallerGUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Pre-Installer")
        self.set_default_size(600, 480)
        self.set_border_width(12)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(outer)

        # Notebook
        self.nb = Gtk.Notebook()
        outer.pack_start(self.nb, True, True, 0)
        self._build_network_page()
        self._build_disk_page()
        self._build_components_page()
        self._build_graphics_page()

        # Start button
        btn_start = Gtk.Button(label="Start Installation")
        btn_start.connect("clicked", lambda w: self.on_start())
        outer.pack_start(btn_start, False, False, 0)

        self.show_all()

    # -- Network Page ---------------------------------------------------------
    def _build_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.nb.append_page(page, Gtk.Label(label="Network"))

        # Mirror refresh
        btn_mirror = Gtk.Button(label="Refresh Mirrors")
        btn_mirror.connect("clicked", lambda w: self._refresh_mirrors())
        page.pack_start(btn_mirror, False, False, 0)

        # Wi-Fi SSIDs
        page.pack_start(Gtk.Label(label="Available Wi-Fi Networks:"), False, False, 0)
        self.cb_ssid = Gtk.ComboBoxText()
        page.pack_start(self.cb_ssid, False, False, 0)
        self._refresh_ssids()

        # Password entry
        self.ent_pwd = Gtk.Entry()
        self.ent_pwd.set_visibility(False)
        self.ent_pwd.set_placeholder_text("Password (if required)")
        page.pack_start(self.ent_pwd, False, False, 0)

        # Connect button
        btn_conn = Gtk.Button(label="Connect")
        btn_conn.connect("clicked", lambda w: self._connect_wifi())
        page.pack_start(btn_conn, False, False, 0)

    def _refresh_mirrors(self):
        try:
            run(["reflector","--country","US","--latest","5","--sort","rate",
                 "--save","/etc/pacman.d/mirrorlist"])
            self._message("Mirrorlist refreshed")
        except Exception as e:
            self._message(f"Failed to refresh mirrors: {e}")

    def _refresh_ssids(self):
        ssids = scan_wifi()
        self.cb_ssid.remove_all()
        for s in ssids:
            self.cb_ssid.append_text(s)
        if ssids:
            self.cb_ssid.set_active(0)

    def _connect_wifi(self):
        ssid = self.cb_ssid.get_active_text()
        pwd  = self.ent_pwd.get_text().strip()
        if not ssid:
            return self._message("Please select a network first.")
        cmd = ['nmcli','dev','wifi','connect',ssid]
        if pwd:
            cmd += ['password', pwd]
        try:
            run(cmd)
            self._message(f"Connected to {ssid}")
        except Exception as e:
            self._message(f"Failed to connect: {e}")

    # -- Disk Page ------------------------------------------------------------
    def _build_disk_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.nb.append_page(page, Gtk.Label(label="Disk"))
        self.spin_root = Gtk.SpinButton.new_with_range(10,500,5)
        self.spin_home = Gtk.SpinButton.new_with_range(10,500,5)
        self.spin_var  = Gtk.SpinButton.new_with_range(5,200,5)
        page.pack_start(Gtk.Label(label="Root size (GB):"), False, False, 0)
        page.pack_start(self.spin_root, False, False, 0)
        page.pack_start(Gtk.Label(label="Home size (GB):"), False, False, 0)
        page.pack_start(self.spin_home, False, False, 0)
        page.pack_start(Gtk.Label(label="Var size (GB):"), False, False, 0)
        page.pack_start(self.spin_var, False, False, 0)

    # -- Components Page ------------------------------------------------------
    def _build_components_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
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
                cb.set_label(f"{label} (installed)")
            self.ck[pkg] = cb
            page.pack_start(cb, False, False, 0)

    # -- Graphics Page --------------------------------------------------------
    def _build_graphics_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.nb.append_page(page, Gtk.Label(label="Graphics"))
        gpu = detect_gpu()
        text = f"Install {gpu} driver" if gpu else "No GPU detected"
        self.cb_gpu = Gtk.CheckButton(label=text)
        if not gpu:
            self.cb_gpu.set_sensitive(False)
        page.pack_start(self.cb_gpu, False, False, 0)

    # -- Start Installation --------------------------------------------------
    def on_start(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 1) Official vs meta
        selected = [p for p,cb in self.ck.items() if cb.get_active() and cb.get_sensitive()]
        if self.cb_gpu.get_active() and detect_gpu():
            selected.append(detect_gpu())
        official  = [p for p in selected if not p.startswith('rustpy-')]
        local_meta = [p for p in selected if p.startswith('rustpy-')]

        # 2) Install official
        if official:
            self._message("Installing: "+", ".join(official))
            try:
                run(['pacman','-Sy','--noconfirm']+official)
            except Exception as e:
                self._message(f"pacman failed: {e}")

        # 3) Build / generate meta-packages
        for meta in local_meta:
            d = os.path.join(base_dir, meta)
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
                dep = os.environ.get('XDG_CURRENT_DESKTOP','generic').lower() or 'base'
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
  :  # meta only
}}
"""
                open(os.path.join(d,'PKGBUILD'),'w').write(skeleton)
                self._message(f"Generated PKGBUILD for {meta}")
            self._message(f"Building {meta}…")
            try:
                run(['makepkg','-si','--noconfirm'], cwd=d)
            except Exception as e:
                self._message(f"makepkg failed: {e}")

        # 4) Launch full bootstrap
        boot = os.path.join(base_dir,'rustpy-arch-bootstrap.sh')
        if not os.path.isfile(boot):
            return self._message("Bootstrap script missing!")
        self._message("Launching full bootstrap in background…")
        run(['bash',boot], check=False)

        Gtk.main_quit()

    # -- Dialog Helper --------------------------------------------------------
    def _message(self, text):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=text
        )
        dlg.run()
        dlg.destroy()

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

