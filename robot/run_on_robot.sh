#!/bin/bash
# Runs ON the robot (copied there by start.sh). Starts the movement node and the language node,
# then the chat, and stops both nodes when the chat ends.
cd "$(dirname "$0")"
for f in /opt/ros/*/setup.bash ~/ros2_ws/install/setup.bash ~/*_ws/install/setup.bash; do [ -f "$f" ] && source "$f"; done
: "${OLLAMA_URL:?OLLAMA_URL must point at the Mac running ollama}"
: "${MAX_SPEED:=0.3}" "${TURN_RADIUS:=1.0}" "${VEHICLE:=car}" "${CMD_VEL_TOPIC:=/cmd_vel}" "${ODOM_TOPIC:=/odom}"

cleanup() {
    python3 send.py stop >/dev/null 2>&1   # stop the car before anything else
    kill $MOVE_PID $LANG_PID 2>/dev/null
    wait 2>/dev/null
    echo "Nodes stopped."
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM   # a dropped ssh connection still runs cleanup and stops the robot

# Before anything can move: the robot must report its position, and something must listen for speeds.
if ! timeout 5 ros2 topic echo --once "$ODOM_TOPIC" >/dev/null 2>&1; then
    echo "No position reports on $ODOM_TOPIC. Start the robot's driver first (or set ODOM_TOPIC). Nothing was started."
    exit 1
fi
LISTENERS=$(timeout 5 ros2 topic info "$CMD_VEL_TOPIC" 2>/dev/null | awk '/Subscription count/{print $3}')
if [ "${LISTENERS:-0}" -eq 0 ]; then
    echo "Nothing listens on $CMD_VEL_TOPIC, so the robot would not move. Start its driver first (or set CMD_VEL_TOPIC)."
    exit 1
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
echo "Speed $MAX_SPEED m/s, turn radius $TURN_RADIUS m, driving on $CMD_VEL_TOPIC, position from $ODOM_TOPIC."
echo "Logs on the robot: /tmp/llm_cmd_vel.log and /tmp/llm_language.log"
python3 chat.py
