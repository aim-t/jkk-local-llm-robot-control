#!/bin/bash
# Run while the robot's driver is running, to see why something is missing. Read-only.
#     bash robot/diagnose.sh
source "$(dirname "$0")/env.sh"

robot_ssh 'bash -s' <<'REMOTE'
for f in /opt/ros/*/setup.bash ~/ros2_ws/install/setup.bash; do [ -f "$f" ] && source "$f"; done
eval "$(grep -E '^[[:space:]]*export[[:space:]]+(ROS_DOMAIN_ID|RMW_IMPLEMENTATION|CYCLONEDDS_URI)=' ~/.bashrc 2>/dev/null)"
section() { echo; echo "=== $1 ==="; }

section "ROS 2 channel"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}  RMW=${RMW_IMPLEMENTATION:-default}"

section "running nodes"
timeout 10 ros2 node list 2>/dev/null || echo "(none found)"

section "topics"
timeout 10 ros2 topic list -t 2>/dev/null || echo "(none found)"

section "messages actually arriving (3 s each)"
for t in /odom /sensors/core /drive /teleop /ackermann_cmd /joy; do
    echo -n "$t: "
    timeout 4 ros2 topic hz "$t" 2>/dev/null | grep -m1 "average rate" || echo "nothing"
done

section "motor controller (VESC) connection"
ls -l /dev/ttyACM* 2>/dev/null
ls -l /dev/serial/by-id/ 2>/dev/null | tail -n +2
echo "port in the driver's settings: $(grep -h 'port:' ~/ros2_ws/src/f1tenth_system/f1tenth_stack/config/vesc.yaml 2>/dev/null | head -1)"
echo "this user's groups: $(id -nG)   (needs 'dialout' to open serial ports)"

section "driver programs running"
ps -eo pid,etime,cmd | grep -E 'vesc|ackermann|joy|urg|mux|odom|throttle' | grep -v grep || echo "(none)"
REMOTE
