"""
================================================================================
USB Sentry Pro - Advanced USB & Removable Storage Access Security Tool
Version: 1.5.0
Developer: Yunus İNAN
Copyright: Copyright © 2026 Yunus İNAN tarafından geliştirilmiştir. Tüm hakları saklıdır.
================================================================================
"""

import os
import sys
import json
import base64
import ctypes
import hashlib
import secrets
import subprocess
import winreg
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageDraw, ImageTk

# ==============================================================================
# 1. Administrator Privileges Check & Relaunch
# ==============================================================================
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_admin():
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        sys.exit(0)

# ==============================================================================
# 2. Registry Paths & System Constants
# ==============================================================================
KEY_USBSTOR = r"SYSTEM\CurrentControlSet\Services\USBSTOR"
KEY_STORAGE_POLICIES = r"SYSTEM\CurrentControlSet\Control\StorageDevicePolicies"
KEY_REMOVABLE_DEVICES = r"SOFTWARE\Policies\Microsoft\Windows\RemovableStorageDevices"

# Class GUIDs under RemovableStorageDevices
GUID_USB_DISKS = r"{53f5630d-b6bf-11d0-94f2-00a0c91efb8b}"
GUID_CD_DVD     = r"{99042d36-9db0-11d0-94f2-00a0c91efb8b}"
GUID_FLOPPY     = r"{53f56311-b6bf-11d0-94f2-00a0c91efb8b}"
GUID_TAPE       = r"{6ac27879-a641-4170-ba40-e0f99f836f42}"
GUID_WPD        = r"{6ac27878-a641-4170-ba40-e0f99f836f42}"

KEY_DEVICE_INSTALL_RESTRICTIONS = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions"
KEY_DENY_DEVICE_IDS = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions\DenyDeviceIDs"
KEY_ALLOW_DEVICE_IDS = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions\AllowDeviceIDs"
KEY_DENY_DEVICE_CLASSES = r"SOFTWARE\Policies\Microsoft\Windows\DeviceInstall\Restrictions\DenyDeviceClasses"

KEY_EXPLORER_ADVANCED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
KEY_EXPLORER_POLICIES = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
ENUM_USBSTOR_PATH = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"

HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A
WM_DEVICECHANGE = 0x0219
DBT_DEVNODES_CHANGED = 0x0007
SMTO_ABORTIFHUNG = 0x0002
SHCNE_ASSOCCHANGED = 0x08000000
SHCNF_FLUSH = 0x1000

# SetupAPI / CfgMgr32 prototypes
try:
    cfg = ctypes.windll.cfgmgr32
    cfg.CM_Locate_DevNodeW.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.c_wchar_p, ctypes.c_ulong]
    cfg.CM_Locate_DevNodeW.restype = ctypes.c_ulong
    cfg.CM_Reenumerate_DevNode.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    cfg.CM_Reenumerate_DevNode.restype = ctypes.c_ulong
except Exception:
    pass

# ==============================================================================
# 3. Persistent Configuration Management (~/.usbsentrypro/config.json)
# ==============================================================================
def get_config_path() -> str:
    """
    Returns path to ~/.usbsentrypro/config.json.
    Ensures directory exists and is 100% consistent across standard and elevated runs.
    """
    user_home = os.path.expanduser("~")
    target_dir = os.path.join(user_home, ".usbsentrypro")
    os.makedirs(target_dir, exist_ok=True)
    config_file = os.path.join(target_dir, "config.json")

    # Migrate from older config files if present
    if not os.path.exists(config_file):
        for candidate in [
            os.path.join(os.environ.get("APPDATA", ""), "USBSentryPro", "sentry_config.json"),
            os.path.join(os.environ.get("APPDATA", ""), "USBSentryPro", "config.json"),
            os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "app_config.json")
        ]:
            if os.path.exists(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = f.read()
                    with open(config_file, "w", encoding="utf-8") as f:
                        f.write(data)
                    break
                except Exception:
                    pass

    return config_file

def load_config() -> dict:
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if "lock_enabled" in cfg and "lock_active" not in cfg:
                    cfg["lock_active"] = cfg["lock_enabled"]
                return cfg
        except Exception:
            pass
    return {
        "lock_active": False,
        "password_hash": "",
        "password_salt": "",
        "block_install_enabled": False,
        "anti_tamper_enabled": False
    }

def save_config(cfg_dict: dict):
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=4)
    except Exception as e:
        print(f"save_config error: {e}")

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def verify_password(entered: str, salt: str, expected_hash: str) -> bool:
    if not expected_hash:
        return True
    return hash_password(entered, salt) == expected_hash

# ==============================================================================
# 4. Real 16x16 RGBA Menu Icons Generator (Pillow + ImageTk)
# ==============================================================================
def create_menu_icons() -> dict:
    """
    Generates clean, professional 16x16 RGBA icons for every menu item,
    providing native Win32 clarity with zero distorted unicode characters.
    """
    icons = {}

    def new_canvas():
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        return im, d

    # 1. lock (Padlock)
    im, d = new_canvas()
    d.arc([5, 2, 10, 8], 180, 0, fill=(127, 140, 141, 255), width=2)
    d.rectangle([3, 7, 12, 14], fill=(241, 196, 15, 255), outline=(214, 137, 16, 255))
    d.rectangle([7, 9, 8, 12], fill=(44, 62, 80, 255))
    icons["lock"] = ImageTk.PhotoImage(im)

    # 2. key (Golden Key)
    im, d = new_canvas()
    d.ellipse([2, 2, 7, 7], outline=(243, 156, 18, 255), width=2)
    d.line([(6, 6), (13, 13)], fill=(243, 156, 18, 255), width=2)
    d.line([(10, 10), (12, 8)], fill=(243, 156, 18, 255), width=2)
    d.line([(12, 12), (14, 10)], fill=(243, 156, 18, 255), width=2)
    icons["key"] = ImageTk.PhotoImage(im)

    # 3. refresh (Circular Arrows)
    im, d = new_canvas()
    d.arc([2, 2, 13, 13], 30, 300, fill=(41, 128, 185, 255), width=2)
    d.polygon([(11, 2), (15, 5), (10, 7)], fill=(41, 128, 185, 255))
    icons["refresh"] = ImageTk.PhotoImage(im)

    # 4. exit (Door / Exit Arrow)
    im, d = new_canvas()
    d.rectangle([2, 2, 7, 13], fill=(127, 140, 141, 255), outline=(44, 62, 80, 255))
    d.line([(7, 8), (14, 8)], fill=(231, 76, 60, 255), width=2)
    d.polygon([(11, 5), (15, 8), (11, 11)], fill=(231, 76, 60, 255))
    icons["exit"] = ImageTk.PhotoImage(im)

    # 5. allow_all (Green Check Circle)
    im, d = new_canvas()
    d.ellipse([2, 2, 13, 13], fill=(39, 174, 96, 255))
    d.line([(4, 8), (7, 11), (12, 5)], fill=(255, 255, 255, 255), width=2)
    icons["allow_all"] = ImageTk.PhotoImage(im)

    # 6. block_all (Red Prohibition Circle)
    im, d = new_canvas()
    d.ellipse([2, 2, 13, 13], outline=(192, 57, 43, 255), width=2)
    d.line([(4, 4), (11, 11)], fill=(192, 57, 43, 255), width=2)
    icons["block_all"] = ImageTk.PhotoImage(im)

    # 7. cd (Compact Disc)
    im, d = new_canvas()
    d.ellipse([2, 2, 13, 13], fill=(189, 195, 199, 255), outline=(127, 140, 141, 255))
    d.ellipse([5, 5, 10, 10], fill=(72, 219, 251, 255))
    d.ellipse([6, 6, 9, 9], fill=(240, 240, 240, 255), outline=(127, 140, 141, 255))
    icons["cd"] = ImageTk.PhotoImage(im)

    # 8. floppy (Diskette)
    im, d = new_canvas()
    d.rectangle([2, 2, 13, 13], fill=(41, 128, 185, 255), outline=(27, 79, 114, 255))
    d.rectangle([4, 2, 11, 6], fill=(189, 195, 199, 255))
    d.rectangle([4, 8, 11, 12], fill=(236, 240, 241, 255))
    icons["floppy"] = ImageTk.PhotoImage(im)

    # 9. tape (Cassette Tape)
    im, d = new_canvas()
    d.rectangle([2, 4, 13, 12], fill=(52, 73, 94, 255), outline=(44, 62, 80, 255))
    d.ellipse([4, 6, 7, 9], fill=(236, 240, 241, 255))
    d.ellipse([8, 6, 11, 9], fill=(236, 240, 241, 255))
    icons["tape"] = ImageTk.PhotoImage(im)

    # 10. phone (Mobile / MTP Device)
    im, d = new_canvas()
    d.rectangle([4, 2, 11, 14], fill=(22, 160, 133, 255), outline=(17, 120, 100, 255))
    d.rectangle([5, 4, 10, 11], fill=(44, 62, 80, 255))
    d.ellipse([7, 12, 8, 13], fill=(255, 255, 255, 255))
    icons["phone"] = ImageTk.PhotoImage(im)

    # 11. stop_install (Stop Sign)
    im, d = new_canvas()
    d.polygon([(5, 2), (10, 2), (13, 5), (13, 10), (10, 13), (5, 13), (2, 10), (2, 5)], fill=(192, 57, 43, 255))
    d.rectangle([4, 7, 11, 8], fill=(255, 255, 255, 255))
    icons["stop_install"] = ImageTk.PhotoImage(im)

    # 12. protect_files (Shield with Lock)
    im, d = new_canvas()
    d.polygon([(8, 1), (13, 3), (13, 9), (8, 14), (3, 9), (3, 3)], fill=(41, 128, 185, 255), outline=(21, 67, 96, 255))
    d.rectangle([6, 7, 9, 10], fill=(241, 196, 15, 255))
    d.arc([6, 5, 9, 8], 180, 0, fill=(255, 255, 255, 255), width=1)
    icons["protect_files"] = ImageTk.PhotoImage(im)

    # 13. autorun (Lightning Bolt)
    im, d = new_canvas()
    d.polygon([(9, 1), (4, 8), (8, 8), (6, 14), (13, 7), (9, 7)], fill=(243, 156, 18, 255))
    icons["autorun"] = ImageTk.PhotoImage(im)

    # 14. hidden_files (Eye Reveal Icon)
    im, d = new_canvas()
    d.ellipse([2, 4, 13, 11], outline=(41, 128, 185, 255), width=2)
    d.ellipse([6, 6, 9, 9], fill=(41, 128, 185, 255))
    icons["hidden_files"] = ImageTk.PhotoImage(im)

    # 15. file_ext (File Extension Tag)
    im, d = new_canvas()
    d.polygon([(3, 2), (10, 2), (13, 5), (13, 14), (3, 14)], fill=(236, 240, 241, 255), outline=(142, 68, 173, 255))
    d.rectangle([5, 8, 11, 11], fill=(142, 68, 173, 255))
    icons["file_ext"] = ImageTk.PhotoImage(im)

    # 16. eject (Hardware Eject Icon)
    im, d = new_canvas()
    d.polygon([(8, 2), (3, 9), (13, 9)], fill=(211, 84, 0, 255))
    d.rectangle([3, 11, 13, 13], fill=(211, 84, 0, 255))
    icons["eject"] = ImageTk.PhotoImage(im)

    # 17. info (Info Circle)
    im, d = new_canvas()
    d.ellipse([2, 2, 13, 13], fill=(41, 128, 185, 255))
    d.rectangle([7, 4, 8, 5], fill=(255, 255, 255, 255))
    d.rectangle([7, 7, 8, 11], fill=(255, 255, 255, 255))
    icons["info"] = ImageTk.PhotoImage(im)

    # 18. about (Security Shield Check)
    im, d = new_canvas()
    d.polygon([(8, 1), (13, 3), (13, 9), (8, 14), (3, 9), (3, 3)], fill=(31, 79, 114, 255), outline=(241, 196, 15, 255))
    d.line([(5, 7), (7, 10), (11, 5)], fill=(255, 255, 255, 255), width=2)
    icons["about"] = ImageTk.PhotoImage(im)

    return icons

# ==============================================================================
# 5. Low-Level Registry Helper Functions
# ==============================================================================
def get_reg_dword(root_key, subkey: str, value_name: str, default: int = None):
    try:
        with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_READ) as k:
            val, vtype = winreg.QueryValueEx(k, value_name)
            if vtype == winreg.REG_DWORD:
                return val
    except OSError:
        pass
    return default

def set_reg_dword(root_key, subkey: str, value_name: str, value: int):
    try:
        with winreg.CreateKeyEx(root_key, subkey, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, value_name, 0, winreg.REG_DWORD, int(value))
    except OSError as e:
        print(f"Error set_reg_dword {subkey}\\{value_name}: {e}")

def set_reg_string(root_key, subkey: str, value_name: str, value: str):
    try:
        with winreg.CreateKeyEx(root_key, subkey, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, value_name, 0, winreg.REG_SZ, str(value))
    except OSError as e:
        print(f"Error set_reg_string {subkey}\\{value_name}: {e}")

def delete_reg_value(root_key, subkey: str, value_name: str):
    try:
        with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, value_name)
    except OSError:
        pass

def delete_reg_tree(root_key, subkey: str):
    try:
        with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as k:
            while True:
                try:
                    sub = winreg.EnumKey(k, 0)
                    delete_reg_tree(root_key, f"{subkey}\\{sub}")
                except OSError:
                    break
        winreg.DeleteKey(root_key, subkey)
    except OSError:
        pass

def broadcast_system_changes():
    try:
        ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_FLUSH, 0, 0)
    except Exception:
        pass
    try:
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_DEVICECHANGE, DBT_DEVNODES_CHANGED, 0,
            SMTO_ABORTIFHUNG, 2000, ctypes.byref(res)
        )
    except Exception:
        pass
    try:
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Policy",
            SMTO_ABORTIFHUNG, 2000, ctypes.byref(res)
        )
    except Exception:
        pass
    try:
        devnode = ctypes.c_ulong(0)
        if ctypes.windll.cfgmgr32.CM_Locate_DevNodeW(ctypes.byref(devnode), None, 0) == 0:
            ctypes.windll.cfgmgr32.CM_Reenumerate_DevNode(devnode, 0)
    except Exception:
        pass

# ==============================================================================
# 6. Core USB Access Modes (Mode 1: Allow, Mode 2: Read-Only, Mode 3: Block)
# ==============================================================================
MODE_ALLOW = 1
MODE_READ_ONLY = 2
MODE_BLOCK = 3

def get_current_mode() -> int:
    usb_start = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 3)
    write_protect = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_STORAGE_POLICIES, "WriteProtect", 0)
    deny_all_gen = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All", 0)
    deny_all_cls = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, f"{KEY_REMOVABLE_DEVICES}\\{GUID_USB_DISKS}", "Deny_All", 0)
    deny_wr_gen = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_Write", 0)
    deny_wr_cls = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, f"{KEY_REMOVABLE_DEVICES}\\{GUID_USB_DISKS}", "Deny_Write", 0)

    if usb_start == 4 or deny_all_gen == 1 or deny_all_cls == 1:
        return MODE_BLOCK
    if write_protect == 1 or deny_wr_gen == 1 or deny_wr_cls == 1:
        return MODE_READ_ONLY
    return MODE_ALLOW

def apply_mode(mode: int):
    guid_path = f"{KEY_REMOVABLE_DEVICES}\\{GUID_USB_DISKS}"
    if mode == MODE_ALLOW:
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 3)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_STORAGE_POLICIES, "WriteProtect", 0)
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_Write")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_All")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Write")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Read")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Execute")

    elif mode == MODE_READ_ONLY:
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 3)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_STORAGE_POLICIES, "WriteProtect", 1)
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_All")
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_Write", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Write", 1)
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Read")

    elif mode == MODE_BLOCK:
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 4)
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_STORAGE_POLICIES, "WriteProtect")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_Write")
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_All", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Write", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Read", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, guid_path, "Deny_Execute", 1)

    broadcast_system_changes()

# ==============================================================================
# 7. Peripheral Class GUID Policies (CD-DVD, Floppy, Tape, WPD)
# ==============================================================================
def get_class_guid_policy(guid: str) -> int:
    path = f"{KEY_REMOVABLE_DEVICES}\\{guid}"
    dw = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Write", 0)
    dr = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Read", 0)
    da = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_All", 0)
    if da == 1 or (dw == 1 and dr == 1):
        return 3  # Block
    elif dw == 1:
        return 2  # Read-Only
    return 1      # Allow

def set_class_guid_policy(guid: str, mode: int):
    path = f"{KEY_REMOVABLE_DEVICES}\\{guid}"
    if mode == 1:  # Allow
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Write")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Read")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Execute")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_All")
    elif mode == 2:  # Read-Only
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Write", 1)
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Read")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Execute")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, path, "Deny_All")
    elif mode == 3:  # Block
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Write", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Read", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_Execute", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, path, "Deny_All", 1)
    broadcast_system_changes()

# ==============================================================================
# 8. Anti-Tamper / Driver Hardening (usbstor.inf / usbstor.pnf)
# ==============================================================================
def get_inf_files():
    windir = os.environ.get("SystemRoot", r"C:\Windows")
    inf = os.path.join(windir, "inf", "usbstor.inf")
    pnf = os.path.join(windir, "inf", "usbstor.pnf")
    return inf, pnf

def is_driver_files_protected() -> bool:
    inf, _ = get_inf_files()
    if os.path.exists(inf):
        try:
            p = subprocess.run(["icacls", inf], capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            out = p.stdout.decode("latin1", errors="ignore").upper()
            if "SYSTEM:(DENY" in out or "USERS:(DENY" in out or "(DENY)(F)" in out or "SYSTEM:(D)" in out or "USERS:(D)" in out:
                return True
        except Exception:
            pass
    return False

def toggle_driver_files_protection(protect: bool):
    inf_files = get_inf_files()
    for f in inf_files:
        if os.path.exists(f):
            if protect:
                subprocess.run(["takeown", "/f", f, "/a"], capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                subprocess.run(["icacls", f, "/grant", "*S-1-5-32-544:F"], capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                subprocess.run(["icacls", f, "/grant", "Administrators:F"], capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                for sid in ["*S-1-5-18", "*S-1-1-0", "*S-1-5-32-545", "SYSTEM", "Everyone", "Users"]:
                    subprocess.run(["icacls", f, "/deny", f"{sid}:(F)"], capture_output=True, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            else:
                for sid in ["*S-1-5-18", "*S-1-1-0", "*S-1-5-32-545", "SYSTEM", "Everyone", "Users"]:
                    subprocess.run(["icacls", f, "/remove:d", sid], capture_output=True, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                subprocess.run(["icacls", f, "/reset"], capture_output=True, check=False,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

# ==============================================================================
# 9. Device Installation Restriction & Devnode Disabling (Dual-Lock)
# ==============================================================================
def get_connected_usb_device_ids() -> list:
    ids = set()
    kernel32 = ctypes.windll.kernel32
    mask = kernel32.GetLogicalDrives()
    active_letters = [chr(ord('A') + i) + ':' for i in range(26) if (mask & (1 << i))]
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\MountedDevices") as k:
            cnt = winreg.QueryInfoKey(k)[1]
            for i in range(cnt):
                name, val, _ = winreg.EnumValue(k, i)
                if name.startswith(r"\DosDevices\\"):
                    letter = name.replace(r"\DosDevices\\", "")
                    if letter in active_letters and isinstance(val, (bytes, bytearray)):
                        txt = val.decode("utf-16le", errors="ignore")
                        if "USBSTOR" in txt or "USB" in txt:
                            clean = txt.replace(r"\??\\", "").replace(r"\??\#", "").replace("_??_", "")
                            clean = clean.split("#{")[0].strip("\x00")
                            dev_id = clean.replace("#", "\\")
                            if dev_id:
                                ids.add(dev_id)
    except OSError:
        pass

    path = r"SYSTEM\CurrentControlSet\Control\DeviceClasses\{53f56307-b6bf-11d0-94f2-00a0c91efb8b}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            count = winreg.QueryInfoKey(k)[0]
            for i in range(count):
                sub = winreg.EnumKey(k, i)
                ctrl_path = f"{path}\\{sub}\\Control"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ctrl_path) as ck:
                        if winreg.QueryValueEx(ck, "Linked")[0] == 1:
                            clean = sub.replace("##?#", "").split("#{")[0]
                            dev_id = clean.replace("#", "\\")
                            if "USBSTOR" in dev_id or "USB" in dev_id:
                                ids.add(dev_id)
                except OSError:
                    pass
    except OSError:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services\USBSTOR\Enum") as k:
            cnt = winreg.QueryInfoKey(k)[1]
            for i in range(cnt):
                _, val, _ = winreg.EnumValue(k, i)
                if val and isinstance(val, str) and ("USBSTOR" in val or "USB" in val):
                    ids.add(val)
    except OSError:
        pass

    ps_script = """
    $ids = @()
    $disks = Get-CimInstance Win32_DiskDrive -ErrorAction SilentlyContinue | Where-Object { $_.InterfaceType -eq 'USB' -or $_.PNPDeviceID -like 'USB*' }
    foreach ($d in $disks) {
        if ($d.PNPDeviceID) { $ids += $d.PNPDeviceID }
        $pnp = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | Where-Object { $_.DeviceID -eq $d.PNPDeviceID }
        if ($pnp -and $pnp.HardwareID) {
            foreach ($h in $pnp.HardwareID) {
                if ($h -and $h -notin @('GenDisk', 'USBSTOR\\Disk', 'USBSTOR\\RAW')) {
                    $ids += $h
                }
            }
        }
    }
    $ids | Select-Object -Unique | ForEach-Object { Write-Output $_ }
    """
    try:
        enc = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        p = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc],
                           capture_output=True, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        lines = p.stdout.decode("utf-8", errors="ignore").splitlines()
        for line in lines:
            line = line.strip()
            if line and line not in ("GenDisk", "USBSTOR\\Disk", "USBSTOR\\RAW"):
                ids.add(line)
    except Exception:
        pass

    for dev in list(ids):
        if dev.startswith("USBSTOR\\"):
            parts = dev.split("\\")
            if len(parts) >= 3:
                key_path = f"SYSTEM\\CurrentControlSet\\Enum\\USBSTOR\\{parts[1]}\\{parts[2]}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as dev_key:
                        hw_val, _ = winreg.QueryValueEx(dev_key, "HardwareID")
                        if isinstance(hw_val, list):
                            for h in hw_val:
                                if h not in ("GenDisk", "USBSTOR\\Disk", "USBSTOR\\RAW"):
                                    ids.add(h)
                except OSError:
                    pass

    return sorted(list(ids))

def set_disconnected_usbstor_devices_disabled(connected_ids: list):
    base_path = ENUM_USBSTOR_PATH
    cfg = ctypes.windll.cfgmgr32
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as base_key:
            num_devs = winreg.QueryInfoKey(base_key)[0]
            for i in range(num_devs):
                dev_name = winreg.EnumKey(base_key, i)
                dev_path = f"{base_path}\\{dev_name}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_path) as dev_key:
                        num_insts = winreg.QueryInfoKey(dev_key)[0]
                        for j in range(num_insts):
                            inst_id = winreg.EnumKey(dev_key, j)
                            inst_path = f"{dev_path}\\{inst_id}"
                            full_id = f"USBSTOR\\{dev_name}\\{inst_id}"

                            dn = ctypes.c_ulong(0)
                            ret = cfg.CM_Locate_DevNodeW(ctypes.byref(dn), full_id, 0)
                            is_conn = (ret == 0)

                            if not is_conn and connected_ids:
                                full_u = full_id.upper()
                                inst_u = inst_id.upper()
                                for cid in connected_ids:
                                    cid_u = cid.upper()
                                    if inst_u in cid_u or full_u in cid_u or cid_u in full_u:
                                        is_conn = True
                                        break

                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path, 0,
                                                    winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as inst_key:
                                    if is_conn:
                                        try:
                                            cf, _ = winreg.QueryValueEx(inst_key, "ConfigFlags")
                                            if cf != 0:
                                                winreg.SetValueEx(inst_key, "ConfigFlags", 0, winreg.REG_DWORD, 0)
                                        except OSError:
                                            winreg.SetValueEx(inst_key, "ConfigFlags", 0, winreg.REG_DWORD, 0)
                                    else:
                                        winreg.SetValueEx(inst_key, "ConfigFlags", 0, winreg.REG_DWORD, 1)
                            except OSError:
                                pass
                except OSError:
                    pass
    except OSError:
        pass

def reset_all_usbstor_devices_configflags():
    base_path = ENUM_USBSTOR_PATH
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as base_key:
            num_devs = winreg.QueryInfoKey(base_key)[0]
            for i in range(num_devs):
                dev_name = winreg.EnumKey(base_key, i)
                dev_path = f"{base_path}\\{dev_name}"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, dev_path) as dev_key:
                        num_insts = winreg.QueryInfoKey(dev_key)[0]
                        for j in range(num_insts):
                            inst_id = winreg.EnumKey(dev_key, j)
                            inst_path = f"{dev_path}\\{inst_id}"
                            try:
                                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, inst_path, 0,
                                                    winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as inst_key:
                                    try:
                                        cf, _ = winreg.QueryValueEx(inst_key, "ConfigFlags")
                                        if cf == 1 or (cf & 1):
                                            winreg.SetValueEx(inst_key, "ConfigFlags", 0, winreg.REG_DWORD, 0)
                                    except OSError:
                                        pass
                            except OSError:
                                pass
                except OSError:
                    pass
    except OSError:
        pass

def toggle_enum_usbstor_lock(lock: bool):
    if lock:
        ps_script = """
        $p = 'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR'
        $acl = Get-Acl $p
        $acl.Access | Where-Object { $_.AccessControlType -eq 'Deny' -and $_.IdentityReference -match 'SYSTEM' } | ForEach-Object { $acl.RemoveAccessRule($_) }
        $sid = New-Object System.Security.Principal.SecurityIdentifier('S-1-5-18')
        $rule = New-Object System.Security.AccessControl.RegistryAccessRule($sid, 'WriteKey', 'ContainerInherit', 'None', 'Deny')
        $acl.AddAccessRule($rule)
        Set-Acl $p $acl
        """
    else:
        ps_script = """
        $p = 'HKLM:\\SYSTEM\\CurrentControlSet\\Enum\\USBSTOR'
        $acl = Get-Acl $p
        $acl.Access | Where-Object { $_.AccessControlType -eq 'Deny' -and $_.IdentityReference -match 'SYSTEM' } | ForEach-Object { $acl.RemoveAccessRule($_) }
        Set-Acl $p $acl
        """
    try:
        enc = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc],
                       capture_output=True, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except Exception as e:
        print(f"toggle_enum_usbstor_lock error: {e}")

def is_device_install_blocked() -> bool:
    ddi = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceIDs")
    if ddi == 1:
        return True
    du = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyUnspecified")
    if du == 1:
        return True
    return is_driver_files_protected()

def toggle_device_install_block(block: bool):
    if block:
        allowed_ids = get_connected_usb_device_ids()
        set_disconnected_usbstor_devices_disabled(allowed_ids)

        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceIDs", 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceIDsRetroactive", 0)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyUnspecified", 1)

        delete_reg_tree(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_IDS)
        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_IDS, 0, winreg.KEY_SET_VALUE):
                pass
        except OSError:
            pass
        set_reg_string(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_IDS, "1", r"USBSTOR\*")
        set_reg_string(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_IDS, "2", r"USB\*")

        delete_reg_tree(winreg.HKEY_LOCAL_MACHINE, KEY_ALLOW_DEVICE_IDS)
        try:
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, KEY_ALLOW_DEVICE_IDS, 0, winreg.KEY_SET_VALUE):
                pass
        except OSError:
            pass
        for idx, dev_id in enumerate(allowed_ids, start=1):
            set_reg_string(winreg.HKEY_LOCAL_MACHINE, KEY_ALLOW_DEVICE_IDS, str(idx), dev_id)

        toggle_enum_usbstor_lock(True)
        toggle_driver_files_protection(True)
    else:
        toggle_enum_usbstor_lock(False)
        reset_all_usbstor_devices_configflags()

        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceIDs")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceIDsRetroactive")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyUnspecified")
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_DEVICE_INSTALL_RESTRICTIONS, "DenyDeviceClasses")
        delete_reg_tree(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_IDS)
        delete_reg_tree(winreg.HKEY_LOCAL_MACHINE, KEY_ALLOW_DEVICE_IDS)
        delete_reg_tree(winreg.HKEY_LOCAL_MACHINE, KEY_DENY_DEVICE_CLASSES)

        toggle_driver_files_protection(False)

    broadcast_system_changes()
    try:
        subprocess.Popen(["gpupdate", "/target:computer", "/force"],
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except Exception:
        pass

# ==============================================================================
# 10. Windows Explorer Tweaks & USB Utilities
# ==============================================================================
def is_autorun_disabled() -> bool:
    val = get_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_EXPLORER_POLICIES, "NoDriveTypeAutoRun")
    return val == 0xFF or val == 255

def toggle_autorun(disable: bool):
    if disable:
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_EXPLORER_POLICIES, "NoDriveTypeAutoRun", 0xFF)
        set_reg_dword(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_POLICIES, "NoDriveTypeAutoRun", 0xFF)
    else:
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_EXPLORER_POLICIES, "NoDriveTypeAutoRun")
        delete_reg_value(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_POLICIES, "NoDriveTypeAutoRun")
    broadcast_system_changes()

def is_hidden_files_shown() -> bool:
    val = get_reg_dword(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_ADVANCED, "Hidden", 2)
    return val == 1

def toggle_hidden_files(show: bool):
    set_reg_dword(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_ADVANCED, "Hidden", 1 if show else 2)
    broadcast_system_changes()

def is_file_extensions_shown() -> bool:
    val = get_reg_dword(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_ADVANCED, "HideFileExt", 1)
    return val == 0

def toggle_file_extensions(show: bool):
    set_reg_dword(winreg.HKEY_CURRENT_USER, KEY_EXPLORER_ADVANCED, "HideFileExt", 0 if show else 1)
    broadcast_system_changes()

def open_safely_remove_dialog():
    try:
        subprocess.Popen(["RunDll32.exe", "shell32.dll,Control_RunDLL", "hotplug.dll"])
    except Exception as e:
        messagebox.showerror("Hata", f"Donanım Güvenle Kaldır penceresi açılamadı:\n{e}")

def unhide_drive_files_dialog(parent):
    kernel32 = ctypes.windll.kernel32
    mask = kernel32.GetLogicalDrives()
    active_drives = [chr(ord('A') + i) + ":" for i in range(26) if (mask & (1 << i))]

    drive = simpledialog.askstring(
        "Gizli Dosyaları Görünür Yap",
        f"Temizlemek istediğiniz sürücü harfini girin (Örn: E:)\n\nMevcut Sürücüler: {', '.join(active_drives)}",
        parent=parent
    )
    if not drive:
        return

    clean_drive = drive.strip().upper()
    if not clean_drive.endswith(":"):
        clean_drive += ":"

    if clean_drive not in active_drives:
        messagebox.showerror("Hata", f"'{clean_drive}' sürücüsü bulunamadı veya bağlı değil!", parent=parent)
        return

    target = f"{clean_drive}\\*"
    try:
        subprocess.run(["attrib", "-h", "-r", "-s", "/s", "/d", target],
                       capture_output=True, check=False,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        toggle_hidden_files(True)
        messagebox.showinfo("Başarılı", f"'{clean_drive}' sürücüsündeki tüm gizli ve sistem dosyaları görünür yapıldı.", parent=parent)
    except Exception as e:
        messagebox.showerror("Hata", f"İşlem sırasında hata oluştu:\n{e}", parent=parent)

# ==============================================================================
# 11. Polished Modal Dialogs (Change Password, Runtime Verify, About)
# ==============================================================================
class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, has_existing_password: bool = False):
        super().__init__(parent)
        self.title("Yönetici Şifresi")
        self.has_existing = has_existing_password
        self.result = None

        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        w, h = 360, 275 if self.has_existing else 225
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

        frame = ttk.Frame(self, padding=(20, 16, 20, 14))
        frame.pack(fill=tk.BOTH, expand=True)

        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="Yönetici Şifresini Belirle",
            font=("Segoe UI", 11, "bold"),
            foreground="#1B4F72"
        ).pack(side=tk.LEFT)

        self.old_entry = None
        if self.has_existing:
            ttk.Label(frame, text="Eski Şifre:", font=("Segoe UI", 9)).pack(anchor="w")
            self.old_entry = ttk.Entry(frame, show="●", font=("Segoe UI", 9))
            self.old_entry.pack(fill=tk.X, pady=(2, 6))
            self.old_entry.focus_set()

        ttk.Label(frame, text="Yeni Şifre:", font=("Segoe UI", 9)).pack(anchor="w")
        self.new_entry = ttk.Entry(frame, show="●", font=("Segoe UI", 9))
        self.new_entry.pack(fill=tk.X, pady=(2, 6))
        if not self.has_existing:
            self.new_entry.focus_set()

        ttk.Label(frame, text="Yeni Şifreyi Onayla:", font=("Segoe UI", 9)).pack(anchor="w")
        self.confirm_entry = ttk.Entry(frame, show="●", font=("Segoe UI", 9))
        self.confirm_entry.pack(fill=tk.X, pady=(2, 6))

        self.var_show_pwd = tk.BooleanVar(value=False)
        self.chk_show = ttk.Checkbutton(
            frame,
            text="Şifreyi Göster",
            variable=self.var_show_pwd,
            command=self.toggle_show_pwd
        )
        self.chk_show.pack(anchor="w", pady=(2, 10))

        btn_box = ttk.Frame(frame)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_box,
            text="Kaydet",
            font=("Segoe UI Semibold", 9),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.on_save
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_box,
            text="İptal",
            font=("Segoe UI", 9),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.on_cancel
        ).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.on_cancel())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def toggle_show_pwd(self):
        mask = "" if self.var_show_pwd.get() else "●"
        if self.old_entry:
            self.old_entry.config(show=mask)
        self.new_entry.config(show=mask)
        self.confirm_entry.config(show=mask)

    def on_save(self):
        old_val = self.old_entry.get() if self.old_entry else ""
        new_val = self.new_entry.get()
        confirm_val = self.confirm_entry.get()

        if not new_val:
            messagebox.showerror("Hata", "Yeni şifre boş bırakılamaz!", parent=self)
            return
        if new_val != confirm_val:
            messagebox.showerror("Hata", "Girdiğiniz yeni şifreler birbiriyle uyuşmuyor!", parent=self)
            return

        self.result = {"old": old_val, "new": new_val}
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()

class VerifyPasswordDialog(tk.Toplevel):
    def __init__(self, parent, expected_hash: str, salt: str):
        super().__init__(parent)
        self.title("Yönetici Şifresi")
        self.expected_hash = expected_hash
        self.salt = salt
        self.verified = False

        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        w, h = 330, 160
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")

        frame = ttk.Frame(self, padding=(20, 14, 20, 14))
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Kilidi kaldırmak için şifrenizi girin:", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        self.entry_pwd = ttk.Entry(frame, show="●", font=("Segoe UI", 10))
        self.entry_pwd.pack(fill=tk.X, pady=(0, 6))
        self.entry_pwd.focus_set()

        self.var_show = tk.BooleanVar(value=False)
        def toggle_show():
            self.entry_pwd.config(show="" if self.var_show.get() else "●")
        ttk.Checkbutton(frame, text="Şifreyi Göster", variable=self.var_show, command=toggle_show).pack(anchor="w", pady=(0, 10))

        btn_box = ttk.Frame(frame)
        btn_box.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(
            btn_box,
            text="Tamam",
            font=("Segoe UI Semibold", 9),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.on_submit
        ).pack(side=tk.RIGHT, padx=(6, 0))

        tk.Button(
            btn_box,
            text="İptal",
            font=("Segoe UI", 9),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=12,
            pady=3,
            cursor="hand2",
            command=self.on_cancel
        ).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self.on_submit())
        self.bind("<Escape>", lambda e: self.on_cancel())
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window(self)

    def on_submit(self):
        val = self.entry_pwd.get()
        if verify_password(val, self.salt, self.expected_hash):
            self.verified = True
            self.destroy()
        else:
            messagebox.showerror("Hata", "Hatalı şifre!", parent=self)
            self.entry_pwd.delete(0, tk.END)

    def on_cancel(self):
        self.verified = False
        self.destroy()

# ==============================================================================
# 12. Main Application Window (USBSentryApp)
# ==============================================================================
class USBSentryApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("USB Sentry Pro v1.5.0 - Yunus İNAN")
        self.root.geometry("430x215")
        self.root.resizable(False, False)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(50, (sw - 430) // 2)
        y = max(50, (sh - 215) // 2)
        self.root.geometry(f"430x215+{x}+{y}")

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        # Load Icon
        icon_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "app_icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

        # Protocol handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close_window)

        # Load Persistent Configuration
        self.config = load_config()

        # State Variables
        self.mode_var = tk.IntVar(value=get_current_mode())
        self.var_lock_settings = tk.BooleanVar(value=self.config.get("lock_active", False))
        self.var_block_install = tk.BooleanVar(value=is_device_install_blocked())
        self.var_protect_driver = tk.BooleanVar(value=is_driver_files_protected())
        self.var_autorun = tk.BooleanVar(value=is_autorun_disabled())
        self.var_hidden_files = tk.BooleanVar(value=is_hidden_files_shown())
        self.var_file_ext = tk.BooleanVar(value=is_file_extensions_shown())

        # Peripheral Class Variables
        self.var_cddvd = tk.IntVar(value=get_class_guid_policy(GUID_CD_DVD))
        self.var_floppy = tk.IntVar(value=get_class_guid_policy(GUID_FLOPPY))
        self.var_tape = tk.IntVar(value=get_class_guid_policy(GUID_TAPE))
        self.var_wpd = tk.IntVar(value=get_class_guid_policy(GUID_WPD))

        # Setup Styles & Typography
        self.setup_styles()

        # Generate & Persist Real 16x16 Menu Icons
        self._menu_icons = create_menu_icons()

        # Build Main Interface Elements
        self.setup_menu()
        self.setup_main_layout()

        # Check Startup Lock
        self.lock_overlay = None
        pwd_hash = self.config.get("password_hash", "")
        lock_active = self.config.get("lock_active", False)

        if pwd_hash and lock_active:
            self.is_unlocked = False
            self.show_startup_lock_overlay()
        else:
            self.is_unlocked = True
            self.show_main_interface()

        self.apply_changes = self.on_apply

        # Global Accelerators
        self.root.bind("<F5>", lambda e: self.sync_all_states())
        self.root.bind("<F1>", lambda e: self.show_about_dialog())
        self.root.bind("<Control-s>", lambda e: self.on_apply())
        self.root.bind("<Control-S>", lambda e: self.on_apply())

    def setup_styles(self):
        style = ttk.Style()
        try:
            for theme in ["vista", "winnative", "clam"]:
                if theme in style.theme_names():
                    style.theme_use(theme)
                    break
        except Exception:
            pass
        style.configure("TRadiobutton", font=("Segoe UI", 9), padding=(4, 5))
        style.configure("TLabel", font=("Segoe UI", 9))

    # --------------------------------------------------------------------------
    # Startup Lock Screen Overlay (In-Window Modal Frame)
    # --------------------------------------------------------------------------
    def show_startup_lock_overlay(self):
        self.root.config(menu="")
        self.attempts = 3

        self.lock_overlay = ttk.Frame(self.root, padding=(28, 20, 28, 16))
        self.lock_overlay.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            self.lock_overlay,
            text="Yönetici Doğrulaması",
            font=("Segoe UI", 12, "bold"),
            foreground="#1B4F72"
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            self.lock_overlay,
            text="Ayarlar kilitlidir. Devam etmek için lütfen şifrenizi girin:",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(0, 10))

        entry_row = ttk.Frame(self.lock_overlay)
        entry_row.pack(fill=tk.X, pady=(0, 6))

        self.lock_entry = ttk.Entry(entry_row, show="●", font=("Segoe UI", 10))
        self.lock_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.lock_entry.focus_set()

        self.var_show_lock_pwd = tk.BooleanVar(value=False)
        def toggle_show():
            mask = "" if self.var_show_lock_pwd.get() else "●"
            self.lock_entry.config(show=mask)

        chk_show = ttk.Checkbutton(
            entry_row,
            text="Şifreyi Göster",
            variable=self.var_show_lock_pwd,
            command=toggle_show
        )
        chk_show.pack(side=tk.RIGHT)

        self.lock_warning = ttk.Label(
            self.lock_overlay,
            text="",
            font=("Segoe UI", 8),
            foreground="#C0392B"
        )
        self.lock_warning.pack(anchor="w", pady=(2, 6))

        btn_row = ttk.Frame(self.lock_overlay)
        btn_row.pack(fill=tk.X, side=tk.BOTTOM)

        btn_login = tk.Button(
            btn_row,
            text="Giriş Yap",
            font=("Segoe UI Semibold", 9),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=14,
            pady=3,
            cursor="hand2",
            command=self.on_unlock_submit
        )
        btn_login.pack(side=tk.RIGHT)

        self.lock_entry.bind("<Return>", lambda e: self.on_unlock_submit())

    def on_unlock_submit(self):
        entered = self.lock_entry.get()
        pwd_salt = self.config.get("password_salt", "")
        pwd_hash = self.config.get("password_hash", "")

        if verify_password(entered, pwd_salt, pwd_hash):
            self.is_unlocked = True
            self.lock_overlay.destroy()
            self.lock_overlay = None
            self.show_main_interface()
        else:
            self.attempts -= 1
            if self.attempts <= 0:
                messagebox.showerror("Hata", "3 kez hatalı şifre girildi. Uygulama sonlandırılıyor.", parent=self.root)
                self.root.destroy()
                sys.exit(0)
            else:
                self.lock_warning.config(text=f"Hatalı şifre! Kalan deneme hakkı: {self.attempts}")
                self.lock_entry.delete(0, tk.END)

    def show_main_interface(self):
        self.root.config(menu=self.menubar)
        self.main_container.pack(fill=tk.BOTH, expand=True)
        self.draw_usb_canvas(self.mode_var.get())
        self.refresh_lock_state()

    def on_close_window(self):
        if self.lock_overlay is not None:
            self.root.destroy()
            sys.exit(0)
        self.root.destroy()

    # --------------------------------------------------------------------------
    # Menus with Real 16x16 PhotoImage Icons & Clean Labels
    # --------------------------------------------------------------------------
    def setup_menu(self):
        self.menubar = tk.Menu(self.root)

        # 1. AYARLAR MENÜSÜ
        self.menu_settings = tk.Menu(self.menubar, tearoff=0)
        self.menu_settings.add_checkbutton(
            label="Ayarları Kilitle",
            image=self._menu_icons["lock"],
            compound="left",
            variable=self.var_lock_settings,
            command=self.on_toggle_lock_settings
        )
        self.menu_settings.add_command(
            label="Şifreyi Değiştir...",
            image=self._menu_icons["key"],
            compound="left",
            command=self.on_change_password
        )
        self.menu_settings.add_separator()
        self.menu_settings.add_command(
            label="Yenile",
            image=self._menu_icons["refresh"],
            compound="left",
            accelerator="F5",
            command=self.sync_all_states
        )
        self.menu_settings.add_command(
            label="Çıkış",
            image=self._menu_icons["exit"],
            compound="left",
            accelerator="Alt+F4",
            command=self.root.quit
        )
        self.menubar.add_cascade(label="Ayarlar", menu=self.menu_settings)

        # 2. SEÇENEKLER MENÜSÜ
        self.menu_options = tk.Menu(self.menubar, tearoff=0)

        self.menu_options.add_command(
            label="Tüm Çıkarılabilir Aygıtlara İzin Ver",
            image=self._menu_icons["allow_all"],
            compound="left",
            command=self.opt_allow_all_removable
        )
        self.menu_options.add_command(
            label="Tüm Çıkarılabilir Aygıtları Engelle",
            image=self._menu_icons["block_all"],
            compound="left",
            command=self.opt_block_all_removable
        )
        self.menu_options.add_separator()

        # Cascade: CD-DVD Aygıtları
        self.sub_cddvd = tk.Menu(self.menu_options, tearoff=0)
        self.sub_cddvd.add_radiobutton(label="Okuma ve Yazma İzni Ver", variable=self.var_cddvd, value=1,
                                       command=lambda: set_class_guid_policy(GUID_CD_DVD, 1))
        self.sub_cddvd.add_radiobutton(label="Sadece Okuma İzni Ver", variable=self.var_cddvd, value=2,
                                       command=lambda: set_class_guid_policy(GUID_CD_DVD, 2))
        self.sub_cddvd.add_radiobutton(label="Aygıtı Engelle", variable=self.var_cddvd, value=3,
                                       command=lambda: set_class_guid_policy(GUID_CD_DVD, 3))
        self.menu_options.add_cascade(label="CD-DVD Aygıtları", image=self._menu_icons["cd"], compound="left", menu=self.sub_cddvd)

        # Cascade: Floppy Aygıtları
        self.sub_floppy = tk.Menu(self.menu_options, tearoff=0)
        self.sub_floppy.add_radiobutton(label="Okuma ve Yazma İzni Ver", variable=self.var_floppy, value=1,
                                        command=lambda: set_class_guid_policy(GUID_FLOPPY, 1))
        self.sub_floppy.add_radiobutton(label="Sadece Okuma İzni Ver", variable=self.var_floppy, value=2,
                                        command=lambda: set_class_guid_policy(GUID_FLOPPY, 2))
        self.sub_floppy.add_radiobutton(label="Aygıtı Engelle", variable=self.var_floppy, value=3,
                                        command=lambda: set_class_guid_policy(GUID_FLOPPY, 3))
        self.menu_options.add_cascade(label="Floppy Aygıtları", image=self._menu_icons["floppy"], compound="left", menu=self.sub_floppy)

        # Cascade: Tape Aygıtları
        self.sub_tape = tk.Menu(self.menu_options, tearoff=0)
        self.sub_tape.add_radiobutton(label="Okuma ve Yazma İzni Ver", variable=self.var_tape, value=1,
                                      command=lambda: set_class_guid_policy(GUID_TAPE, 1))
        self.sub_tape.add_radiobutton(label="Sadece Okuma İzni Ver", variable=self.var_tape, value=2,
                                      command=lambda: set_class_guid_policy(GUID_TAPE, 2))
        self.sub_tape.add_radiobutton(label="Aygıtı Engelle", variable=self.var_tape, value=3,
                                      command=lambda: set_class_guid_policy(GUID_TAPE, 3))
        self.menu_options.add_cascade(label="Tape Aygıtları", image=self._menu_icons["tape"], compound="left", menu=self.sub_tape)

        # Cascade: WPD Aygıtları (Telefon/MTP)
        self.sub_wpd = tk.Menu(self.menu_options, tearoff=0)
        self.sub_wpd.add_radiobutton(label="İzin Ver", variable=self.var_wpd, value=1,
                                     command=lambda: set_class_guid_policy(GUID_WPD, 1))
        self.sub_wpd.add_radiobutton(label="Engelle", variable=self.var_wpd, value=3,
                                     command=lambda: set_class_guid_policy(GUID_WPD, 3))
        self.menu_options.add_cascade(label="WPD Aygıtları (Telefon/MTP)", image=self._menu_icons["phone"], compound="left", menu=self.sub_wpd)

        self.menu_options.add_separator()

        # Checkbuttons
        self.menu_options.add_checkbutton(
            label="Usb Aygıtlarının Yüklenmesini Engelle",
            image=self._menu_icons["stop_install"],
            compound="left",
            variable=self.var_block_install,
            command=self.on_toggle_block_install
        )
        self.menu_options.add_checkbutton(
            label="Sürücü Dosyalarını Koru (Yazma Koruması)",
            image=self._menu_icons["protect_files"],
            compound="left",
            variable=self.var_protect_driver,
            command=self.on_toggle_protect_driver
        )
        self.menu_options.add_checkbutton(
            label="Otomatik Çalıştırmayı Devre Dışı Bırak",
            image=self._menu_icons["autorun"],
            compound="left",
            variable=self.var_autorun,
            command=self.on_toggle_autorun
        )
        self.menu_options.add_command(
            label="Sürücüdeki Gizli Dosyaları Görünür Yap",
            image=self._menu_icons["hidden_files"],
            compound="left",
            command=lambda: unhide_drive_files_dialog(self.root)
        )
        self.menu_options.add_checkbutton(
            label="Dosya Uzantılarını Göster",
            image=self._menu_icons["file_ext"],
            compound="left",
            variable=self.var_file_ext,
            command=self.on_toggle_file_ext
        )
        self.menu_options.add_separator()
        self.menu_options.add_command(
            label="Donanımı Güvenle Kaldır",
            image=self._menu_icons["eject"],
            compound="left",
            command=open_safely_remove_dialog
        )
        self.menubar.add_cascade(label="Seçenekler", menu=self.menu_options)

        # 3. YARDIM MENÜSÜ
        self.menu_help = tk.Menu(self.menubar, tearoff=0)
        self.menu_help.add_command(
            label="Kılavuz / Bilgi...",
            image=self._menu_icons["info"],
            compound="left",
            command=self.show_help_dialog
        )
        self.menu_help.add_separator()
        self.menu_help.add_command(
            label="Hakkında",
            image=self._menu_icons["about"],
            compound="left",
            accelerator="F1",
            command=self.show_about_dialog
        )
        self.menubar.add_cascade(label="Yardım", menu=self.menu_help)

    # --------------------------------------------------------------------------
    # Main Window Layout
    # --------------------------------------------------------------------------
    def setup_main_layout(self):
        self.main_container = ttk.Frame(self.root)

        top_container = ttk.Frame(self.main_container, padding=(14, 10, 14, 4))
        top_container.pack(fill=tk.BOTH, expand=True)

        # Left Column: Exact 105x105 USB Canvas
        self.left_frame = ttk.Frame(top_container, width=105, height=105)
        self.left_frame.pack(side=tk.LEFT, padx=(4, 16), pady=0)
        self.left_frame.pack_propagate(False)

        self.canvas = tk.Canvas(self.left_frame, width=105, height=105, bg="#F0F0F0", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Right Column: 3 Styled Native Radio Buttons (Segoe UI 9pt)
        self.right_frame = ttk.Frame(top_container)
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=2)

        self.radio_allow = ttk.Radiobutton(
            self.right_frame,
            text="Okuma ve Yazma İzni Ver (Varsayılan)",
            variable=self.mode_var,
            value=MODE_ALLOW,
            command=self.on_radio_select
        )
        self.radio_allow.pack(anchor="w", pady=(1, 5))

        self.radio_ro = ttk.Radiobutton(
            self.right_frame,
            text="Sadece Okuma İzni Ver",
            variable=self.mode_var,
            value=MODE_READ_ONLY,
            command=self.on_radio_select
        )
        self.radio_ro.pack(anchor="w", pady=(1, 5))

        self.radio_block = ttk.Radiobutton(
            self.right_frame,
            text="Usb Depolama Aygıtlarını Engelle",
            variable=self.mode_var,
            value=MODE_BLOCK,
            command=self.on_radio_select
        )
        self.radio_block.pack(anchor="w", pady=(1, 5))

        # Bottom Bar: Lock Status Banner & "Değişiklikleri Uygula" Button
        bottom_frame = ttk.Frame(self.main_container, padding=(14, 2, 14, 10))
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.lock_banner = ttk.Label(
            bottom_frame,
            text="",
            font=("Segoe UI", 8, "italic"),
            foreground="#C0392B"
        )
        self.lock_banner.pack(side=tk.LEFT, padx=(4, 0))

        self.btn_apply = tk.Button(
            bottom_frame,
            text="Değişiklikleri Uygula",
            font=("Segoe UI Semibold", 10),
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.apply_changes
        )
        self.btn_apply.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 4))

    # --------------------------------------------------------------------------
    # Pixel-Perfect 105x105 USB Canvas Artwork (Native Win32 Proportions)
    # --------------------------------------------------------------------------
    def draw_usb_canvas(self, mode: int):
        self.canvas.delete("all")
        cx = 52

        # 1. Metallic USB Connector Plug (Width: 38px, Height: 24px)
        self.canvas.create_rectangle(33, 10, 71, 34, fill="#B0BEC5", outline="#78909C", width=1)
        self.canvas.create_rectangle(40, 16, 46, 25, fill="#37474F", outline="")
        self.canvas.create_rectangle(58, 16, 64, 25, fill="#37474F", outline="")
        self.canvas.create_line(35, 12, 69, 12, fill="#FFFFFF", width=1)

        # 2. Plastic Collar / Neck Band
        self.canvas.create_rectangle(27, 32, 77, 38, fill="#263238", outline="#102027", width=1)

        # 3. Compact Horizontal Rectangular Body (Width: 78px, Height: 58px)
        colors = {
            MODE_ALLOW: ("#27AE60", "#2ECC71", "#1B4F72"),
            MODE_READ_ONLY: ("#F39C12", "#F1C40F", "#7E5109"),
            MODE_BLOCK: ("#C0392B", "#E74C3C", "#641E16"),
        }
        base_col, hi_col, border_col = colors.get(mode, colors[MODE_ALLOW])

        self.canvas.create_rectangle(13, 38, 91, 96, fill=base_col, outline=border_col, width=2)
        self.canvas.create_line(16, 42, 16, 92, fill=hi_col, width=2)

        # 4. White USB Trident Logo (Clean & Proportionate)
        self.canvas.create_line(cx, 54, cx, 82, fill="#FFFFFF", width=2)
        self.canvas.create_polygon(cx, 46, cx - 5, 54, cx + 5, 54, fill="#FFFFFF", outline="")
        self.canvas.create_line(cx, 66, cx - 9, 61, cx - 9, 56, fill="#FFFFFF", width=2)
        self.canvas.create_oval(cx - 12, 53, cx - 6, 59, fill="#FFFFFF", outline="")
        self.canvas.create_line(cx, 70, cx + 9, 65, cx + 9, 60, fill="#FFFFFF", width=2)
        self.canvas.create_rectangle(cx + 6, 57, cx + 12, 63, fill="#FFFFFF", outline="")
        self.canvas.create_oval(cx - 3, 82, cx + 3, 88, fill="#FFFFFF", outline="")

        # 5. LED Indicator Light
        led_col = {MODE_ALLOW: "#58D68D", MODE_READ_ONLY: "#F4D03F", MODE_BLOCK: "#F1948A"}.get(mode, "#58D68D")
        self.canvas.create_oval(cx - 2, 90, cx + 2, 94, fill=led_col, outline="")

        # 6. Mode 3 Block Prohibition Badge
        if mode == MODE_BLOCK:
            self.canvas.create_oval(37, 52, 67, 82, outline="#FFFFFF", width=4)
            self.canvas.create_oval(38, 53, 66, 81, outline="#922B21", width=3)
            self.canvas.create_line(43, 58, 61, 76, fill="#922B21", width=3)

    # --------------------------------------------------------------------------
    # Radio & Apply Event Handlers
    # --------------------------------------------------------------------------
    def on_radio_select(self):
        if not self.is_unlocked:
            return
        self.draw_usb_canvas(self.mode_var.get())

    def on_apply(self):
        if not self.is_unlocked:
            messagebox.showwarning("Kilitli", "Ayarlar kilitli! Lütfen önce yönetici kilidini açın.", parent=self.root)
            return

        target_mode = self.mode_var.get()
        apply_mode(target_mode)

        mode_names = {
            MODE_ALLOW: "Okuma ve Yazma İzni Verildi (USB erişimi açık).",
            MODE_READ_ONLY: "Sadece Okuma İzni Verildi (Yazma koruması etkin).",
            MODE_BLOCK: "Usb Depolama Aygıtları Tamamen Engellendi."
        }
        self.draw_usb_canvas(target_mode)
        messagebox.showinfo("USB Sentry Pro", mode_names.get(target_mode, "Değişiklikler uygulandı."), parent=self.root)

    def apply_changes(self):
        return self.on_apply()

    # --------------------------------------------------------------------------
    # Synchronize All States (F5)
    # --------------------------------------------------------------------------
    def sync_all_states(self):
        cur_mode = get_current_mode()
        self.mode_var.set(cur_mode)
        self.draw_usb_canvas(cur_mode)

        self.var_block_install.set(is_device_install_blocked())
        self.var_protect_driver.set(is_driver_files_protected())
        self.var_autorun.set(is_autorun_disabled())
        self.var_hidden_files.set(is_hidden_files_shown())
        self.var_file_ext.set(is_file_extensions_shown())

        self.var_cddvd.set(get_class_guid_policy(GUID_CD_DVD))
        self.var_floppy.set(get_class_guid_policy(GUID_FLOPPY))
        self.var_tape.set(get_class_guid_policy(GUID_TAPE))
        self.var_wpd.set(get_class_guid_policy(GUID_WPD))

        self.refresh_lock_state()

    # --------------------------------------------------------------------------
    # Lock / Unlock Management
    # --------------------------------------------------------------------------
    def refresh_lock_state(self):
        state = "normal" if self.is_unlocked else "disabled"

        self.radio_allow.config(state=state)
        self.radio_ro.config(state=state)
        self.radio_block.config(state=state)
        self.btn_apply.config(state=state)

        # Options menu items
        menu_state = "normal" if self.is_unlocked else "disabled"
        for i in range(self.menu_options.index("end") + 1):
            try:
                self.menu_options.entryconfig(i, state=menu_state)
            except Exception:
                pass

        if not self.is_unlocked:
            self.lock_banner.config(text="Ayarlar Kilitli (Korumalı)")
        else:
            self.lock_banner.config(text="")

    def on_toggle_lock_settings(self):
        want_lock = self.var_lock_settings.get()

        if want_lock:
            pwd_hash = self.config.get("password_hash", "")
            pwd_salt = self.config.get("password_salt", "")

            if not pwd_hash:
                messagebox.showinfo(
                    "Şifre Gereklidir",
                    "Ayarları kilitlemek için lütfen önce bir yönetici şifresi belirleyin.",
                    parent=self.root
                )
                dlg = ChangePasswordDialog(self.root, has_existing_password=False)
                if dlg.result:
                    salt = secrets.token_hex(16)
                    h = hash_password(dlg.result["new"], salt)
                    self.config["password_salt"] = salt
                    self.config["password_hash"] = h
                    self.config["lock_active"] = True
                    save_config(self.config)
                    self.is_unlocked = False
                    self.refresh_lock_state()
                    messagebox.showinfo("USB Sentry Pro", "Yönetici şifresi kaydedildi ve ayarlar kilitlendi.", parent=self.root)
                else:
                    self.var_lock_settings.set(False)
            else:
                self.config["lock_active"] = True
                save_config(self.config)
                self.is_unlocked = False
                self.refresh_lock_state()
                messagebox.showinfo("USB Sentry Pro", "Ayarlar kilitlendi.", parent=self.root)

        else:
            pwd_hash = self.config.get("password_hash", "")
            pwd_salt = self.config.get("password_salt", "")

            if pwd_hash:
                dlg = VerifyPasswordDialog(self.root, expected_hash=pwd_hash, salt=pwd_salt)
                if dlg.verified:
                    self.config["lock_active"] = False
                    save_config(self.config)
                    self.is_unlocked = True
                    self.refresh_lock_state()
                    messagebox.showinfo("USB Sentry Pro", "Ayarlar kilidi başarıyla kaldırıldı.", parent=self.root)
                else:
                    self.var_lock_settings.set(True)
            else:
                self.config["lock_active"] = False
                save_config(self.config)
                self.is_unlocked = True
                self.refresh_lock_state()

    def on_change_password(self):
        has_pwd = bool(self.config.get("password_hash", ""))
        dlg = ChangePasswordDialog(self.root, has_existing_password=has_pwd)
        if dlg.result:
            if has_pwd:
                old_salt = self.config.get("password_salt", "")
                old_hash = self.config.get("password_hash", "")
                if not verify_password(dlg.result["old"], old_salt, old_hash):
                    messagebox.showerror("Hata", "Eski şifre hatalı! Şifre değiştirilemedi.", parent=self.root)
                    return

            new_salt = secrets.token_hex(16)
            new_hash = hash_password(dlg.result["new"], new_salt)
            self.config["password_salt"] = new_salt
            self.config["password_hash"] = new_hash
            self.config["lock_active"] = True
            save_config(self.config)
            self.var_lock_settings.set(True)
            messagebox.showinfo("Başarılı", "Yönetici şifresi başarıyla güncellendi ve kilit aktif edildi.", parent=self.root)

    # --------------------------------------------------------------------------
    # Options Menu Actions
    # --------------------------------------------------------------------------
    def opt_allow_all_removable(self):
        if not self.is_unlocked:
            return
        delete_reg_value(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All")
        set_class_guid_policy(GUID_USB_DISKS, 1)
        set_class_guid_policy(GUID_CD_DVD, 1)
        set_class_guid_policy(GUID_FLOPPY, 1)
        set_class_guid_policy(GUID_TAPE, 1)
        set_class_guid_policy(GUID_WPD, 1)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 3)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_STORAGE_POLICIES, "WriteProtect", 0)
        self.sync_all_states()
        messagebox.showinfo("USB Sentry Pro", "Tüm çıkarılabilir aygıtlara tam izin verildi.", parent=self.root)

    def opt_block_all_removable(self):
        if not self.is_unlocked:
            return
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_REMOVABLE_DEVICES, "Deny_All", 1)
        set_class_guid_policy(GUID_USB_DISKS, 3)
        set_class_guid_policy(GUID_CD_DVD, 3)
        set_class_guid_policy(GUID_FLOPPY, 3)
        set_class_guid_policy(GUID_TAPE, 3)
        set_class_guid_policy(GUID_WPD, 3)
        set_reg_dword(winreg.HKEY_LOCAL_MACHINE, KEY_USBSTOR, "Start", 4)
        self.sync_all_states()
        messagebox.showinfo("USB Sentry Pro", "Tüm çıkarılabilir aygıtlar engellendi.", parent=self.root)

    def on_toggle_block_install(self):
        if not self.is_unlocked:
            return
        val = self.var_block_install.get()
        toggle_device_install_block(val)
        actual = is_device_install_blocked()
        self.var_block_install.set(actual)
        self.config["block_install_enabled"] = actual
        save_config(self.config)

        if actual:
            msg = (
                "USB Aygıtlarının Yüklenmesini Engelleme ETKİNLEŞTİRİLDİ.\n\n"
                "• Şu anda takılı olan USB sürücüler dinamik beyaz listeye alındı.\n"
                "• Bu andan sonra bilgisayara takılacak diğer tüm USB bellekler kesin olarak engellenir.\n"
                "• Enum\\USBSTOR kayıt defteri izinleri kilitlendi."
            )
        else:
            msg = (
                "USB Aygıtlarının Yüklenmesini Engelleme KALDIRILDI.\n\n"
                "• Beyaz liste ve Enum\\USBSTOR kilitleri kaldırıldı.\n"
                "• Tüm USB sürücüler normal şekilde bağlanabilir."
            )
        messagebox.showinfo("USB Sentry Pro", msg, parent=self.root)

    def on_toggle_protect_driver(self):
        if not self.is_unlocked:
            return
        val = self.var_protect_driver.get()
        toggle_driver_files_protection(val)
        actual = is_driver_files_protected()
        self.var_protect_driver.set(actual)
        self.config["anti_tamper_enabled"] = actual
        save_config(self.config)

        if actual:
            messagebox.showinfo("USB Sentry Pro", "Sürücü dosyaları (usbstor.inf/pnf) yazma korumasıyla kilitlendi.", parent=self.root)
        else:
            messagebox.showinfo("USB Sentry Pro", "Sürücü dosyalarının yazma koruması kaldırıldı.", parent=self.root)

    def on_toggle_autorun(self):
        if not self.is_unlocked:
            return
        toggle_autorun(self.var_autorun.get())

    def on_toggle_file_ext(self):
        if not self.is_unlocked:
            return
        toggle_file_extensions(self.var_file_ext.get())

    # --------------------------------------------------------------------------
    # Dialogs: Help & About
    # --------------------------------------------------------------------------
    def show_help_dialog(self):
        info = (
            "USB Sentry Pro - Kullanım Kılavuzu\n\n"
            "1. Okuma ve Yazma İzni Ver:\n"
            "   USB depolama aygıtları tam erişim ile normal şekilde çalışır.\n\n"
            "2. Sadece Okuma İzni Ver:\n"
            "   Aygıtlardan veri okunabilir; ancak USB'ye yeni veri yazılamaz veya silinemez.\n\n"
            "3. Usb Depolama Aygıtlarını Engelle:\n"
            "   Tüm USB flash bellek ve taşınabilir disk erişimini tamamen devre dışı bırakır.\n\n"
            "4. Usb Aygıtlarının Yüklenmesini Engelle:\n"
            "   Şu an takılı olan sürücüleri beyaz listeye alır, yeni takılacak USB'leri engeller.\n\n"
            "5. Seçenekler Menüsü:\n"
            "   CD-DVD, Floppy, Tape ve WPD (Telefon) aygıtlarını ayrı ayrı yönetebilirsiniz.\n\n"
            "6. Ayarları Kilitle:\n"
            "   Yetkisiz kişilerin ayarları değiştirmesini SHA-256 şifresi ile önler."
        )
        messagebox.showinfo("Kullanım Kılavuzu", info, parent=self.root)

    def show_about_dialog(self):
        about_dlg = tk.Toplevel(self.root)
        about_dlg.title("Hakkında - USB Sentry Pro")
        about_dlg.geometry("400x290")
        about_dlg.resizable(False, False)
        about_dlg.transient(self.root)
        about_dlg.grab_set()

        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 145
        about_dlg.geometry(f"+{max(50, x)}+{max(50, y)}")

        frame = ttk.Frame(about_dlg, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        lbl_title = ttk.Label(frame, text="USB Sentry Pro", font=("Segoe UI", 14, "bold"), foreground="#1B4F72")
        lbl_title.pack(anchor="center", pady=(0, 2))

        lbl_ver = ttk.Label(frame, text="Sürüm: 1.5.0 (64-bit Professional)", font=("Segoe UI", 9, "bold"))
        lbl_ver.pack(anchor="center", pady=(0, 10))

        lbl_desc = ttk.Label(
            frame,
            text="Gelişmiş USB Port & Çıkarılabilir Depolama Erişim Güvenlik Yöneticisi\n"
                 "Kurumsal düzeyde PnP kısıtlaması, dinamik donanım beyaz listesi\n"
                 "ve sürücü anti-tamper koruma motoru.",
            font=("Segoe UI", 8),
            justify="center"
        )
        lbl_desc.pack(anchor="center", pady=(0, 12))

        sep = ttk.Separator(frame, orient="horizontal")
        sep.pack(fill="x", pady=8)

        lbl_dev = ttk.Label(frame, text="Geliştirici: Yunus İNAN", font=("Segoe UI", 10, "bold"), foreground="#2C3E50")
        lbl_dev.pack(anchor="center", pady=(0, 4))

        lbl_copy = ttk.Label(
            frame,
            text="Copyright © 2026 Yunus İNAN tarafından geliştirilmiştir.\nTüm hakları saklıdır.",
            font=("Segoe UI", 8),
            justify="center",
            foreground="#5D6D7E"
        )
        lbl_copy.pack(anchor="center", pady=(0, 14))

        btn_close = tk.Button(
            frame,
            text="Tamam",
            font=("Segoe UI", 9),
            width=10,
            bg="#F3F3F3",
            fg="#000000",
            activebackground="#E5E5E5",
            activeforeground="#000000",
            relief="groove",
            bd=1,
            pady=3,
            cursor="hand2",
            command=about_dlg.destroy
        )
        btn_close.pack(anchor="center")

# ==============================================================================
# 13. Application Entry Point
# ==============================================================================
def main():
    ensure_admin()
    root = tk.Tk()
    app = USBSentryApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
