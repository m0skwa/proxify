<p align="center">
  <img src="proxify.svg" alt="Proxify" width="120">
</p>

<h1 align="center">Proxify</h1>

A lightweight, cross-platform desktop client for Proxmox VE built with Python and Tkinter.
Proxify allows you to quickly monitor your virtual machines (QEMU) and containers (LXC), start offline guests, and establish remote connections directly from your desktop without needing to keep the heavy web UI open.

## Features

* **Multi-Account Support:** Save and easily switch between multiple Proxmox server credentials locally.
* **Live Monitoring:** View the current status of all your VMs and LXC containers.
* **Direct Connections:** Launch direct SPICE sessions for VMs or open web consoles for containers.
* **Power Management:** Start offline guests directly from the app.

---

## Installation & Usage

### Windows

You can run Proxify without installing Python by using the pre-compiled executable.

1. **Download Proxify:** [Download the latest Proxify Version](https://github.com/m0skwa/proxify/releases/latest/download/Proxify-1.0.0.exe)
2. **Install virt-viewer (Required for VM SPICE connections):** Download and install the Windows client from [virt-manager.org](https://virt-manager.org/download).

### Linux

Install the dependencies for your distribution:

**Arch / Manjaro**
```bash
sudo pacman -S --needed base-devel git python python-requests tk virt-viewer
```

**Debian / Ubuntu**
```bash
sudo apt install build-essential git python3 python3-requests python3-tk virt-viewer
```

**Fedora**
```bash
sudo dnf install @development-tools git python3 python3-requests python3-tkinter virt-viewer
```

**openSUSE**
```bash
sudo zypper install -t pattern devel_basis
sudo zypper install git python3 python3-requests python3-tk virt-viewer
```

Then clone the repository and launch Proxify:
```bash
git clone https://github.com/m0skwa/proxify.git
cd proxify
makepkg -si
```

### macOS

**Option A — Install the app (recommended):**

1. **Download Proxify:** [Download the latest Proxify.dmg](https://github.com/m0skwa/proxify/releases/latest/download/Proxify-1.0.0.dmg)
2. Open the `.dmg` and drag **Proxify** into **Applications**.
3. **Install a SPICE client (required for VM connections):**
   ```bash
   brew install --cask remote-viewer
   ```

> The app is not notarized yet, so on first launch macOS Gatekeeper will block it.
> Right-click **Proxify.app → Open → Open** (only needed once).

**Option B — Run from source:**

```bash
brew install python-tk
brew install --cask remote-viewer   # SPICE client, needed for VM connections
git clone https://github.com/m0skwa/proxify.git
cd proxify
pip3 install requests
python3 proxify.py
```

**Option C — Build the app and .dmg yourself:**

```bash
brew install python-tk
git clone https://github.com/m0skwa/proxify.git
cd proxify
./build-macos.sh          # -> dist/Proxify.app  and  Proxify-<version>.dmg
```

On macOS the app uses the native window (with the real traffic-light controls).

### AUR (coming soon)

Proxify will be available directly from the AUR:
```bash
yay -S proxify
```

---

## Configuration

Credentials are stored locally:

* Linux: `~/.config/Proxify/config.json`
* Windows: `%APPDATA%\Proxify\config.json`

On first launch you enter host, user and password. If you leave out the realm (e.g. just `root`), `@pam` is assumed. Use the user menu (top right) to switch between saved accounts, add a new one, or log out.

> Note: SPICE only works for VMs (QEMU). Containers have no SPICE display, so the browser console is used instead. Passwords are stored in plaintext (file mode `600` on Linux).

## License

MIT
