#!/usr/bin/env python3
from openpilot.system.ui.lib.application import gui_app
import openpilot.system.ui.tici_updater as tici_updater
import openpilot.system.ui.mici_updater as mici_updater


# @atoms REQ-382 — System UI Applications
# @atoms REQ-397 — Update Entry Point
def main():
  if gui_app.big_ui():
    tici_updater.main()
  else:
    mici_updater.main()


if __name__ == "__main__":
  main()
