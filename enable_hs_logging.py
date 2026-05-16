#!/usr/bin/env python3
"""
Creates/updates the Hearthstone log.config file so that Power.log is written.
Run this ONCE before launching Hearthstone.

  python enable_hs_logging.py
"""
import sys
from pathlib import Path

LOG_CONFIG_CONTENT = """\
[LoadingScreen]
LogLevel=1
FilePrinting=True
ConsolePrinting=True

[Power]
LogLevel=1
FilePrinting=True
ConsolePrinting=True
ScreenPrinting=False
Verbose=True

[Zone]
LogLevel=1
FilePrinting=True
ConsolePrinting=True
"""

def get_config_path() -> Path:
    if sys.platform == "win32":
        import os
        return Path(os.environ["LOCALAPPDATA"]) / "Blizzard" / "Hearthstone" / "log.config"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Preferences" / "Blizzard" / "Hearthstone" / "log.config"
    else:
        raise RuntimeError("Unsupported OS")

def main():
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(LOG_CONFIG_CONTENT, encoding="utf-8")
    print(f"✓ log.config written to:\n  {path}")
    print("\nRestart Hearthstone for changes to take effect.")

if __name__ == "__main__":
    main()
