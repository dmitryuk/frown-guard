import os
import shutil
import sys

APP_NAME = "Frown Guard"


def config_dir() -> str:
    """Returns a per-user, writable directory for settings (created on demand)."""
    if sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_NAME)
    elif sys.platform.startswith("win"):
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        base = os.path.join(xdg, "frown-guard")
    os.makedirs(base, exist_ok=True)
    return base


def config_file() -> str:
    """
    Absolute path of config.json. The original app used a path relative to the
    working directory, which is "/" (read-only) when launched from Finder, so
    calibration was never saved. A legacy ./config.json is migrated once.
    """
    path = os.path.join(config_dir(), "config.json")
    legacy = os.path.abspath("config.json")
    if not os.path.exists(path) and os.path.isfile(legacy):
        try:
            shutil.copyfile(legacy, path)
        except OSError:
            pass
    return path
