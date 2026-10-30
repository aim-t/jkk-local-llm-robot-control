#!/bin/bash
# Step 1: check the connection and look at the robot, without changing anything on it.
#     bash robot/check.sh
source "$(dirname "$0")/env.sh"

echo "Robot: $ROBOT_NAME at $ROBOT_IP, login $ROBOT_USER"
if ! ping -c 2 -t 4 "$ROBOT_IP" >/dev/null 2>&1; then
    echo "NOT REACHABLE. Join the robot's network first (Wi-Fi or cable)."
    echo "This Mac's addresses: $(ifconfig | awk '/inet /{print $2}' | grep -v 127.0.0.1 | tr '\n' ' ')"
    exit 1
fi
echo "Reachable. Logging in to look around (read-only)..."
robot_ssh 'bash -s' <<'REMOTE'
for f in /opt/ros/*/setup.bash ~/ros2_ws/install/setup.bash ~/*_ws/install/setup.bash; do [ -f "$f" ] && source "$f"; done
# ssh commands do not read ~/.bashrc, where the robot's ROS 2 channel is set.
eval "$(grep -E '^[[:space:]]*export[[:space:]]+(ROS_DOMAIN_ID|RMW_IMPLEMENTATION|CYCLONEDDS_URI)=' ~/.bashrc 2>/dev/null)"
echo "hostname:      $(hostname)"
echo "system:        $(. /etc/os-release; echo "$PRETTY_NAME") on $(uname -m)"
echo "ROS 2:         ${ROS_DISTRO:-not found} (ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-unset}, RMW=${RMW_IMPLEMENTATION:-default})"
echo "python:        $(python3 --version 2>&1)"
echo "memory:        $(free -h | awk '/Mem:/{print $2 " total, " $7 " available"}')"
echo "rclpy:         $(python3 -c 'import rclpy; print("ok")' 2>&1 | tail -1)"
command -v ros2 >/dev/null || { echo "ros2 command not found"; exit 0; }
echo "--- topics ---"
timeout 10 ros2 topic list -t 2>/dev/null | grep -iE "cmd_vel|odom|drive|ackermann|scan|imu" || echo "(none of the driving topics are visible: is the car's driver started?)"
for t in /cmd_vel /drive /odom /odom_combined; do
  if timeout 10 ros2 topic list 2>/dev/null | grep -qx "$t"; then
    echo "--- $t ---"; timeout 10 ros2 topic info "$t" 2>/dev/null
    case "$t" in /cmd_vel|/drive) ;; *) false ;; esac || { echo -n "rate: "; timeout 6 ros2 topic hz "$t" 2>/dev/null | grep -m1 "average rate" || echo "no messages"; }
  fi
done
REMOTE
