#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
USB Sentry Pro - Enterprise USB & Removable Media Access Controller
Version: 1.5.0
Developer: Yunus İNAN
Copyright: Copyright © 2026 Yunus İNAN. Tüm hakları saklıdır.
================================================================================
Core USB storage policy engine and native Win32 management interface.
"""

import os
import sys
import winreg
import ctypes
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# ------------------------------------------------------------------------------
# Security Policy Constants
# ------------------------------------------------------------------------------
MODE_ALLOW = 1       # Read & Write Allowed (Default)
MODE_READ_ONLY = 2   # Read-Only (Write Protection)
MODE_BLOCK = 3       # Block All USB Storage Devices

USBSTOR_KEY = r"SYSTEM\CurrentControlSet\Services\USBSTOR"
STORAGE_POLICIES_KEY = r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies"

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def ensure_admin():
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit(0)

def restart_shell():
    """Refreshes Windows Explorer shell to ensure changes take effect immediately."""
    try:
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], capture_output=True, creationflags=0x08000000)
        subprocess.Popen(["explorer.exe"], creationflags=0x08000000)
    except Exception as e:
        print(f"Shell restart error: {e}")

# ------------------------------------------------------------------------------
# Core Registry USB Access Control Engine
# ------------------------------------------------------------------------------
def get_current_mode() -> int:
    """Reads current system policy from Windows Registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY, 0, winreg.KEY_READ) as key:
            start_val, _ = winreg.QueryValueEx(key, "Start")
            if start_val == 4:
                return MODE_BLOCK
    except Exception:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY, 0, winreg.KEY_READ) as key:
            wp_val, _ = winreg.QueryValueEx(key, "WriteProtect")
            if wp_val == 1:
                return MODE_READ_ONLY
    except Exception:
        pass

    return MODE_ALLOW

def apply_mode(mode: int) -> bool:
    """Applies the selected 3-tier access policy to Windows Registry."""
    try:
        # 1. Block USB Storage
        if mode == MODE_BLOCK:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 4)
            return True

        # 2. Allow Read & Write
        elif mode == MODE_ALLOW:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 3)
            try:
                with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 0)
            except Exception:
                pass
            return True

        # 3. Read-Only (Write Protect)
        elif mode == MODE_READ_ONLY:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, USBSTOR_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "Start", 0, winreg.REG_DWORD, 3)
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, STORAGE_POLICIES_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "WriteProtect", 0, winreg.REG_DWORD, 1)
            return True

    except Exception as e:
        print(f"apply_mode error: {e}")
        return False

# ------------------------------------------------------------------------------
# Core GUI Interface
# ------------------------------------------------------------------------------
class USBSentryApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("USB Sentry Pro v1.5.0 - Yunus İNAN")
        self.root.geometry("430x215")
        self.root.resizable(False, False)

        self.mode_var = tk.IntVar(value=get_current_mode())
        self.setup_ui()

    def setup_ui(self):
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.BOTH, expand=True)

        # Left Canvas
        self.canvas = tk.Canvas(top_frame, width=105, height=105, bg="#F0F0F0", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=(6, 16), pady=4)

        # Right Options
        right_frame = ttk.Frame(top_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Radiobutton(
            right_frame,
            text="Tüm Aygıtlara İzin Ver (Varsayılan)",
            variable=self.mode_var,
            value=MODE_ALLOW,
            command=self.update_canvas
        ).pack(anchor="w", pady=4)

        ttk.Radiobutton(
            right_frame,
            text="Sadece Okunabilir Yap",
            variable=self.mode_var,
            value=MODE_READ_ONLY,
            command=self.update_canvas
        ).pack(anchor="w", pady=4)

        ttk.Radiobutton(
            right_frame,
            text="Usb Depolama Aygıtlarını Engelle",
            variable=self.mode_var,
            value=MODE_BLOCK,
            command=self.update_canvas
        ).pack(anchor="w", pady=4)

        # Bottom Apply Button
        bottom_frame = ttk.Frame(container)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(6, 0))

        self.btn_apply = tk.Button(
            bottom_frame,
            text="Değişiklikleri Uygula",
            font=("Segoe UI Semibold", 10),
            bg="#F3F3F3",
            fg="#000000",
            relief="groove",
            bd=1,
            padx=10,
            pady=4,
            cursor="hand2",
            command=self.on_apply
        )
        self.btn_apply.pack(fill=tk.X)

        self.update_canvas()

    def update_canvas(self):
        self.canvas.delete("all")
        mode = self.mode_var.get()
        color = "#27AE60" if mode == MODE_ALLOW else ("#F39C12" if mode == MODE_READ_ONLY else "#C0392B")
        self.canvas.create_rectangle(30, 20, 75, 90, fill=color, outline="#2C3E50", width=2)
        self.canvas.create_rectangle(40, 10, 65, 20, fill="#BDC3C7", outline="#7F8C8D")

    def on_apply(self):
        target_mode = self.mode_var.get()
        if apply_mode(target_mode):
            messagebox.showinfo("USB Sentry Pro", "Değişiklikler başarıyla uygulandı.", parent=self.root)
        else:
            messagebox.showerror("Hata", "Politika uygulanamadı!", parent=self.root)

def main():
    ensure_admin()
    root = tk.Tk()
    app = USBSentryApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
