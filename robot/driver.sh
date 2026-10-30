#!/bin/bash
# Start, stop or check the robot's own driver from the Mac, without opening a terminal on it.
#     bash robot/driver.sh start | stop | status | log
# For car2 (F1TENTH): starts f1tenth_stack's bringup with a copy of its VESC settings in which
# the serial port is /dev/ttyACM0 (the lab's file names /dev/ttyACM1, which does not exist).
# The lab's own files are not changed. Starting the driver does not move the car.
source "$(dirname "$0")/env.sh"
ACTION="${1:-status}"

robot_ssh "ACTION=$ACTION bash -s" <<'REMOTE'
for f in /opt/ros/*/setup.bash ~/ros2_ws/install/setup.bash; do [ -f "$f" ] && source "$f"; done
eval "$(grep -E '^[[:space:]]*export[[:space:]]+(ROS_DOMAIN_ID|RMW_IMPLEMENTATION|CYCLONEDDS_URI)=' ~/.bashrc 2>/dev/null)"
mkdir -p ~/llm_commands
PIDFILE=~/llm_commands/bringup.pid LOG=~/llm_commands/bringup.log
running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "$ACTION" in
start)
    if running || pgrep -f "bringup_launch.py" >/dev/null; then echo "The driver is already running."; exit 0; fi
    ORIG=~/ros2_ws/install/f1tenth_stack/share/f1tenth_stack/config/vesc.yaml
    PORT=$(ls /dev/serial/by-id/*ChibiOS* 2>/dev/null | head -1 | xargs -r readlink -f)
    [ -n "$PORT" ] || { echo "Motor controller (VESC) not found on USB. Is the car's battery on?"; exit 1; }
    sed -E "s#^([[:space:]]*port:).*#\1 $PORT#" "$ORIG" > ~/vesc_llm.yaml
    setsid nohup ros2 launch f1tenth_stack bringup_launch.py vesc_config:=$HOME/vesc_llm.yaml > "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    echo "Driver starting (motor controller on $PORT)..."
    for _ in $(seq 1 15); do grep -q "Connected to VESC" "$LOG" && break; grep -q "FATAL" "$LOG" && break; sleep 1; done
    grep -E "Connected to VESC|FATAL" "$LOG" | sed -E 's/\[[0-9]{10}\.[0-9]+\] //' | head -3
    grep -q "Connected to VESC" "$LOG" || { echo "The motor controller did not connect; see: bash robot/driver.sh log"; exit 1; }
    ;;
stop)
    if running; then
        kill -INT -- -"$(cat "$PIDFILE")" 2>/dev/null || kill -INT "$(cat "$PIDFILE")"
        sleep 3; pkill -f "bringup_launch.py" 2>/dev/null; rm -f "$PIDFILE"; echo "Driver stopped."
    elif pgrep -f "bringup_launch.py" >/dev/null; then
        echo "A driver is running that was not started by this script; stop it where it was started."
    else
        echo "The driver is not running."
    fi
    ;;
status)
    if running; then echo "Driver running (started by this script)."
    elif pgrep -f "bringup_launch.py" >/dev/null; then echo "Driver running (started elsewhere)."
    else echo "Driver not running."; fi
    for t in /sensors/core /odom; do echo -n "  $t: "; timeout 4 ros2 topic hz "$t" 2>/dev/null | grep -m1 "average rate" || echo "nothing"; done
    ;;
log) tail -40 "$LOG" 2>/dev/null | sed -E 's/\[[0-9]{10}\.[0-9]+\] //' || echo "No log yet." ;;
*) echo "Use: start, stop, status or log"; exit 1 ;;
esac
REMOTE
