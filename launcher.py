#!/usr/bin/env python3
"""Praxis Voice Agent Launcher — single-window Start/Stop/Call GUI."""

import os
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
START_SCRIPT = os.path.join(SCRIPT_DIR, "start-daemons.py")
STOP_SCRIPT = os.path.join(SCRIPT_DIR, "stop-voice-agent.sh")

LLAMA_PORT = 8099
V2_PORT = 9019


class VoiceAgentLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Praxis Voice Agent")
        self.geometry("380x280")
        self.resizable(False, False)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 380) // 2
        y = (self.winfo_screenheight() - 280) // 2
        self.geometry(f"380x280+{x}+{y}")

        # Colors (Catppuccin Mocha)
        self.GREEN = "#22c55e"
        self.RED = "#ef4444"
        self.AMBER = "#f59e0b"
        self.DARK = "#1e1e2e"
        self.SURFACE = "#313244"
        self.TEXT = "#cdd6f4"

        self.configure(bg=self.DARK)
        self._running = False

        self._build_ui()
        self.after(200, self._refresh_status)

    def _build_ui(self):
        # Header
        tk.Label(
            self, text="Praxis Voice Agent",
            font=("Segoe UI", 16, "bold"),
            bg=self.DARK, fg=self.TEXT
        ).pack(pady=(12, 0))

        tk.Label(
            self, text="Gemma 4 E4B  •  AudioSocket  •  Baresip",
            font=("Segoe UI", 9),
            bg=self.DARK, fg="#6c7086"
        ).pack(pady=(2, 8))

        # Status indicators frame
        status_frame = tk.Frame(self, bg=self.SURFACE)
        status_frame.pack(fill="x", padx=16, pady=8)

        self.llama_label = tk.Label(
            status_frame, text="●  llama-server (:8099)",
            font=("Segoe UI", 10),
            bg=self.SURFACE, fg="#6c7086"
        )
        self.llama_label.pack(anchor="w", padx=12, pady=(8, 2))

        self.v2_label = tk.Label(
            status_frame, text="●  AudioSocket  (:9019)",
            font=("Segoe UI", 10),
            bg=self.SURFACE, fg="#6c7086"
        )
        self.v2_label.pack(anchor="w", padx=12, pady=2)

        self.log_label = tk.Label(
            status_frame, text="Ready",
            font=("Segoe UI", 9, "italic"),
            bg=self.SURFACE, fg="#6c7086"
        )
        self.log_label.pack(anchor="w", padx=12, pady=(4, 8))

        # Button frame
        btn_frame = tk.Frame(self, bg=self.DARK)
        btn_frame.pack(fill="x", padx=16, pady=8)

        self.toggle_btn = tk.Button(
            btn_frame, text="▶  Start",
            font=("Segoe UI", 12, "bold"),
            bg=self.GREEN, fg="white",
            activebackground=self.GREEN, activeforeground="white",
            bd=0, relief="flat",
            cursor="hand2",
            height=2,
            command=self._toggle,
        )
        self.toggle_btn.pack(fill="x", ipady=6)

        self.call_btn = tk.Button(
            btn_frame, text="Call Agent",
            font=("Segoe UI", 11),
            bg="#3b82f6", fg="white",
            activebackground="#3b82f6", activeforeground="white",
            bd=0, relief="flat",
            cursor="hand2",
            state="disabled",
            height=1,
            command=self._call,
        )
        self.call_btn.pack(fill="x", ipady=4, pady=(8, 0))

        # Footer
        tk.Label(
            self, text="Start = launch servers  |  Call = open softphone + dial",
            font=("Segoe UI", 8),
            bg=self.DARK, fg="#45475a"
        ).pack(side="bottom", pady=(0, 8))

    def _check_ports(self):
        """Return (llama_up, v2_up)"""
        llama = False
        v2 = False
        try:
            r = subprocess.run(
                ["curl", "-sf", f"http://127.0.0.1:{LLAMA_PORT}/health"],
                capture_output=True, timeout=3,
            )
            llama = r.returncode == 0
        except Exception:
            pass
        try:
            r = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True, text=True, timeout=3,
            )
            v2 = f":{V2_PORT} " in r.stdout
        except Exception:
            pass
        return llama, v2

    def _refresh_status(self):
        llama_up, v2_up = self._check_ports()

        color = self.GREEN if llama_up else "#6c7086"
        self.llama_label.configure(fg=color)

        color = self.GREEN if v2_up else "#6c7086"
        self.v2_label.configure(fg=color)

        self._running = llama_up and v2_up

        if self._running:
            self.toggle_btn.configure(
                text="■  Stop",
                bg=self.RED,
                activebackground=self.RED,
            )
            self.call_btn.configure(state="normal")
        else:
            self.toggle_btn.configure(
                text="▶  Start",
                bg=self.GREEN,
                activebackground=self.GREEN,
            )
            self.call_btn.configure(state="disabled")

        self.after(1500, self._refresh_status)

    def _toggle(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        self.log_label.configure(text="Starting...", fg=self.AMBER)
        self.toggle_btn.configure(state="disabled")

        def run():
            try:
                result = subprocess.run(
                    ["python3", START_SCRIPT],
                    capture_output=True, text=True, timeout=60,
                )
            except Exception as e:
                self.after(0, lambda: self._on_start_done(False, str(e)))
                return
            self.after(0, lambda: self._on_start_done(
                result.returncode == 0, result.stdout
            ))

        threading.Thread(target=run, daemon=True).start()

    def _on_start_done(self, ok, info):
        self.toggle_btn.configure(state="normal")
        if ok:
            self.log_label.configure(text="Running", fg=self.GREEN)
        else:
            self.log_label.configure(text="Failed", fg=self.RED)
            messagebox.showerror("Error", "Failed to start servers:\n" + info)

    def _stop(self):
        self.log_label.configure(text="Stopping...", fg=self.AMBER)
        self.toggle_btn.configure(state="disabled")

        def run():
            try:
                subprocess.run(
                    ["bash", STOP_SCRIPT],
                    capture_output=True, text=True, timeout=15,
                )
            except Exception:
                pass
            self.after(0, lambda: self._on_stop_done())

        threading.Thread(target=run, daemon=True).start()

    def _on_stop_done(self):
        self.toggle_btn.configure(state="normal")
        self.log_label.configure(text="Stopped", fg="#6c7086")

    def _call(self):
        """Open baresip and auto-dial testlive."""
        try:
            subprocess.Popen(["gnome-terminal", "--", "baresip", "-e", "/dial testlive"])
        except Exception:
            try:
                subprocess.Popen(["xterm", "-e", "baresip", "-e", "/dial testlive"])
            except Exception:
                messagebox.showwarning(
                    "No terminal emulator found",
                    "Install gnome-terminal or xterm, or run:\nbaresip -e '/dial testlive'",
                )


if __name__ == "__main__":
    VoiceAgentLauncher().mainloop()
