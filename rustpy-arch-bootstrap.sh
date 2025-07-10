#!/usr/bin/env python3
import os
import subprocess
import sys
import gi
import random

# -----------------------------------------------------------------------------
# Auto-install missing Python modules via pacman
# -----------------------------------------------------------------------------
def ensure_pkg(pkg_name):
    if subprocess.run(
        ['pacman','-Qi', pkg_name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode != 0:
        subprocess.run(
            ['sudo','pacman','-Sy','--noconfirm', pkg_name],
            check=True
        )

# Pillow for image generation
try:
    from PIL import Image, ImageDraw
except ImportError:
    ensure_pkg('python-pillow')
    from PIL import Image, ImageDraw

# PyGObject
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

# -----------------------------------------------------------------------------
# DE ↔ Arch groups
# -----------------------------------------------------------------------------
DE_MAP = {
    'xfce':     'xfce4',
    'gnome':    'gnome',
    'kde':      'plasma-desktop',
    'deepin':   'deepin',
    'lxqt':     'lxqt',
    'mate':     'mate',
    'cinnamon': 'cinnamon',
    'budgie':   'budgie-desktop',
}

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def run(cmd, check=True, cwd=None):
    if check:
        subprocess.run(cmd, check=True, cwd=cwd)
    else:
        subprocess.Popen(cmd, cwd=cwd)

def is_installed(pkg):
    return subprocess.run(
        ['pacman','-Qi',pkg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

def detect_gpu():
    out = subprocess.check_output(
        "lspci -nn | grep -Ei 'VGA'", shell=True
    ).decode().lower()
    if 'nvidia' in out: return 'nvidia'
    if 'amd'    in out: return 'xf86-video-amdgpu'
    if 'intel'  in out: return 'mesa'
    return None

def scan_wifi():
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
        super().__init__(title="RustPy-Arch Installer")
        self.set_default_size(900, 600)
        self.set_border_width(12)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        self.nb = Gtk.Notebook()
        vbox.pack_start(self.nb, True, True, 0)

        self._build_network_page()
        self._build_disk_page()
        self._build_components_page()
        self._build_graphics_page()
        self._build_kernel_page()     # NEW
        self._build_theme_page()      # NEW
        self._build_rustpy_page()

        btn_start = Gtk.Button(label="Start Installation")
        btn_start.connect("clicked", lambda w: self.on_start())
        vbox.pack_start(btn_start, False, False, 0)

        self.show_all()

    # --- Network -------------------------------------------------------------
    def _build_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Network"))
        btn = Gtk.Button(label="Refresh Mirrors")
        btn.connect("clicked", lambda w: self._refresh_mirrors())
        page.pack_start(btn, False, False, 0)
        page.pack_start(Gtk.Label(label="Wi-Fi SSIDs:"), False, False, 0)
        self.cb_ssid = Gtk.ComboBoxText()
        page.pack_start(self.cb_ssid, False, False, 0)
        self._refresh_ssids()
        self.ent_pwd = Gtk.Entry(); self.ent_pwd.set_visibility(False)
        self.ent_pwd.set_placeholder_text("Password (if required)")
        page.pack_start(self.ent_pwd, False, False, 0)
        btn = Gtk.Button(label="Connect")
        btn.connect("clicked", lambda w: self._connect_wifi())
        page.pack_start(btn, False, False, 0)

    def _refresh_mirrors(self):
        try:
            run([
                "reflector","--country","US","--latest","5",
                "--sort","rate","--save","/etc/pacman.d/mirrorlist"
            ])
            self._message("Mirrors refreshed")
        except Exception as e:
            self._message(f"Mirror refresh failed: {e}")

    def _refresh_ssids(self):
        self.cb_ssid.remove_all()
        for s in scan_wifi():
            self.cb_ssid.append_text(s)
        if self.cb_ssid.get_active() < 0 and self.cb_ssid.get_model().iter_n_children(None)>0:
            self.cb_ssid.set_active(0)

    def _connect_wifi(self):
        ssid = self.cb_ssid.get_active_text()
        pwd  = self.ent_pwd.get_text().strip()
        if not ssid:
            return self._message("Select a network first.")
        cmd = ['nmcli','dev','wifi','connect',ssid]
        if pwd: cmd+=['password',pwd]
        try:
            run(cmd)
            self._message(f"Connected to {ssid}")
        except Exception as e:
            self._message(f"Connect failed: {e}")

    # --- Disk ----------------------------------------------------------------
    def _build_disk_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Disk Layout"))
        for label, rng in (
            ("Root (GB):", (10,500,5)),
            ("Home (GB):", (10,500,5)),
            ("Var  (GB):", (5,200,5)),
        ):
            page.pack_start(Gtk.Label(label=label), False, False, 0)
            spin = Gtk.SpinButton.new_with_range(*rng)
            setattr(self, f"spin_{label.split()[0].lower()}", spin)
            page.pack_start(spin, False, False, 0)

    # --- Components ----------------------------------------------------------
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
                cb.set_label(f"{label} (installed)")
            self.ck[pkg] = cb
            page.pack_start(cb, False, False, 0)

    # --- Graphics ------------------------------------------------------------
    def _build_graphics_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Graphics"))
        gpu = detect_gpu()
        text = f"Install {gpu} driver" if gpu else "No GPU detected"
        self.cb_gpu = Gtk.CheckButton(label=text)
        if not gpu: self.cb_gpu.set_sensitive(False)
        page.pack_start(self.cb_gpu, False, False, 0)

    # --- Kernel --------------------------------------------------------------
    def _build_kernel_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Kernel"))
        self.cb_kernel = Gtk.CheckButton(
            label="Build custom kernel with my hardware config"
        )
        page.pack_start(self.cb_kernel, False, False, 0)

    # --- Theme ---------------------------------------------------------------
    def _build_theme_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Theme"))
        self.cb_use_icons = Gtk.CheckButton(label="Use existing system icon theme")
        self.cb_gen_wall  = Gtk.CheckButton(label="Generate a random wallpaper")
        page.pack_start(self.cb_use_icons, False, False, 0)
        page.pack_start(self.cb_gen_wall,  False, False, 0)

    # --- Rust+Python ---------------------------------------------------------
    def _build_rustpy_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.nb.append_page(page, Gtk.Label(label="Rust + Python"))
        self.cb_ripgrep    = Gtk.CheckButton(label="ripgrep")
        self.cb_exa        = Gtk.CheckButton(label="exa")
        self.cb_tar_rs     = Gtk.CheckButton(label="tar-rs")
        self.cb_systemd_rs = Gtk.CheckButton(label="systemd-system-rs")
        self.cb_rustpython = Gtk.CheckButton(label="RustPython")
        self.cb_pyo3       = Gtk.CheckButton(label="PyO3")
        for cb in (
            self.cb_ripgrep, self.cb_exa, self.cb_tar_rs,
            self.cb_systemd_rs, self.cb_rustpython, self.cb_pyo3
        ):
            page.pack_start(cb, False, False, 0)

    # --- Start Installation -------------------------------------------------
    def on_start(self):
        base = os.path.dirname(os.path.abspath(__file__))

        # 1) custom kernel?
        if self.cb_kernel.get_active():
            self._build_custom_kernel()

        # 2) theme
        if self.cb_gen_wall.get_active():
            self._generate_wallpaper()
        # no-op if using system icons

        # 3) rest of your flow (network, disk, etc.)
        # [copy in your existing on_start logic here]
        self._message("Now proceeding with normal Arch/RustPyDE install…")
        Gtk.main_quit()

    # --- Custom Kernel -------------------------------------------------------
    def _build_custom_kernel(self):
        self._message("Building custom kernel…")
        ensure_pkg('asp')
        work = os.path.expanduser('~/rustpy-kernel')
        if os.path.exists(work): subprocess.run(['rm','-rf',work])
        os.makedirs(work,exist_ok=True)
        # export Arch kernel PKGBUILD
        run(['asp','export','linux'], cwd=work)
        kdir = os.path.join(work,'linux')
        # copy running config
        if os.path.exists('/proc/config.gz'):
            run(['zcat','/proc/config.gz'], check=False, cwd=kdir)
            subprocess.run(
                ['zcat','/proc/config.gz'], stdout=open(os.path.join(kdir,'.config'),'wb')
            )
        # build
        try:
            run(['makepkg','-si','--noconfirm'], cwd=kdir)
            self._message("Custom kernel built & installed.")
        except Exception as e:
            self._message(f"Kernel build failed: {e}")

    # --- Wallpaper -----------------------------------------------------------
    def _generate_wallpaper(self):
        path = os.path.expanduser('~/Pictures/rustpy_wallpaper.png')
        w,h = 1920,1080
        im = Image.new('RGB',(w,h), (
            random.randrange(256),
            random.randrange(256),
            random.randrange(256)
        ))
        draw = ImageDraw.Draw(im)
        # simple gradient
        for y in range(h):
            c = int(255 * y / h)
            draw.line([(0,y),(w,y)], fill=(c,c//2,255-c))
        im.save(path)
        self._message(f"Wallpaper generated at {path}")

    # --- Dialog --------------------------------------------------------------
    def _message(self, txt):
        dlg = Gtk.MessageDialog(
            transient_for=self, flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=txt
        )
        dlg.run(); dlg.destroy()

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()



