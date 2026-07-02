#!/usr/bin/env python3
"""

Config:
    Windows:  %APPDATA%\\Proxify\\config.json
    Linux:    ~/.config/Proxify/config.json

"""

import os
import sys
import json
import glob
import shutil
import tempfile
import webbrowser
import subprocess
from urllib.parse import urlparse

import urllib3
import requests
import tkinter as tk
from tkinter import ttk, messagebox

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

__version__ = "1.0.0"

VERIFY_SSL = False     # Proxmox self-signed -> False

# ---------------- Proxmox theme (orange / dark) ----------------
BG       = "#16191c"
SURFACE  = "#212529"
HEADER   = "#0e1113"
ELEV     = "#2a2f34"
BORDER   = "#2e3338"
WHITE    = "#e8eaed"
SUBTEXT  = "#9aa0a6"
MUTED    = "#6b7177"
ICON_OFF = "#4d5358"   # icon color when guest is down
ORANGE   = "#e57000"   # Proxmox accent
ORANGE_HV= "#ff8a1f"
DOT_RED  = "#ff5f57"
DOT_YEL  = "#febc2e"
DOT_GRN  = "#28c840"
if sys.platform == "darwin":
    FONT = "Helvetica Neue"
elif sys.platform == "win32":
    FONT = "Segoe UI"
else:
    FONT = "Sans"
# ---------------------------------------------------------------

# ---- icon bitmaps ('#' = pixel, ' ' = transparent) ----
P_VM = [
    "                ",
    "  ############  ",
    "  #          #  ",
    "  #          #  ",
    "  #          #  ",
    "  #          #  ",
    "  #          #  ",
    "  #          #  ",
    "  ############  ",
    "       ##       ",
    "     ######     ",
    "   ##########   ",
    "                ",
    "                ",
]
P_CT = [
    "                ",
    "  ############  ",
    "  #          #  ",
    "  ############  ",
    "  #          #  ",
    "  ############  ",
    "  #          #  ",
    "  ############  ",
    "  #          #  ",
    "  ############  ",
    "                ",
    "                ",
    "                ",
    "                ",
]
P_USER = [
    "              ",
    "     ####     ",
    "    ######    ",
    "    ######    ",
    "    ######    ",
    "     ####     ",
    "              ",
    "   ########   ",
    "  ##########  ",
    " ############ ",
    " ############ ",
    "              ",
    "              ",
    "              ",
]


def make_icon(pattern, color):
    h, w = len(pattern), len(pattern[0])
    img = tk.PhotoImage(width=w, height=h)
    for y, row in enumerate(pattern):
        for x, ch in enumerate(row):
            if ch != " ":
                img.put(color, (x, y))
    return img


def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(base, "Proxify")
    os.makedirs(d, exist_ok=True)
    return d


class Config:
    def __init__(self):
        self.path = os.path.join(config_dir(), "config.json")
        self.data = {"accounts": [], "last": 0}
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            pass
        self.data.setdefault("accounts", [])
        self.data.setdefault("last", 0)

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            if os.name != "nt":
                os.chmod(self.path, 0o600)
        except Exception as e:
            print(f"Could not save config: {e}")

    def accounts(self):
        return self.data["accounts"]

    def add_account(self, host, user, pw):
        for i, a in enumerate(self.data["accounts"]):
            if a["host"] == host and a["user"] == user:
                a["password"] = pw
                self.data["last"] = i
                self.save()
                return i
        self.data["accounts"].append({"host": host, "user": user, "password": pw})
        self.data["last"] = len(self.data["accounts"]) - 1
        self.save()
        return self.data["last"]


class Proxmox:
    def __init__(self, host, user, password):
        self.host = host.rstrip("/")
        self.proxy_host = urlparse(self.host).hostname
        self.s = requests.Session()
        self.s.verify = VERIFY_SSL
        r = self.s.post(f"{self.host}/api2/json/access/ticket",
                        data={"username": user, "password": password}, timeout=10)
        r.raise_for_status()
        d = r.json()["data"]
        self.s.cookies.set("PVEAuthCookie", d["ticket"])
        self.csrf = d["CSRFPreventionToken"]

    def get(self, path):
        r = self.s.get(f"{self.host}/api2/json{path}", timeout=10)
        r.raise_for_status()
        return r.json()["data"]

    def post(self, path, data=None):
        r = self.s.post(f"{self.host}/api2/json{path}", data=data or {},
                        headers={"CSRFPreventionToken": self.csrf}, timeout=15)
        r.raise_for_status()
        return r.json()["data"]

    def list_guests(self):
        out = []
        for node in self.get("/nodes"):
            n = node["node"]
            for vm in self.get(f"/nodes/{n}/qemu"):
                out.append({"node": n, "vmid": vm["vmid"], "type": "qemu",
                            "name": vm.get("name", f"vm{vm['vmid']}"),
                            "status": vm.get("status", "?")})
            for ct in self.get(f"/nodes/{n}/lxc"):
                out.append({"node": n, "vmid": ct["vmid"], "type": "lxc",
                            "name": ct.get("name", f"ct{ct['vmid']}"),
                            "status": ct.get("status", "?")})
        return sorted(out, key=lambda v: int(v["vmid"]))

    def spice(self, node, vmid):
        return self.post(f"/nodes/{node}/qemu/{vmid}/spiceproxy",
                         data={"proxy": self.proxy_host})

    def console_url(self, node, vmid, name):
        return (f"{self.host}/?console=lxc&xtermjs=1"
                f"&vmid={vmid}&vmname={name}&node={node}&resize=scale&cmd=")

    def start(self, node, vmid, vtype):
        return self.post(f"/nodes/{node}/{vtype}/{vmid}/status/start")


def find_remote_viewer():
    exe = shutil.which("remote-viewer")
    if exe:
        return exe
    cands = []
    if sys.platform == "darwin":
        cands += ["/opt/homebrew/bin/remote-viewer",   # Homebrew (Apple Silicon)
                  "/usr/local/bin/remote-viewer",       # Homebrew (Intel)
                  "/opt/local/bin/remote-viewer"]       # MacPorts
        cands += glob.glob("/Applications/*emote*iewer*.app/Contents/MacOS/*")
    elif os.name == "nt":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            if base:
                cands += glob.glob(os.path.join(base, "VirtViewer*", "bin", "remote-viewer.exe"))
    for c in cands:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def launch_spice(spice_data):
    viewer = find_remote_viewer()
    if not viewer:
        raise RuntimeError(
            "remote-viewer (SPICE client) not found. Install one:\n"
            "  Linux:    pacman -S virt-viewer  (or apt/dnf/zypper)\n"
            "  Windows:  virt-manager.org\n"
            "  macOS:    brew install --cask remoteviewer\n"
            "            (or MacPorts: sudo port install virt-viewer)")
    fd, path = tempfile.mkstemp(suffix=".vv")
    with os.fdopen(fd, "w") as f:
        f.write("[virt-viewer]\n")
        for k, v in spice_data.items():
            val = str(v).replace("\n", "\\n")
            f.write(f"{k}={val}\n")
    try:
        proc = subprocess.Popen([viewer, path], stderr=subprocess.PIPE,
                                stdout=subprocess.DEVNULL)
    except OSError as e:
        raise RuntimeError(f"Could not launch remote-viewer:\n{e}")
    # A broken client (e.g. missing Homebrew deps) exits within milliseconds;
    # report that instead of silently pretending SPICE started.
    try:
        rc = proc.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        return  # still running -> the viewer window is up
    err = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
    raise RuntimeError(
        f"remote-viewer exited immediately (exit code {rc}).\n"
        f"The SPICE client seems broken. Try reinstalling it:\n"
        f"  macOS:  brew reinstall virt-viewer\n"
        + (f"\n{err[:400]}" if err else ""))


def hover_button(parent, text, command, bg, hover, fg=BG, pad=(16, 8),
                 image=None, bold=True):
    font = (FONT, 10, "bold") if bold else (FONT, 10)
    opts = dict(text=text, bg=bg, fg=fg, padx=pad[0], pady=pad[1],
                font=font, cursor="hand2", disabledforeground=MUTED)
    if image is not None:
        opts["image"] = image
        opts["compound"] = "left"
    if sys.platform == "darwin":
        # The native Aqua tk.Button ignores bg/relief and always renders as a
        # solid white rounded button, so style a tk.Label as a button instead.
        b = tk.Label(parent, **opts)
        b.bind("<Button-1>",
               lambda e: command() if str(b["state"]) != "disabled" else None)
    else:
        b = tk.Button(parent, command=command, relief="flat", bd=0,
                      activebackground=hover, activeforeground=fg, **opts)
    b.bind("<Enter>", lambda e: b.config(bg=hover) if str(b["state"]) != "disabled" else None)
    b.bind("<Leave>", lambda e: b.config(bg=bg) if str(b["state"]) != "disabled" else None)
    return b


class Proxify(tk.Tk):
    def __init__(self):
        super().__init__(className="Proxify")
        self.title("Proxify")
        self.cfg = Config()
        self.pve = None
        self.account_label = ""
        self._minimized = False
        self._maxed = False

        # Frameless (custom titlebar + traffic lights) only where it works well:
        # Windows and Linux/X11. On macOS the native window already has real
        # traffic lights, and on Wayland a borderless window can't take focus.
        self._frameless = (
            sys.platform == "win32"
            or (sys.platform.startswith("linux") and not os.environ.get("WAYLAND_DISPLAY"))
        )
        if os.environ.get("PROXIFY_NO_FRAMELESS"):
            self._frameless = False
        if self._frameless:
            self.overrideredirect(True)
        self.configure(bg=BG)
        self._center()
        self.bind("<Map>", self._on_map)
        self.after(80, self._take_focus)
        self._style()
        self._build_icons()
        self._titlebar(with_controls=self._frameless)

        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.show_login()

    # ---------- icons ----------
    def _build_icons(self):
        self.icons = {
            "vm_up":   make_icon(P_VM, WHITE),
            "vm_down": make_icon(P_VM, ICON_OFF),
            "ct_up":   make_icon(P_CT, WHITE),
            "ct_down": make_icon(P_CT, ICON_OFF),
            "user":    make_icon(P_USER, "#cfd3d7"),
        }

    # ---------- window frame / controls ----------
    def _center(self):
        self.update_idletasks()
        w, h = 700, 580
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _titlebar(self, with_controls=True):
        bar = tk.Frame(self, bg=HEADER, height=42)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        if with_controls:
            c = tk.Canvas(bar, width=64, height=24, bg=HEADER, highlightthickness=0)
            c.pack(side="left", padx=(14, 12))
            dots = [(DOT_RED, "\u00d7", self._close),
                    (DOT_YEL, "\u2013", self._minimize),
                    (DOT_GRN, "+", self._toggle_max)]
            self._glyphs = []
            for i, (col, gly, cmd) in enumerate(dots):
                x = 2 + i * 20
                oid = c.create_oval(x, 6, x + 13, 19, fill=col, outline="")
                tid = c.create_text(x + 7, 12, text=gly, fill="#1a1a1a",
                                    font=(FONT, 8, "bold"), state="hidden")
                c.tag_bind(oid, "<Button-1>", lambda e, f=cmd: f())
                c.tag_bind(tid, "<Button-1>", lambda e, f=cmd: f())
                self._glyphs.append(tid)
            c.bind("<Enter>", lambda e: [c.itemconfig(g, state="normal") for g in self._glyphs])
            c.bind("<Leave>", lambda e: [c.itemconfig(g, state="hidden") for g in self._glyphs])
        else:
            # native window already provides controls; just pad the wordmark
            tk.Frame(bar, bg=HEADER, width=14).pack(side="left")

        # multi-color title:  Pro (white) x (orange) ify (white)
        parts = [("Pro", WHITE), ("x", ORANGE), ("ify", WHITE)]
        movers = [bar]
        for txt, col in parts:
            lbl = tk.Label(bar, text=txt, bg=HEADER, fg=col,
                           font=(FONT, 12, "bold"), padx=0, bd=0)
            lbl.pack(side="left")
            movers.append(lbl)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        if with_controls:
            for w in movers:
                w.bind("<Button-1>", self._start_move)
                w.bind("<B1-Motion>", self._do_move)
                w.bind("<Double-Button-1>", lambda e: self._toggle_max())

    def _start_move(self, e):
        self._ox = self.winfo_pointerx() - self.winfo_x()
        self._oy = self.winfo_pointery() - self.winfo_y()

    def _do_move(self, e):
        self.geometry(f"+{self.winfo_pointerx() - self._ox}+{self.winfo_pointery() - self._oy}")

    def _close(self):
        self.destroy()

    def _take_focus(self):
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _minimize(self):
        if self._frameless:
            self._minimized = True
            self.overrideredirect(False)
        self.iconify()

    def _on_map(self, e):
        if self._minimized:
            self._minimized = False
            self.overrideredirect(True)
        if self._frameless:
            self.after(50, self._take_focus)

    def _toggle_max(self):
        if self._maxed:
            self.geometry(self._normgeo)
            self._maxed = False
        else:
            self._normgeo = self.geometry()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{sw}x{sh - 48}+0+0")
            self._maxed = True

    # ---------- ttk style ----------
    def _style(self):
        st = ttk.Style()
        st.theme_use("clam")
        st.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                     foreground=WHITE, rowheight=32, borderwidth=0, font=(FONT, 10))
        st.configure("Treeview.Heading", background=HEADER, foreground=ORANGE,
                     font=(FONT, 10, "bold"), borderwidth=0, relief="flat")
        st.map("Treeview.Heading", background=[("active", ELEV)])
        st.map("Treeview", background=[("selected", ORANGE)], foreground=[("selected", BG)])

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    # ---------- login view ----------
    def _field(self, parent, label, show=""):
        tk.Label(parent, text=label, bg=BG, fg=SUBTEXT, font=(FONT, 9)).pack(anchor="w")
        e = tk.Entry(parent, show=show, bg=SURFACE, fg=WHITE, insertbackground=WHITE,
                     relief="flat", font=(FONT, 11), highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ORANGE)
        e.pack(fill="x", ipady=6, pady=(3, 12))
        return e

    def show_login(self, add_new=False):
        self._clear()
        f = tk.Frame(self.body, bg=BG)
        f.pack(fill="both", expand=True, padx=30, pady=24)

        tk.Label(f, text="Add user" if add_new else "Sign in", bg=BG, fg=WHITE,
                 font=(FONT, 16, "bold")).pack(anchor="w")
        tk.Label(f, text="Connect to your Proxmox server", bg=BG, fg=SUBTEXT,
                 font=(FONT, 9)).pack(anchor="w", pady=(0, 18))

        accs = self.cfg.accounts()
        self.sel_var = tk.StringVar()
        if accs and not add_new:
            tk.Label(f, text="Saved account", bg=BG, fg=SUBTEXT, font=(FONT, 9)).pack(anchor="w")
            labels = [self._acc_label(a) for a in accs]
            om = tk.OptionMenu(f, self.sel_var, *labels, command=self._fill_from_saved)
            om.config(bg=SURFACE, fg=WHITE, activebackground=ELEV, activeforeground=WHITE,
                      relief="flat", highlightthickness=1, highlightbackground=BORDER,
                      font=(FONT, 10), anchor="w", cursor="hand2")
            om["menu"].config(bg=SURFACE, fg=WHITE, activebackground=ORANGE,
                              activeforeground=BG, relief="flat", bd=0)
            om.pack(fill="x", pady=(3, 14))

        self.e_host = self._field(f, "Host  (e.g. https://192.168.1.180:8006)")
        self.e_user = self._field(f, "User  (e.g. root@pam)")
        self.e_pass = self._field(f, "Password", show="*")

        self.save_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="Save credentials", variable=self.save_var,
                       bg=BG, fg=SUBTEXT, activebackground=BG, activeforeground=WHITE,
                       selectcolor=SURFACE, font=(FONT, 10), bd=0,
                       highlightthickness=0, cursor="hand2").pack(anchor="w", pady=(0, 16))

        hover_button(f, "Connect", self._do_login, ORANGE, ORANGE_HV).pack(anchor="w")

        if add_new and self.pve is not None:
            hover_button(f, "Cancel", self.show_main, ELEV, BORDER, fg=WHITE,
                         pad=(14, 8)).pack(anchor="w", pady=(8, 0))

        self.login_msg = tk.Label(f, text="", bg=BG, fg=DOT_RED, font=(FONT, 9),
                                  wraplength=600, justify="left")
        self.login_msg.pack(anchor="w", pady=(12, 0))

        last = self.cfg.data.get("last", 0)
        if accs and not add_new and 0 <= last < len(accs):
            self._fill_fields(accs[last])
            self.sel_var.set(self._acc_label(accs[last]))
        self.e_pass.bind("<Return>", lambda e: self._do_login())
        self.after(120, self.e_host.focus_set)

    def _acc_label(self, a):
        return f'{a["user"]} @ {urlparse(a["host"]).hostname}'

    def _fill_fields(self, a):
        for e, v in ((self.e_host, a["host"]), (self.e_user, a["user"]), (self.e_pass, a["password"])):
            e.delete(0, "end")
            e.insert(0, v)

    def _fill_from_saved(self, label):
        for a in self.cfg.accounts():
            if self._acc_label(a) == label:
                self._fill_fields(a)
                break

    def _do_login(self):
        host = self.e_host.get().strip()
        user = self.e_user.get().strip()
        pw = self.e_pass.get()
        if not (host and user and pw):
            self.login_msg.config(text="Please fill in host, user and password.", fg=DOT_RED)
            return
        if "@" not in user:            # no realm given -> assume PAM
            user += "@pam"
        if not host.startswith("http"):
            host = "https://" + host
        self.login_msg.config(text="Connecting ...", fg=SUBTEXT)
        self.update_idletasks()
        try:
            pve = Proxmox(host, user, pw)
        except Exception as e:
            self.login_msg.config(text=f"Login failed: {e}", fg=DOT_RED)
            return
        self.pve = pve
        if self.save_var.get():
            self.cfg.add_account(host, user, pw)
        self.account_label = self._acc_label({"host": host, "user": user})
        self.show_main()

    # ---------- main view ----------
    def show_main(self):
        self._clear()

        top = tk.Frame(self.body, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(top, text=urlparse(self.pve.host).hostname, bg=BG, fg=SUBTEXT,
                 font=(FONT, 10)).pack(side="left")
        hover_button(top, "Web UI", self._open_webui, ELEV, BORDER, fg=SUBTEXT,
                     pad=(10, 5)).pack(side="left", padx=(10, 0))
        self.user_chip = hover_button(
            top, "  " + self.account_label + "   \u25be", self._open_user_menu,
            ELEV, BORDER, fg=WHITE, pad=(10, 5),
            image=self.icons["user"], bold=False)
        self.user_chip.pack(side="right")

        search_row = tk.Frame(self.body, bg=BG)
        search_row.pack(fill="x", padx=16, pady=(4, 0))
        box = tk.Frame(search_row, bg=SURFACE, highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=ORANGE)
        box.pack(fill="x")
        tk.Label(box, text="\U0001f50d", bg=SURFACE, fg=MUTED,
                 font=(FONT, 11)).pack(side="left", padx=(10, 4))
        self.search_entry = tk.Entry(box, bg=SURFACE, fg=WHITE,
                                     insertbackground=WHITE, relief="flat",
                                     font=(FONT, 11), highlightthickness=0, bd=0)
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=6)
        self._search_ph = "Search VMs and CTs by name, ID or status …"
        self._clear_x = tk.Label(box, text="✕", bg=SURFACE, fg=MUTED,
                                 font=(FONT, 10), cursor="hand2")
        self._clear_x.bind("<Button-1>", lambda e: self._clear_search())
        self._set_placeholder()
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filter())

        wrap = tk.Frame(self.body, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(wrap, columns=("vmid", "name", "status"),
                                 show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=50, anchor="center", stretch=False)
        for c, txt, w in (("vmid", "ID", 70), ("name", "NAME", 320), ("status", "STATUS", 110)):
            self.tree.heading(c, text=txt)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=2, pady=2)
        self.tree.bind("<Double-1>", lambda e: self.connect())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_start_btn())
        self.tree.tag_configure("up", foreground=WHITE)
        self.tree.tag_configure("down", foreground=MUTED)

        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", padx=16, pady=12)
        hover_button(bar, "Connect", self.connect, ORANGE, ORANGE_HV).pack(side="left")
        self.start_btn = hover_button(bar, "Start", self.do_start, ELEV, BORDER, fg=WHITE)
        self.start_btn.pack(side="left", padx=8)
        hover_button(bar, "Refresh", self.refresh, ELEV, BORDER, fg=WHITE).pack(side="right")
        self._update_start_btn()

        self.status = tk.Label(self.body, text="", bg=HEADER, fg=SUBTEXT, anchor="w",
                               font=(FONT, 9), padx=12, pady=6)
        self.status.pack(fill="x", side="bottom")
        self.refresh()

    def _open_user_menu(self):
        m = tk.Menu(self, tearoff=0, bg=SURFACE, fg=WHITE,
                    activebackground=ORANGE, activeforeground=BG, bd=0, relief="flat")
        m.add_command(label="  " + self.account_label, image=self.icons["user"],
                      compound="left", state="disabled")
        m.add_separator()
        for i, a in enumerate(self.cfg.accounts()):
            if self._acc_label(a) == self.account_label:
                continue
            m.add_command(label="  Switch to " + self._acc_label(a),
                          command=lambda i=i: self._switch_to(i))
        m.add_command(label="  + New user", command=lambda: self.show_login(add_new=True))
        m.add_separator()
        m.add_command(label="  Log out", command=self.logout, foreground=DOT_RED,
                      activeforeground=WHITE, activebackground=DOT_RED)
        x = self.user_chip.winfo_rootx()
        y = self.user_chip.winfo_rooty() + self.user_chip.winfo_height() + 2
        m.tk_popup(x, y)

    def _switch_to(self, i):
        a = self.cfg.accounts()[i]
        try:
            pve = Proxmox(a["host"], a["user"], a["password"])
        except Exception as e:
            messagebox.showerror("Login failed", str(e))
            return
        self.pve = pve
        self.cfg.data["last"] = i
        self.cfg.save()
        self.account_label = self._acc_label(a)
        self.show_main()

    def _msg(self, t):
        self.status.config(text=t)

    # ---------- search ----------
    def _set_placeholder(self):
        self._search_active = False
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, self._search_ph)
        self.search_entry.config(fg=MUTED)
        self._clear_x.pack_forget()

    def _search_focus_in(self, e):
        if not self._search_active:
            self._search_active = True
            self.search_entry.delete(0, "end")
            self.search_entry.config(fg=WHITE)
            self._apply_filter()

    def _search_focus_out(self, e):
        if not self.search_entry.get():
            self._set_placeholder()
            self._apply_filter()

    def _clear_search(self):
        self._search_active = True
        self.search_entry.delete(0, "end")
        self.search_entry.config(fg=WHITE)
        self.search_entry.focus_set()
        self._apply_filter()

    def _query(self):
        if not getattr(self, "_search_active", False):
            return ""
        return self.search_entry.get().strip().lower()

    def refresh(self):
        try:
            self.guests = self.pve.list_guests()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._apply_filter()

    def _apply_filter(self):
        if not hasattr(self, "guests"):
            return
        q = self._query()
        self._clear_x.pack(side="right", padx=(4, 10)) if q else self._clear_x.pack_forget()

        def match(g):
            kind = "vm qemu" if g["type"] == "qemu" else "ct lxc container"
            hay = f"{g['vmid']} {g['name']} {g['status']} {kind}".lower()
            return all(tok in hay for tok in q.split())

        shown = [g for g in self.guests if match(g)]
        self.tree.delete(*self.tree.get_children())
        for g in shown:
            up = g["status"] == "running"
            kind = "vm" if g["type"] == "qemu" else "ct"
            icon = self.icons[f"{kind}_{'up' if up else 'down'}"]
            self.tree.insert("", "end", iid=f"{g['node']}:{g['type']}:{g['vmid']}",
                             text="", image=icon,
                             values=(g["vmid"], g["name"], g["status"]),
                             tags=("up" if up else "down",))
        self._update_start_btn()
        vms = sum(1 for g in self.guests if g["type"] == "qemu")
        cts = len(self.guests) - vms
        base = f"{len(self.guests)} guests  ({vms} VMs, {cts} CTs)"
        self._msg(f"{len(shown)} of {base}" if q else base)

    # ---------- start button state ----------
    def _update_start_btn(self):
        sel = self.tree.selection()
        running = bool(sel) and self.tree.item(sel[0], "values")[2] == "running"
        self._set_start_enabled(bool(sel) and not running)

    def _set_start_enabled(self, enabled):
        if enabled:
            self.start_btn.config(state="normal", bg=ELEV, fg=WHITE, cursor="hand2")
        else:
            self.start_btn.config(state="disabled", bg=SURFACE, fg=MUTED, cursor="arrow")

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            self._msg("Select an entry first.")
            return None
        node, vtype, vmid = sel[0].split(":")
        name = self.tree.item(sel[0], "values")[1]
        return node, vtype, vmid, name

    def _open_webui(self):
        webbrowser.open(self.pve.host)
        self._msg("Web UI opened \u2013 log in there once, then CT consoles work.")

    def connect(self):
        s = self._selected()
        if not s:
            return
        node, vtype, vmid, name = s
        try:
            if vtype == "qemu":
                launch_spice(self.pve.spice(node, vmid))
                self._msg(f"SPICE started: {name} ({vmid})")
            else:
                webbrowser.open(self.pve.console_url(node, vmid, name))
                self._msg(f"Console opened: {name} ({vmid}). If it says \"401 No ticket\", "
                          f"click \"Web UI\" and log in once.")
        except Exception as e:
            messagebox.showerror("Connection error", str(e))

    def do_start(self):
        s = self._selected()
        if not s:
            return
        node, vtype, vmid, name = s
        try:
            self.pve.start(node, vmid, vtype)
            self._msg(f"Starting {name} ({vmid}) ...")
            self.after(1500, self.refresh)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def logout(self):
        self.pve = None
        self.show_login()


if __name__ == "__main__":
    Proxify().mainloop()