#!/usr/bin/env python3
"""Praxis Voice Agent Launcher — one-button toggle + dial."""

import os
import subprocess
import sys
import tkinter as tk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
START_CMD = [sys.executable, os.path.join(SCRIPT_DIR, "start-daemons.py")]
STOP_SCRIPT = os.path.join(SCRIPT_DIR, "stop-voice-agent.sh")
LLAMA_PORT = 8099
V2_PORT = 9019
SIP_EXT = "testlive"

# ── Colors ──
GREEN  = "#22c55e"
RED    = "#ef4444"
AMBER  = "#f59e0b"
BLUE   = "#3b82f6"
DARK   = "#1e1e2e"
SURF   = "#313244"
TEXT   = "#cdd6f4"


def _check_ports():
    """Fast port check. Returns (llama_up, v2_up)."""
    llama, v2 = False, False
    try:
        r = subprocess.run(["curl", "-sf", f"http://127.0.0.1:{LLAMA_PORT}/health"],
                           capture_output=True, timeout=2)
        llama = r.returncode == 0
    except Exception:
        pass
    try:
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=2)
        v2 = f":{V2_PORT} " in r.stdout
    except Exception:
        pass
    return llama, v2


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Praxis Voice Agent")
        self.geometry("400x320")
        self.resizable(False, False)
        self.configure(bg=DARK)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 320) // 2
        self.geometry(f"400x320+{x}+{y}")

        self._running = False
        self._busy = False

        self._build_ui()
        self.after(500, self._init_check)

    # ── UI ──

    def _build_ui(self):
        # Header
        tk.Label(self, text="Praxis Voice Agent", font=("Segoe UI", 16, "bold"),
                 bg=DARK, fg=TEXT).pack(pady=(12, 0))
        tk.Label(self, text="Gemma 4 E4B  •  AudioSocket  •  Baresip",
                 font=("Segoe UI", 9), bg=DARK, fg="#6c7086").pack(pady=(0, 8))

        # Status frame
        sf = tk.Frame(self, bg=SURF)
        sf.pack(fill="x", padx=14, pady=8)

        self.llama_dot = tk.Label(sf, text="●", font=("Segoe UI", 14),
                                   bg=SURF, fg="#6c7086")
        self.llama_dot.pack(side="left", padx=(12, 4))
        self.llama_lbl = tk.Label(sf, text="llama-server  :8099",
                                   font=("Segoe UI", 10), bg=SURF, fg="#6c7086")
        self.llama_lbl.pack(side="left")
        tk.Label(sf, text="", bg=SURF).pack()  # line break

        sf2 = tk.Frame(self, bg=SURF)
        sf2.pack(fill="x", padx=14, pady=(0, 2))

        self.v2_dot = tk.Label(sf2, text="●", font=("Segoe UI", 14),
                                bg=SURF, fg="#6c7086")
        self.v2_dot.pack(side="left", padx=(12, 4))
        self.v2_lbl = tk.Label(sf2, text="AudioSocket   :9019",
                                font=("Segoe UI", 10), bg=SURF, fg="#6c7086")
        self.v2_lbl.pack(side="left")

        # Status text
        self.status_lbl = tk.Label(self, text="Starting...", font=("Segoe UI", 9, "italic"),
                                    bg=DARK, fg="#6c7086")
        self.status_lbl.pack(pady=(2, 6))

        # Dial info
        self.dial_lbl = tk.Label(
            self, text=f'Dial:  {SIP_EXT}',
            font=("Segoe UI", 14, "bold"), bg=DARK, fg=GREEN
        )
        self.dial_lbl.pack(pady=(4, 4))
        self.dial_lbl.pack_forget()  # hidden until running

        # Buttons
        bf = tk.Frame(self, bg=DARK)
        bf.pack(fill="x", padx=14, pady=6)

        self.toggle_btn = tk.Button(
            bf, text="▶  Start Servers", font=("Segoe UI", 12, "bold"),
            bg=GREEN, fg="white", activebackground=GREEN, activeforeground="white",
            bd=0, relief="flat", cursor="hand2", height=2,
            command=self._toggle,
        )
        self.toggle_btn.pack(fill="x", ipady=6)

        self.call_btn = tk.Button(
            bf, text="Call", font=("Segoe UI", 11),
            bg=BLUE, fg="white", activebackground=BLUE, activeforeground="white",
            bd=0, relief="flat", cursor="hand2", state="disabled", height=1,
            command=self._dial,
        )
        self.call_btn.pack(fill="x", ipady=4, pady=(6, 0))

        # Footer hint
        tk.Label(
            self, text="Start = launch servers  |  Call = opens baresip + dials",
            font=("Segoe UI", 8), bg=DARK, fg="#45475a"
        ).pack(side="bottom", pady=(0, 6))

    # ── Logic ──

    def _init_check(self):
        """Check initial state — if servers are already up, show as running."""
        llama_up, v2_up = _check_ports()
        if llama_up and v2_up:
            self._running = True
            self._update_ui_state(True)
        else:
            self._update_ui_state(False)
        self.status_lbl.configure(text="Ready")

    def _update_ui_state(self, running: bool):
        if running:
            self.llama_dot.configure(fg=GREEN)
            self.v2_dot.configure(fg=GREEN)
            self.llama_lbl.configure(fg=TEXT)
            self.v2_lbl.configure(fg=TEXT)
            self.toggle_btn.configure(text="■  Stop Servers", bg=RED, activebackground=RED)
            self.call_btn.configure(state="normal")
            self.dial_lbl.pack(before=self.toggle_btn.master, pady=(4, 4))
            self.status_lbl.configure(text="Running", fg=GREEN)
        else:
            self.llama_dot.configure(fg="#6c7086")
            self.v2_dot.configure(fg="#6c7086")
            self.llama_lbl.configure(fg="#6c7086")
            self.v2_lbl.configure(fg="#6c7086")
            self.toggle_btn.configure(text="▶  Start Servers", bg=GREEN, activebackground=GREEN)
            self.call_btn.configure(state="disabled")
            self.dial_lbl.pack_forget()
            self.status_lbl.configure(text="Stopped", fg="#6c7086")

    def _toggle(self):
        if self._busy:
            return
        self._busy = True
        self.toggle_btn.configure(state="disabled")

        if self._running:
            self._do_stop()
        else:
            self._do_start()

    def _do_start(self):
        self.status_lbl.configure(text="Starting...", fg=AMBER)
        self.update_idletasks()

        # Run synchronously on main thread (blocks UI briefly but is reliable)
        result = subprocess.run(START_CMD, capture_output=True, text=True, timeout=60)
        ok = result.returncode == 0

        # Verify
        if ok:
            llama_up, v2_up = _check_ports()
            ok = llama_up and v2_up

        if ok:
            self._running = True
            self._update_ui_state(True)
        else:
            self._update_ui_state(False)
            self.status_lbl.configure(text="Start failed!", fg=RED)

        self.toggle_btn.configure(state="normal")
        self._busy = False

    def _do_stop(self):
        self.status_lbl.configure(text="Stopping...", fg=AMBER)
        self.update_idletasks()

        subprocess.run(["bash", STOP_SCRIPT], capture_output=True, timeout=15)

        # Verify
        llama_up, v2_up = _check_ports()
        if not llama_up and not v2_up:
            self._running = False
            self._update_ui_state(False)
        else:
            self.status_lbl.configure(text="Stop incomplete — check ports", fg=AMBER)

        self.toggle_btn.configure(state="normal")
        self._busy = False

    def _dial(self):
        """Open baresip with auto-dial."""
        # Use bash -c to avoid quoting headaches across terminal emulators
        cmd = "baresip -e '/dial testlive'"
        # Try multiple terminal emulators
        for term_args in [
            ["gnome-terminal", "--", "bash", "-c", f"{cmd}; exec bash"],
            ["xterm", "-hold", "-e", "bash", "-c", cmd],
            ["xfce4-terminal", "-e", f"bash -c '{cmd}; exec bash'"],
        ]:
            try:
                subprocess.Popen(term_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
        import tkinter.messagebox as mb
        mb.showinfo("Dial manually",
                    f"Open a terminal and run:\n\n  {cmd}")


if __name__ == "__main__":
    Launcher().mainloop()
