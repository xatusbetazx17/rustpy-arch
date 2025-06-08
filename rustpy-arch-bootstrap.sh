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

# Helper to run shell commands and capture output
def sh(cmd):
    return subprocess.check_output(cmd, shell=True).decode().strip()

# Rust driver-detect stub (you'd implement this in Rust and compile to e.g. /usr/local/bin/driver_detect)
# For now, we'll fake it:
def detect_gpu():
    out = sh("lspci -nn | grep -Ei 'VGA'")
    if 'NVIDIA' in out: return 'nvidia'
    if 'AMD'    in out: return 'xf86-video-amdgpu'
    if 'Intel'  in out: return 'mesa'
    return None

class InstallerGUI(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Pre-Installer")
        self.set_border_width(10)
        self.set_default_size(500, 400)

        notebook = Gtk.Notebook()
        self.add(notebook)

        # Page 1: Mirrors & Network
        page1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        notebook.append_page(page1, Gtk.Label(label="Network"))

        # Mirror refresh
        btn_mirror = Gtk.Button(label="Refresh Mirrorlist")
        btn_mirror.connect("clicked", self.on_refresh_mirrors)
        page1.pack_start(btn_mirror, False, False, 0)

        # Wi-Fi entry
        self.ssid = Gtk.Entry();   self.ssid.set_placeholder_text("SSID")
        self.pwd  = Gtk.Entry();   self.pwd.set_placeholder_text("Password"); self.pwd.set_visibility(False)
        btn_wifi = Gtk.Button(label="Connect Wi-Fi")
        btn_wifi.connect("clicked", self.on_connect_wifi)
        page1.pack_start(Gtk.Label(label="Wi-Fi SSID / Password:"), False, False, 0)
        page1.pack_start(self.ssid, False, False, 0)
        page1.pack_start(self.pwd, False, False, 0)
        page1.pack_start(btn_wifi, False, False, 0)

        # Page 2: Disk Allocation
        page2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        notebook.append_page(page2, Gtk.Label(label="Disk"))

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
        notebook.append_page(page3, Gtk.Label(label="Components"))

        # For each component, show checkbox if *not* already installed
        self.checks = {}
        components = {
            'rust':'Rust compiler',
            'git':'Git',
            'base':'Base system',
            'rustpy-de-core':'RustPyDE',
            'rustpy-gaming':'Gaming profile',
            'rustpy-office':'Office profile',
            'rustpy-dev':'Dev profile',
            'rustpy-multimedia':'Multimedia profile',
        }
        for pkg,label in components.items():
            cb = Gtk.CheckButton(label=label)
            if is_installed(pkg):
                cb.set_active(False)
                cb.set_sensitive(False)
                cb.set_label(f"{label} (already installed)")
            self.checks[pkg] = cb
            page3.pack_start(cb, False, False, 0)

        # Page 4: Graphics Driver
        page4 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
        notebook.append_page(page4, Gtk.Label(label="Graphics"))
        current = detect_gpu()
        self.cb_gpu = Gtk.CheckButton(label=f"Install {current} driver" if current else "No GPU driver detected")
        if not current:
            self.cb_gpu.set_sensitive(False)
        page4.pack_start(self.cb_gpu, False, False, 0)

        # Final “Run” button
        btn_run = Gtk.Button(label="Start Installation")
        btn_run.connect("clicked", self.on_start)
        self.add(btn_run)
        self.show_all()

    def on_refresh_mirrors(self, w):
        # call your reflector code
        subprocess.Popen(["bash","-c","reflector --country 'US' --age 12 --sort rate --save /etc/pacman.d/mirrorlist"])
        self.show_feedback("Mirrorlist refreshed")

    def on_connect_wifi(self, w):
        ssid = self.ssid.get_text()
        pwd  = self.pwd.get_text()
        subprocess.Popen(["bash","-c",f"iwctl station wlan0 connect '{ssid}'"])
        self.show_feedback(f"Connecting to {ssid}")

    def show_feedback(self, msg):
        dialog = Gtk.MessageDialog(self, 0, Gtk.MessageType.INFO,
                                   Gtk.ButtonsType.OK, msg)
        dialog.run()
        dialog.destroy()

    def on_start(self, w):
        # 1. Partition using self.size_root.get_value(), etc.
        #    you’d shell out to parted or btrfs tools here.
        # 2. For each checked component: run your bash bootstrap or pacstrap lines.
        # 3. If cb_gpu active: pacman -S the driver.
        # 4. Finally, reboot or chroot back as needed.
        # For now, we’ll just launch your existing installer script:
        subprocess.Popen(["bash","-c","/root/rustpy-arch-bootstrap.sh"])
        self.show_feedback("Installation started in background; follow terminal output.")
        Gtk.main_quit()

def main():
    Gtk.init(None)
    win = InstallerGUI()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()

if __name__ == "__main__":
    main()
