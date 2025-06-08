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

- [EndeavourOS Minimal ISO](https://endeavouros.com/latest-release)  
- [ArcoLinuxD ISO](https://arcolinux.info/downloads)  

## ⚙️ Install RustPy-Arch Script

Once your base system (EndeavourOS or ArcoLinux) is fully installed and you’ve booted into the new environment, open a terminal and run:

```bash
# Clone the RustPy-Arch repository
git clone https://github.com/xatusbetazx17/rustpy-arch.git
cd rustpy-arch

# Make the installer script executable and run it
chmod +x rustpy-arch-all-in-one.sh
./rustpy-arch-all-in-one.sh



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
````bash
#!/usr/bin/env bash
#
# rustpy-arch-all-in-one.sh
#
# Run this as root on a fresh Arch-based ISO/chroot to create and
# install the entire RustPy-Arch system in one step, including:
#  • Rust-based init (initrs) replacing systemd
#  • Rust coreutils (uutils) and other Rust utilities
#  • Python scripts for networking and graphical installer
#  • Btrfs subvolume layout for immutable root
#  • RustPyDE desktop environment and meta-packages
#
# WARNING: This will wipe/reconfigure your target root device (/dev/sda2
# by default), so only run on a test/new system.
#
# USAGE (once booted into an Arch live environment):
#   1. Download the official Arch Linux ISO and write it to a USB stick:
#        • Using balenaEtcher (GUI) or dd (CLI):
#            # dd if=/path/to/archlinux.iso of=/dev/sdX bs=4M status=progress oflag=sync
#        • (Replace /dev/sdX with your USB device; be careful not to overwrite other disks.)
#   2. Boot from that USB on your target machine.
#   3. From the Arch live prompt:
#        # loadkeys us      # (if needed to set your keyboard layout)
#        # timedatectl set-ntp true
#        # iwctl             # (if you need to connect to Wi-Fi; then “exit”)
#   4. Prepare partitions:
#        # fdisk /dev/sda    # or use cfdisk, parted, etc.
#        • Create an EFI partition (~300 MiB, FAT32)—e.g., /dev/sda1
#        • Create a root partition—e.g., /dev/sda2 (will be formatted as Btrfs)
#        • (Optional) Create swap if desired—e.g., /dev/sda3
#   5. Mount partitions:
#        # mount /dev/sda2 /mnt
#        # mkdir -p /mnt/boot/efi
#        # mount /dev/sda1 /mnt/boot/efi
#        # mkswap /dev/sda3 && swapon /dev/sda3   # (if you made swap)
#   6. Arch‐chroot into /mnt:
#        # pacstrap /mnt base   # (or skip if you prefer to just chroot and let the script install)
#        # arch-chroot /mnt /bin/bash
#   7. Copy this script into the chroot:
#        # cp /path/to/rustpy-arch-all-in-one.sh /root/
#        # chmod +x /root/rustpy-arch-all-in-one.sh
#   8. Run the script:
#        # /root/rustpy-arch-all-in-one.sh
#   9. When it finishes, exit chroot and reboot:
#        # exit
#        # umount -R /mnt
#        # reboot
#   10. In GRUB, select “RustPy-Arch.” The Rust-based init will launch the
#       graphical installer automatically—follow its steps to complete setup.
#
set -euo pipefail

# 0) Ensure script is run as root
if [[ "$(id -u)" -ne 0 ]]; then
  echo "ERROR: This script must be run as root." >&2
  exit 1
fi

# 1) Install essential packages
pacman -Sy --noconfirm --needed \
  base \
  linux \
  linux-firmware \
  grub \
  efibootmgr \
  python \
  python-pip \
  rust \
  git \
  base-devel \
  python-gobject \
  gtk3 \
  networkmanager \
  btrfs-progs \
  xorg-server-xwayland \
  sddm \
  leftwm \
  alacritty \
  xdg-desktop-portal \
  util-linux \
  systemd-networkd \
  systemd-resolved \
  ripgrep \
  fd \
  bat

# Enable NetworkManager
systemctl enable NetworkManager

# 2) Basic systemd-networkd & systemd-resolved as fallback
cat > /etc/systemd/network/20-wired.network << 'EOF'
[Match]
Name=en*

[Network]
DHCP=ipv4
EOF

ln -sf /usr/lib/systemd/system/systemd-networkd.service /etc/systemd/system/multi-user.target.wants/
ln -sf /usr/lib/systemd/system/systemd-resolved.service /etc/systemd/system/multi-user.target.wants/
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# 3) Create first-boot flag
touch /etc/rustpy-install-pending

# 4) Replace GNU coreutils with uutils (Rust)
cd /tmp
rm -rf /tmp/coreutils
git clone https://github.com/uutils/coreutils.git /tmp/coreutils
cd /tmp/coreutils
cargo build --release
mkdir -pv /usr/local/bin
cp -v target/release/* /usr/local/bin/

cat > /etc/profile.d/99-localbin.sh << 'EOF'
export PATH="/usr/local/bin:\$PATH"
EOF
chmod +x /etc/profile.d/99-localbin.sh

# 5) Install Rust-based replacements
ln -sf /usr/bin/rg   /usr/local/bin/grep
ln -sf /usr/bin/fd   /usr/local/bin/find
ln -sf /usr/bin/bat  /usr/local/bin/cat

# 6) Build and install Rust init (initrs)
pacman -Sy --noconfirm --needed util-linux

mkdir -pv /opt/initrs
cat > /opt/initrs/Cargo.toml << 'EOF'
[package]
name = "initrs"
version = "0.1.0"
edition = "2021"

[dependencies]
nix = "0.26"
EOF

mkdir -pv /opt/initrs/src
cat > /opt/initrs/src/main.rs << 'EOF'
use nix::mount::{mount, MsFlags};
use nix::unistd::{fork, ForkResult};
use std::process::Command;

fn main() {
    // Mount /proc, /sys, /dev
    mount::<_, _, _, &str>(Some("proc"), "/proc", Some("proc"), MsFlags::empty(), None)
        .expect("mount /proc failed");
    mount::<_, _, _, &str>(Some("sysfs"), "/sys", Some("sysfs"), MsFlags::empty(), None)
        .expect("mount /sys failed");
    mount::<_, _, _, &str>(Some("devtmpfs"), "/dev", Some("devtmpfs"), MsFlags::empty(), None)
        .expect("mount /dev failed");

    // If first-boot flag exists, launch graphical installer under Xwayland
    if std::path::Path::new("/etc/rustpy-install-pending").exists() {
        let _ = Command::new("bash")
            .args(&["-c", "source /etc/profile; Xwayland :1 vt$(fgconsole) &> /dev/null & sleep 1; DISPLAY=:1 python3 /usr/local/bin/installer.py"])
            .spawn();
        std::thread::sleep(std::time::Duration::from_secs(5));
    }

    // After installer or if not first-boot, spawn SDDM
    match unsafe { fork() } {
        Ok(ForkResult::Child) => {
            Command::new("/usr/bin/sddm").spawn().expect("failed to start sddm");
        }
        Ok(ForkResult::Parent { .. }) => { }
        Err(err) => {
            eprintln!("Fork failed: {}", err);
        }
    }

    // Keep PID 1 alive
    loop {
        std::thread::sleep(std::time::Duration::from_secs(60));
    }
}
EOF

cd /opt/initrs
cargo build --release
install -Dm755 target/release/initrs /sbin/init

# 7) Python network-config script
mkdir -pv /opt/python-scripts
chmod 755 /opt/python-scripts

cat > /opt/python-scripts/netconfig.py << 'EOF'
#!/usr/bin/env python3
"""
netconfig.py: Read /etc/netconfig.yaml and apply settings.

Format of /etc/netconfig.yaml:

interfaces:
  en*:
    dhcp: true
"""
import yaml, subprocess, sys

def apply_config(path="/etc/netconfig.yaml"):
    try:
        with open(path) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        print(f"[netconfig] Failed to load YAML: {e}", file=sys.stderr)
        sys.exit(1)

    for iface, settings in cfg.get("interfaces", {}).items():
        if settings.get("dhcp", False):
            subprocess.run(["ip", "link", "set", iface, "up"], check=False)
            subprocess.run(["dhcpcd", iface], check=False)
        elif "address" in settings:
            addr = settings["address"]
            gw   = settings.get("gateway", None)
            subprocess.run(["ip", "link", "set", iface, "up"], check=False)
            subprocess.run(["ip", "addr", "add", addr, "dev", iface], check=False)
            if gw:
                subprocess.run(["ip", "route", "add", "default", "via", gw], check=False)

if __name__ == "__main__":
    apply_config()
EOF

chmod +x /opt/python-scripts/netconfig.py
pip install PyYAML

cat > /etc/netconfig.yaml << 'EOF'
interfaces:
  en*:
    dhcp: true
EOF

cat > /etc/systemd/system/netconfig.service << 'EOF'
[Unit]
Description=Apply custom network config via Python
After=network-pre.target
Wants=network-pre.target

[Service]
Type=oneshot
ExecStart=/opt/python-scripts/netconfig.py

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable netconfig.service

# 8) Configure GRUB to use Rust init
cp -v /etc/default/grub /etc/default/grub.bak
sed -ri -e 's|^GRUB_CMDLINE_LINUX=.*|GRUB_CMDLINE_LINUX="init=/sbin/init console=tty1"|g' /etc/default/grub
grub-mkconfig -o /boot/grub/grub.cfg

# 9) Prompt to set root password
echo "Set root password (leave empty for keyless login):"
passwd root || true

# 10) Btrfs immutable root layout (assumes /dev/sda2)
ROOT_DEV="/dev/sda2"
mkfs.btrfs -f "$ROOT_DEV"
mount "$ROOT_DEV" /mnt
btrfs subvolume create /mnt/@
btrfs subvolume create /mnt/@home
btrfs subvolume create /mnt/@var
umount /mnt

UUID=$(blkid -s UUID -o value "$ROOT_DEV")
cat > /etc/fstab << 'EOF'
UUID=${UUID}  /      btrfs  subvol=@,defaults,ro,compress=zstd  0 0
UUID=${UUID}  /home  btrfs  subvol=@home,defaults,compress=zstd  0 0
UUID=${UUID}  /var   btrfs  subvol=@var,defaults,compress=zstd   0 0
EOF

# 11) RustPyDE meta-package (PKGBUILD)
mkdir -pv /opt/rustpy-de-core
cat > /opt/rustpy-de-core/PKGBUILD << 'EOF'
pkgname=rustpy-de-core
pkgver=1.0.0
pkgrel=1
pkgdesc="RustPyDE Core: compositor, panel, trays, themes"
arch=('x86_64')
license=('MIT')
depends=(
  "leftwm"
  "alacritty"
  "python-gobject"
  "gtk3"
  "xorg-server-xwayland"
  "sddm"
  "xdg-desktop-portal"
)
source=()
sha256sums=('SKIP')

package() {
  install -Dm755 /opt/initrs/target/release/initrs       "\${pkgdir}/usr/local/bin/initrs"
  install -Dm755 /usr/local/bin/rustpyde-session          "\${pkgdir}/usr/local/bin/rustpyde-session"
  mkdir -p "\${pkgdir}/usr/share/rustpyde"
  cp -r /opt/rustpyde/* "\${pkgdir}/usr/share/rustpyde/"
  install -Dm644 /usr/share/applications/rustpyde-installer.desktop \
                "\${pkgdir}/usr/share/applications/rustpyde-installer.desktop"
}
EOF
cd /opt/rustpy-de-core
makepkg -si --noconfirm

# 12) RustPyDE files
mkdir -pv /opt/rustpyde

# 12.1) rustpyde-session
cat > /usr/local/bin/rustpyde-session << 'EOF'
#!/usr/bin/env bash
export XDG_SESSION_TYPE=wayland
export GDK_BACKEND=wayland
export SDL_VIDEODRIVER=wayland

leftwm &
sleep 2
python3 /usr/local/bin/panel.py &
python3 /usr/local/bin/network_tray.py &
python3 /usr/local/bin/volume_tray.py &
alacritty &
wait
EOF
chmod +x /usr/local/bin/rustpyde-session

# 12.2) panel.py
cat > /usr/local/bin/panel.py << 'EOF'
#!/usr/bin/env python3
import gi, time, subprocess
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject

class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.DOCK)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        screen = self.get_screen()
        monitor = screen.get_primary_monitor()
        geom = screen.get_monitor_geometry(monitor)
        self.set_default_size(geom.width, 24)
        self.move(0, 0)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add(box)

        btn_launcher = Gtk.Button(label="≡")
        btn_launcher.connect("clicked", self.on_launcher_clicked)
        box.pack_start(btn_launcher, False, False, 6)

        self.clock = Gtk.Label(label="")
        box.pack_start(self.clock, True, True, 0)
        GObject.timeout_add_seconds(1, self.update_clock)

        self.network_icon = Gtk.Image()
        box.pack_end(self.network_icon, False, False, 6)

        self.show_all()

    def on_launcher_clicked(self, widget):
        subprocess.Popen(["/usr/local/bin/rustpyde-launcher"])

    def update_clock(self):
        self.clock.set_text(time.strftime("%H:%M:%S"))
        return True

if __name__ == "__main__":
    win = Panel()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
EOF
chmod +x /usr/local/bin/panel.py

# 12.3) network_tray.py
cat > /usr/local/bin/network_tray.py << 'EOF'
#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import subprocess

class NetTray(Gtk.StatusIcon):
    def __init__(self):
        super().__init__()
        self.set_from_icon_name("network-wireless")
        self.connect("activate", self.on_click)
        self.show()

    def on_click(self, icon):
        subprocess.Popen(["nm-connection-editor"])

if __name__ == "__main__":
    Gtk.init(None)
    tray = NetTray()
    Gtk.main()
EOF
chmod +x /usr/local/bin/network_tray.py

# 12.4) volume_tray.py
cat > /usr/local/bin/volume_tray.py << 'EOF'
#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import subprocess

class VolTray(Gtk.StatusIcon):
    def __init__(self):
        super().__init__()
        self.set_from_icon_name("audio-volume-medium")
        self.connect("activate", self.on_click)
        self.show()

    def on_click(self, icon):
        subprocess.Popen(["pavucontrol"])

if __name__ == "__main__":
    Gtk.init(None)
    tray = VolTray()
    Gtk.main()
EOF
chmod +x /usr/local/bin/volume_tray.py

# 12.5) rustpyde-launcher
cat > /usr/local/bin/rustpyde-launcher << 'EOF'
#!/usr/bin/env bash
# Simple dmenu/rofi-based launcher; requires dmenu or rofi installed
if command -v rofi &>/dev/null; then
  rofi -show drun
elif command -v dmenu &>/dev/null; then
  ls /usr/share/applications/*.desktop | sed 's#.*/##;s#\.desktop##' | dmenu | xargs -I{} gtk-launch {}
else
  notify-send "No application launcher found"
fi
EOF
chmod +x /usr/local/bin/rustpyde-launcher

# 13) Graphical installer (installer.py)
cat > /usr/local/bin/installer.py << 'EOF'
#!/usr/bin/env python3
import gi, subprocess, os, sys, threading
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

# Map vendor IDs to driver packages
GPU_DRIVERS = {"10de": "nvidia", "1002": "xf86-video-amdgpu", "8086": "mesa xf86-video-intel"}
WIFI_DRIVERS = {"14e4": "broadcom-wl", "10ec": "rtl88XXau-dkms"}

class Installer(Gtk.Window):
    def __init__(self):
        super().__init__(title="RustPy-Arch Installer")
        self.set_border_width(10)
        self.set_default_size(600, 400)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(500)

        # Pages: network, hardware, packages, finish
        self.page_net = self.create_network_page()
        self.page_hw  = self.create_hardware_page()
        self.page_pkgs= self.create_packages_page()
        self.page_done= self.create_finish_page()

        self.stack.add_titled(self.page_net,  "net",  "Network")
        self.stack.add_titled(self.page_hw,   "hw",   "Drivers")
        self.stack.add_titled(self.page_pkgs, "pkgs", "Packages")
        self.stack.add_titled(self.page_done, "done", "Finish")

        self.add(self.stack)
        self.show_all()

    def next_page(self, _button):
        name = self.stack.get_visible_child_name()
        if name == "net":
            self.stack.set_visible_child_name("hw")
        elif name == "hw":
            self.stack.set_visible_child_name("pkgs")
        elif name == "pkgs":
            self.stack.set_visible_child_name("done")
        else:
            Gtk.main_quit()

    def create_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.pack_start(Gtk.Label(label="Connect to a Network"), False, False, 0)

        self.wifi_store = Gtk.ListStore(str)
        self.scan_wifi()
        self.wifi_combo = Gtk.ComboBox.new_with_model(self.wifi_store)
        renderer = Gtk.CellRendererText()
        self.wifi_combo.pack_start(renderer, True)
        self.wifi_combo.add_attribute(renderer, "text", 0)
        page.pack_start(self.wifi_combo, False, False, 0)

        self.pass_entry = Gtk.Entry()
        self.pass_entry.set_placeholder_text("Wi-Fi Password (if needed)")
        page.pack_start(self.pass_entry, False, False, 0)

        btn_connect = Gtk.Button(label="Connect")
        btn_connect.connect("clicked", self.on_connect_wifi)
        page.pack_start(btn_connect, False, False, 0)

        self.net_status = Gtk.Label(label="")
        page.pack_start(self.net_status, False, False, 0)

        btn_next = Gtk.Button(label="Next")
        btn_next.connect("clicked", self.next_page)
        page.pack_end(btn_next, False, False, 0)
        return page

    def scan_wifi(self):
        self.wifi_store.clear()
        out = subprocess.getoutput("iw dev $(ls /sys/class/net | grep wlan) scan ap-force | grep SSID:")
        ssids = set([line.split("SSID:")[1].strip() for line in out.splitlines() if "SSID:" in line])
        for ssid in ssids:
            self.wifi_store.append([ssid])

    def on_connect_wifi(self, _button):
        ssid = self.wifi_combo.get_active_text()
        pwd  = self.pass_entry.get_text()
        if not ssid:
            self.net_status.set_text("No SSID selected.")
            return
        wpa_conf = subprocess.getoutput(f"wpa_passphrase '{ssid}' '{pwd}'")
        with open("/etc/wpa_supplicant.conf", "w") as f:
            f.write(wpa_conf)
        subprocess.run(["wpa_supplicant", "-B", "-i", "$(ls /sys/class/net | grep wlan)", "-c", "/etc/wpa_supplicant.conf"])
        subprocess.run(["dhcpcd", "$(ls /sys/class/net | grep wlan)"])
        self.net_status.set_text(f"Attempting to connect to {ssid}...")

    def create_hardware_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.pack_start(Gtk.Label(label="Detect & Install Drivers"), False, False, 0)

        self.gpu_label = Gtk.Label(label="GPU: Detecting...")
        page.pack_start(self.gpu_label, False, False, 0)
        self.gpu_check = Gtk.CheckButton(label="Install GPU driver")
        page.pack_start(self.gpu_check, False, False, 0)

        self.wifi_label = Gtk.Label(label="Wi-Fi: Detecting...")
        page.pack_start(self.wifi_label, False, False, 0)
        self.wifi_check = Gtk.CheckButton(label="Install Wi-Fi driver")
        page.pack_start(self.wifi_check, False, False, 0)

        btn_detect = Gtk.Button(label="Detect Hardware")
        btn_detect.connect("clicked", self.on_detect_hw)
        page.pack_start(btn_detect, False, False, 0)

        self.hw_status = Gtk.Label(label="")
        page.pack_start(self.hw_status, False, False, 0)

        btn_install = Gtk.Button(label="Install Selected Drivers")
        btn_install.connect("clicked", self.on_install_drivers)
        page.pack_start(btn_install, False, False, 0)

        btn_next = Gtk.Button(label="Next")
        btn_next.connect("clicked", self.next_page)
        page.pack_end(btn_next, False, False, 0)
        return page

    def on_detect_hw(self, _button):
        out = subprocess.getoutput("lspci -nn | grep -Ei 'VGA'")
        self.gpu_info = out.strip()
        vid = ""
        if "NVIDIA" in out:
            vid = "10de"
        elif "AMD" in out:
            vid = "1002"
        elif "Intel" in out:
            vid = "8086"
        self.gpu_label.set_text(f"GPU Detected: {self.gpu_info}")
        if vid:
            self.gpu_driver = GPU_DRIVERS.get(vid, "")
            self.gpu_check.set_label(f"Install {self.gpu_driver}")
            self.gpu_check.set_active(True)
        else:
            self.gpu_check.set_label("No known GPU driver")
            self.gpu_check.set_active(False)

        out2 = subprocess.getoutput("lspci -nn | grep -i 'Network controller'")
        self.wifi_info = out2.strip()
        vid2 = ""
        for key in WIFI_DRIVERS:
            if key in out2:
                vid2 = key
                break
        self.wifi_label.set_text(f"Wi-Fi Detected: {self.wifi_info}")
        if vid2:
            self.wifi_driver = WIFI_DRIVERS.get(vid2, "")
            self.wifi_check.set_label(f"Install {self.wifi_driver}")
            self.wifi_check.set_active(True)
        else:
            self.wifi_check.set_label("No known Wi-Fi driver")
            self.wifi_check.set_active(False)

    def on_install_drivers(self, _button):
        pkgs = []
        if self.gpu_check.get_active() and hasattr(self, "gpu_driver"):
            pkgs.append(self.gpu_driver)
        if self.wifi_check.get_active() and hasattr(self, "wifi_driver"):
            pkgs.append(self.wifi_driver)
        if pkgs:
            self.hw_status.set_text("Installing: " + ", ".join(pkgs))
            threading.Thread(target=self.run_pacman, args=(pkgs,)).start()
        else:
            self.hw_status.set_text("No drivers selected.")

    def run_pacman(self, pkgs):
        subprocess.run(["pacman", "-Sy", "--noconfirm"] + pkgs)
        subprocess.run(["mkinitcpio", "-P"])
        GObject.idle_add(self.hw_status.set_text, "Drivers installed.")

    def create_packages_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.pack_start(Gtk.Label(label="Select Components to Install"), False, False, 0)

        self.comp_store = Gtk.ListStore(str, bool)
        components = [
            ("rustpy-de-core", "Desktop Environment (RustPyDE)"),
            ("rustpy-gaming", "Gaming (Steam, Wine, Vulkan libs)"),
            ("rustpy-office", "Office (LibreOffice, PDF tools)"),
            ("rustpy-dev", "Development (IDE, compilers, Docker)"),
            ("rustpy-multimedia", "Multimedia (VLC, GIMP, FFmpeg)")
        ]
        for pkg, label in components:
            self.comp_store.append([pkg, False])

        tree = Gtk.TreeView(model=self.comp_store)
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Component", renderer_text, text=0)
        tree.append_column(column_text)
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_component_toggled)
        column_toggle = Gtk.TreeViewColumn("Install", renderer_toggle, active=1)
        tree.append_column(column_toggle)
        page.pack_start(tree, True, True, 0)

        btn_next = Gtk.Button(label="Install & Finish")
        btn_next.connect("clicked", self.on_install_components)
        page.pack_end(btn_next, False, False, 0)
        return page

    def on_component_toggled(self, widget, path):
        self.comp_store[path][1] = not self.comp_store[path][1]

    def on_install_components(self, _button):
        to_install = [row[0] for row in self.comp_store if row[1]]
        if to_install:
            self.stack.set_visible_child_name("done")
            threading.Thread(target=self.run_pacman, args=(to_install,)).start()
        else:
            self.stack.set_visible_child_name("done")

    def create_finish_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.finish_label = Gtk.Label(label="Installing components...")
        page.pack_start(self.finish_label, False, False, 0)
        btn_reboot = Gtk.Button(label="Reboot Now")
        btn_reboot.connect("clicked", self.on_reboot)
        page.pack_end(btn_reboot, False, False, 0)
        return page

    def run_pacman(self, pkgs):
        self.finish_label.set_text("Installing: " + ", ".join(pkgs))
        subprocess.run(["pacman", "-Sy", "--noconfirm"] + pkgs)
        if os.path.exists("/etc/rustpy-install-pending"):
            os.remove("/etc/rustpy-install-pending")
        GObject.idle_add(self.finish_label.set_text, "Installation complete. Click Reboot.")

    def on_reboot(self, _button):
        subprocess.run(["systemctl", "reboot"])

def main():
    Gtk.init(None)
    win = Installer()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
EOF
chmod +x /usr/local/bin/installer.py

# Create installer.desktop for SDDM/autostart
mkdir -pv /usr/share/applications
cat > /usr/share/applications/rustpyde-installer.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=RustPy-Arch Installer
Exec=python3 /usr/local/bin/installer.py
OnlyShowIn=RustPyDE;
EOF

# 14) Meta-packages for Gaming, Office, Dev, Multimedia

# rustpy-gaming
mkdir -pv /opt/rustpy-gaming
cat > /opt/rustpy-gaming/PKGBUILD << 'EOF'
pkgname=rustpy-gaming
pkgver=1.0.0
pkgrel=1
pkgdesc="Gaming components: Steam, Wine, Vulkan, 32-bit libs"
arch=('x86_64')
license=('MIT')
depends=(
  "steam"
  "wine"
  "vulkan-intel"
  "lib32-vulkan-intel"
  "vulkan-amd"
  "lib32-vulkan-amd"
  "dxvk-bin"
)
source=()
sha256sums=('SKIP')
package() { :; }
EOF

# rustpy-office
mkdir -pv /opt/rustpy-office
cat > /opt/rustpy-office/PKGBUILD << 'EOF'
pkgname=rustpy-office
pkgver=1.0.0
pkgrel=1
pkgdesc="Office suite: LibreOffice, PDF tools, printer support"
arch=('x86_64')
license=('MIT')
depends=(
  "libreoffice-fresh"
  "evince"
  "cups"
  "hplip"
)
source=()
sha256sums=('SKIP')
package() { :; }
EOF

# rustpy-dev
mkdir -pv /opt/rustpy-dev
cat > /opt/rustpy-dev/PKGBUILD << 'EOF'
pkgname=rustpy-dev
pkgver=1.0.0
pkgrel=1
pkgdesc="Development tools: compilers, IDEs, Docker, Git"
arch=('x86_64')
license=('MIT')
depends=(
  "base-devel"
  "git"
  "rust"
  "python"
  "docker"
  "code"
  "neovim"
  "cmake"
)
source=()
sha256sums=('SKIP')
package() { :; }
EOF

# rustpy-multimedia
mkdir -pv /opt/rustpy-multimedia
cat > /opt/rustpy-multimedia/PKGBUILD << 'EOF'
pkgname=rustpy-multimedia
pkgver=1.0.0
pkgrel=1
pkgdesc="Multimedia tools: VLC, GIMP, FFmpeg"
arch=('x86_64')
license=('MIT')
depends=(
  "vlc"
  "gimp"
  "ffmpeg"
)
source=()
sha256sums=('SKIP')
package() { :; }
EOF

echo "----"
echo "RustPy-Arch all-in-one bootstrap is complete."
echo "Exit chroot, unmount your partitions, and reboot."
echo "In GRUB, select 'RustPy-Arch'; the Rust init will run the graphical installer."
echo "Follow the GUI to finish setting up networks, drivers, and component selection."

# 15) NOTES & REQUIREMENTS

cat << 'EOF'

────────────────────────────────────────────────────────────────────
 NOTES & REQUIREMENTS
────────────────────────────────────────────────────────────────────

1. HARDWARE & SYSTEM REQUIREMENTS
   • A 64-bit x86_64 PC with UEFI or BIOS  
   • At least 2 GB RAM (4 GB+ recommended for the graphical installer)  
   • A working network connection (Ethernet/Wi-Fi) during installation  
   • A target partition (e.g., /dev/sda2) that will be reformatted as Btrfs  
   • A separate EFI partition (e.g., /dev/sda1) mounted at /boot/efi (not overwritten)  

2. BOOT MEDIA PREPARATION
   a) Download the official Arch Linux ISO (https://archlinux.org/download).  
   b) Write it to a USB stick (or DVD) using one of:  
      • **balenaEtcher** (GUI)  
      • **dd** (CLI):
        ```
        dd if=/path/to/archlinux.iso of=/dev/sdX bs=4M status=progress oflag=sync
        ```
        – Replace **/dev/sdX** with your USB device (e.g., /dev/sdb). Be double-sure not to overwrite your main disk.  

3. DISK & PARTITION SETUP (IN LIVE ENVIRONMENT)
   a) Boot from your freshly-written USB or DVD.  
   b) (Optional) Set your keyboard layout, e.g.:
      ```
      loadkeys us
      ```  
   c) Ensure network connectivity:
      – **Ethernet** is usually automatic.  
      – For **Wi-Fi** (iwctl):
        ```
        iwctl
        > device list
        > station wlan0 connect <SSID>
        > exit
        ```  
   d) Partition the target disk (e.g., /dev/sda):
      ```
      fdisk /dev/sda       # or cfdisk, parted, gdisk, etc.
      ```
      – Create an **EFI partition** (~300 MiB, FAT32) → example: /dev/sda1  
      – Create the **root partition** → example: /dev/sda2 (will become Btrfs)  
      – (Optional) Create a **swap partition** → example: /dev/sda3  
   e) Format & mount:
      ```
      mkfs.fat -F32 /dev/sda1
      mkfs.btrfs /dev/sda2
      mkswap /dev/sda3   # if you created swap
      swapon /dev/sda3
      mount /dev/sda2 /mnt
      mkdir -p /mnt/boot/efi
      mount /dev/sda1 /mnt/boot/efi
      ```  

4. ARCH‐CHROOT INTO /mnt
   a) (Optional) If you want to pre‐install “base” packages first:
      ```
      pacstrap /mnt base
      ```
   b) Enter the new root:
      ```
      arch-chroot /mnt /bin/bash
      ```

5. RUN THE ALL-IN-ONE SCRIPT
````

cp /path/to/rustpy-arch-all-in-one.sh /root/
chmod +x /root/rustpy-arch-all-in-one.sh
/root/rustpy-arch-all-in-one.sh

```
– The script will install Rust init, Rust coreutils, Python installer, Btrfs layout, RustPyDE, and all meta-packages.  
– Wait until it finishes (may take 10–20 minutes, depending on your network speed).

6. EXIT & REBOOT
```

exit
umount -R /mnt
reboot

````
– In the GRUB menu, choose **“RustPy-Arch”**.  

7. FIRST BOOT & GRAPHICAL INSTALLER
• Your system lands in the Rust-based init (PID 1).  
• Because `/etc/rustpy-install-pending` still exists, it launches the **graphical GTK installer** under Xwayland.  
• Follow the installer screens to:
  1. **Connect to network** (Wi-Fi/Ethernet).  
  2. **Detect & install GPU/Wi-Fi drivers** automatically.  
  3. **Select component groups** to install:
     – rustpy-de-core (RustPyDE desktop)  
     – rustpy-gaming (Steam, Wine, Vulkan)  
     – rustpy-office (LibreOffice, PDF tools, printers)  
     – rustpy-dev (IDE, compilers, Docker)  
     – rustpy-multimedia (VLC, GIMP, FFmpeg)  
  4. Click **“Install & Finish”**, then **“Reboot Now.”**  

• After reboot, `/etc/rustpy-install-pending` is removed, and you land in SDDM → select **RustPyDE**.

8. IMMUTABLE BTRFS LAYOUT EXPLAINED
• `/` is mounted read-only on `subvol=@`.  
• `/home` is on `subvol=@home` (writable).  
• `/var` is on `subvol=@var` (writable).  
• To snapshot/rollback:
  ```
  btrfs subvolume snapshot /@ /@backup
  btrfs subvolume set-default <backup-uuid> /
  ```

9. IMMEDIATE POST-INSTALL EXPERIENCE
• **Rust coreutils** replace GNU utilities (`ls, cp, mv, grep, find, cat`).  
• **Python network‐config** lives in `/etc/netconfig.yaml` (edit to hardcode settings).  
• **Rust init** handles the first-boot installer.  
• **Btrfs immutable root** with separate `/home` and `/var`.  
• **SDDM** → **RustPyDE** (LeftWM + GTK panel/trays + Alacritty).  
• **pacman** is available to install anything else.

10. CUSTOMIZATION & UPDATES
 • Edit `/etc/netconfig.yaml` to define static IPs or additional interfaces.  
 • Add or modify `/opt/python-scripts` or `/opt/rustpyde` for custom scripts or themes.  
 • To update uutils or initrs:
   ```
   cd /opt/initrs
   git pull
   cargo build --release
   install -Dm755 target/release/initrs /sbin/init
   ```
 • After kernel updates, run `mkinitcpio -P` if you add new drivers.  

────────────────────────────────────────────────────────────────────
````
~~~
