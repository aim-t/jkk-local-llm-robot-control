#!/bin/bash
# Runs ON the robot (copied there by start.sh). Starts the movement node, the converter for
# F1TENTH cars if DRIVE_TOPIC is set, and the language node; then the chat. Stops them all
# when the chat ends.
cd "$(dirname "$0")"
for f in /opt/ros/*/setup.bash ~/ros2_ws/install/setup.bash ~/*_ws/install/setup.bash; do [ -f "$f" ] && source "$f"; done
# The robot's ROS 2 "channel" (domain ID and middleware) is set in its ~/.bashrc, which ssh
# commands do not read. Without the same values, our nodes and the robot's driver never see
# each other.
eval "$(grep -E '^[[:space:]]*export[[:space:]]+(ROS_DOMAIN_ID|RMW_IMPLEMENTATION|CYCLONEDDS_URI)=' ~/.bashrc 2>/dev/null)"
ros2 daemon stop < /dev/null >/dev/null 2>&1  # the ros2 command's helper may remember old settings; it restarts by itself

: "${OLLAMA_URL:?OLLAMA_URL must point at the Mac running ollama}"
: "${MAX_SPEED:=0.3}" "${TURN_RADIUS:=1.0}" "${VEHICLE:=car}" "${CMD_VEL_TOPIC:=/cmd_vel}" "${ODOM_TOPIC:=/odom}"
: "${DRIVE_TOPIC:=}" "${WHEELBASE:=0.25}" "${MAX_STEERING:=0.28}"
# With DRIVE_TOPIC set, the robot listens there (F1TENTH: /drive) and the converter feeds it.
LISTEN_TOPIC="${DRIVE_TOPIC:-$CMD_VEL_TOPIC}"

cleanup() {
    python3 send.py stop >/dev/null 2>&1   # stop the robot before anything else
    kill $MOVE_PID $LANG_PID $CONVERT_PID 2>/dev/null
    wait 2>/dev/null
    echo "Nodes stopped."
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM   # a dropped ssh connection still runs cleanup and stops the robot

echo "ROS 2 channel: ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0}, ${RMW_IMPLEMENTATION:-default middleware}"
# Before anything can move: the robot must report its position, and something must listen.
if [ -n "$DRIVE_TOPIC" ] && ! timeout --foreground 5 ros2 topic echo --once "$ODOM_TOPIC" < /dev/null >/dev/null 2>&1; then
    # F1TENTH: vesc_to_odom only starts publishing after its first steering command. A zero-speed,
    # straight-ahead command wakes it up without moving the car. Right after the driver starts,
    # it may take a few tries; the ros2 command itself also needs a few seconds to start.
    echo "Waking up the position reports with a zero-speed command..."
    : > /tmp/llm_wakeup.log
    for attempt in 1 2 3; do
        # --foreground and < /dev/null: when started from the web page this runs in a terminal
        # session, where a command moved to the background can be paused before it sends anything.
        timeout --foreground 10 ros2 topic pub -r 10 -t 20 "$DRIVE_TOPIC" ackermann_msgs/msg/AckermannDriveStamped \
            "{drive: {speed: 0.0, steering_angle: 0.0}}" < /dev/null >> /tmp/llm_wakeup.log 2>&1
        timeout --foreground 5 ros2 topic echo --once "$ODOM_TOPIC" < /dev/null >/dev/null 2>&1 && break
        echo "  not yet (try $attempt of 3)"
    done
fi
if ! timeout --foreground 5 ros2 topic echo --once "$ODOM_TOPIC" < /dev/null >/dev/null 2>&1; then
    echo "No position reports on $ODOM_TOPIC. Start the robot's driver first (or set ODOM_TOPIC). Nothing was started."
    exit 1
fi
LISTENERS=$(timeout --foreground 5 ros2 topic info "$LISTEN_TOPIC" < /dev/null 2>/dev/null | awk '/Subscription count/{print $3}')
if [ "${LISTENERS:-0}" -eq 0 ]; then
    echo "Nothing listens on $LISTEN_TOPIC, so the robot would not move. Start its driver first. Nothing was started."
    exit 1
fi

if [ -n "$DRIVE_TOPIC" ]; then
    python3 twist_to_ackermann_node.py --ros-args -r /cmd_vel:=$CMD_VEL_TOPIC -p drive_topic:=$DRIVE_TOPIC \
        -p wheelbase:=$WHEELBASE -p max_steering_angle:=$MAX_STEERING > /tmp/llm_convert.log 2>&1 &
    CONVERT_PID=$!
fi
python3 cmd_vel_node.py --ros-args -p vehicle_type:=$VEHICLE -p max_linear_speed:=$MAX_SPEED \
    -p turn_radius:=$TURN_RADIUS -r /cmd_vel:=$CMD_VEL_TOPIC -r /odom:=$ODOM_TOPIC > /tmp/llm_cmd_vel.log 2>&1 &
MOVE_PID=$!
OLLAMA_URL=$OLLAMA_URL python3 go2_command_node.py > /tmp/llm_language.log 2>&1 &
LANG_PID=$!

echo "Waiting for the language model to load..."
for _ in $(seq 1 60); do
    grep -q "Waiting on /voice_command" /tmp/llm_language.log && break
    if ! kill -0 $LANG_PID 2>/dev/null; then echo "Language node failed:"; cat /tmp/llm_language.log; exit 1; fi
    sleep 1
done
for pid in $MOVE_PID $CONVERT_PID; do
    kill -0 $pid 2>/dev/null || { echo "A node failed to start:"; cat /tmp/llm_cmd_vel.log /tmp/llm_convert.log 2>/dev/null; exit 1; }
done
echo "Speed $MAX_SPEED m/s, turn radius $TURN_RADIUS m, sending to $LISTEN_TOPIC, position from $ODOM_TOPIC."
echo "Logs on the robot: /tmp/llm_cmd_vel.log, /tmp/llm_language.log, /tmp/llm_convert.log"
if [ "${GUI:-0}" = 1 ]; then
    python3 robot_bridge_node.py   # talks to the web page on the Mac; runs until the connection closes
else
    python3 chat.py
fi
