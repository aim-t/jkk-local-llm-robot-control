#!/bin/bash
# Drive the robot from the web page on the Mac: type or speak commands in the browser.
#     bash robot/start_gui.sh
# Same settings as start.sh (MAX_SPEED=..., etc.). Press Ctrl+C here to stop everything.
GUI=1 exec bash "$(dirname "$0")/start.sh"
