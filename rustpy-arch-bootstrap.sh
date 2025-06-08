#!/usr/bin/env python3
import os
import subprocess
import sys
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
        btn_mirror = Gtk.Button(label="Refresh Mirrors")
        btn_mirror.connect("clicked", self.refresh_mirrors)
        page1.pack_start(btn_mirror, False, False, 0)
        self.ssid = Gtk.Entry(); self.ssid.set_placeholder_text("SSID")
        self.pwd  = Gtk.Entry(); self.pwd.set_placeholder_text("Password"); self.pwd.set_visibility(False)
        btn_wifi = Gtk.Button(label="Connect Wi-Fi")
        btn_wifi.connect("clicked", self.connect_wifi)
        page1.pack_start(Gtk.Label(label="Wi-Fi:"), False, False, 0)
        page1.pack_start(self.ssid, False, False, 0)
        page1.pack_start(self.pwd, False, False, 0)
        page1.pack_start(btn_wifi, False, False, 0)

        # Page 2: Disk sizes (not yet hooked to actual partitioning)
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
        for pkg,label in comps.items():
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
        ssid = self.ssid.get_text()
        pwd  = self.pwd.get_text()
        run(["iwctl","station","wlan0","connect", ssid])
        self._message(f"Connecting to {ssid}")

    def _message(self, msg):
        dlg = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, msg)
        dlg.run()
        dlg.destroy()

    def on_start(self, btn):
        # Determine base repository directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Gather selected components
        selected = [pkg for pkg, cb in self.checks.items() if cb.get_active() and cb.get_sensitive()]
        # Include GPU driver if chosen
        if self.cb_gpu.get_active():
            gpu = detect_gpu()
            if gpu:
                selected.append(gpu)

        # Split into official packages vs local meta-packages
        official = [pkg for pkg in selected if not pkg.startswith('rustpy-')]
        local_pkgs = [pkg for pkg in selected if pkg.startswith('rustpy-')]

        # Install official packages via pacman
        if official:
            self._message(f"Installing official packages: {', '.join(official)}")
            run(["pacman", "-Sy", "--noconfirm"] + official)

        # Build and install local meta-packages
        for pkg in local_pkgs:
            pkg_dir = os.path.join(base_dir, pkg)
            if os.path.isdir(pkg_dir):
                self._message(f"Building and installing {pkg}...")
                run(["makepkg", "-si", "--noconfirm"], cwd=pkg_dir)
            else:
                self._message(f"Warning: directory for {pkg} not found, skipping")

        # Finally, launch the bootstrap script for everything else
        bootstrap = os.path.join(base_dir, 'rustpy-arch-bootstrap.sh')
        if os.path.isfile(bootstrap):
            self._message("Launching full bootstrap script in background...")
            run(["bash", bootstrap], wait=False)
        else:
            self._message("Error: bootstrap script not found")

        Gtk.main_quit()

if __name__ == '__main__':
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
