"""
macOS "Launch at Login" via a per-user LaunchAgent.

The agent runs the app binary directly (not via `open`) so launchd can supervise
it: KeepAlive/SuccessfulExit=false restarts the app if it crashes, but not after
the user chooses Quit (which exits with status 0). Changes take effect at the
next login; the running instance is never started or killed by this module.
"""
import os
import plistlib
import sys
from typing import Optional

LABEL = "com.frown.guard"
AGENT_PATH = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", f"{LABEL}.plist")
LOG_PATH = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Frown Guard.log")


def app_executable() -> Optional[str]:
    """Path to the bundled executable, or None when not running from a .app bundle."""
    if sys.platform != "darwin" or not getattr(sys, "frozen", False):
        return None
    exe = os.path.realpath(sys.executable)
    return exe if ".app/Contents/MacOS/" in exe else None


def is_supported() -> bool:
    return app_executable() is not None


def is_enabled() -> bool:
    return os.path.isfile(AGENT_PATH)


def enable() -> None:
    exe = app_executable()
    if exe is None:
        raise RuntimeError("Launch at Login is only available in the packaged macOS app.")
    os.makedirs(os.path.dirname(AGENT_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    agent = {
        "Label": LABEL,
        "ProgramArguments": [exe, "--background"],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "ProcessType": "Interactive",
        "StandardOutPath": LOG_PATH,
        "StandardErrorPath": LOG_PATH,
    }
    with open(AGENT_PATH, "wb") as f:
        plistlib.dump(agent, f)


def disable() -> None:
    try:
        os.remove(AGENT_PATH)
    except FileNotFoundError:
        pass
