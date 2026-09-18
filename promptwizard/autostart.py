from __future__ import annotations

import os
import sys

__all__ = ["APP_KEY", "RUN_KEY", "default_command", "is_enabled", "set_enabled"]

APP_KEY = "PromptWizard"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def default_command() -> str:
    executable = sys.executable or "python"
    if getattr(sys, "frozen", False):
        return f'"{executable}"'
    return f'"{executable}" -m promptwizard gui'


def supported() -> bool:
    return sys.platform.startswith("win")


def _winreg():
    import winreg

    return winreg


def is_enabled(key_path: str = RUN_KEY, name: str = APP_KEY) -> bool:
    if not supported():
        return False
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return False
    except ImportError:
        return False
    return bool(value)


def set_enabled(enabled: bool, key_path: str = RUN_KEY, name: str = APP_KEY, command: str = "") -> bool:
    if not supported():
        return False
    winreg = _winreg()
    if enabled:
        value = command or default_command()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass
    return False


def current_command(key_path: str = RUN_KEY, name: str = APP_KEY) -> str:
    if not supported():
        return ""
    try:
        winreg = _winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, name)
        return str(value)
    except (OSError, ImportError):
        return ""


def state(key_path: str = RUN_KEY, name: str = APP_KEY) -> dict[str, object]:
    return {
        "supported": supported(),
        "enabled": is_enabled(key_path, name),
        "command": current_command(key_path, name),
        "platform": os.name,
    }
