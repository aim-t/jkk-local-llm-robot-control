#!/bin/bash
# Step 2: copy the code to the robot and type commands to it.
#     bash robot/start.sh
# Optional settings:  MAX_SPEED=0.3 TURN_RADIUS=1.0 VEHICLE=car CMD_VEL_TOPIC=/cmd_vel ODOM_TOPIC=/odom
#                     DRIVE_TOPIC=/drive (F1TENTH cars; 'none' to send Twist straight to CMD_VEL_TOPIC)
#                     WHEELBASE=0.25 MAX_STEERING=0.28 (car2's values, from its vesc.yaml)
source "$(dirname "$0")/env.sh"

# Settings end up in a command run on the robot, so allow only plain values within safe limits.
MAX_SPEED="${MAX_SPEED:-0.3}"; TURN_RADIUS="${TURN_RADIUS:-1.0}"; VEHICLE="${VEHICLE:-car}"
CMD_VEL_TOPIC="${CMD_VEL_TOPIC:-/cmd_vel}"; ODOM_TOPIC="${ODOM_TOPIC:-/odom}"
DRIVE_TOPIC="${DRIVE_TOPIC:-/drive}"; [ "$DRIVE_TOPIC" = none ] && DRIVE_TOPIC=""
[ "$VEHICLE" = legged ] && [ "${DRIVE_TOPIC:-}" = /drive ] && DRIVE_TOPIC=""
WHEELBASE="${WHEELBASE:-0.25}"; MAX_STEERING="${MAX_STEERING:-0.28}"
python3 - "$MAX_SPEED" "$TURN_RADIUS" "$VEHICLE" "$CMD_VEL_TOPIC" "$ODOM_TOPIC" "${DRIVE_TOPIC:-/none}" "$WHEELBASE" "$MAX_STEERING" <<'CHECK' || exit 1
import re, sys
speed, radius, vehicle, cmd_vel, odom, drive, wheelbase, steering = sys.argv[1:]
problems = []
try:
    if not 0.1 <= float(wheelbase) <= 1.0: problems.append("WHEELBASE must be between 0.1 and 1.0 (m)")
    if not 0.05 <= float(steering) <= 0.6: problems.append("MAX_STEERING must be between 0.05 and 0.6 (rad)")
except ValueError: problems.append("WHEELBASE and MAX_STEERING must be numbers")
try:
    if not 0 < float(speed) <= 1.5: problems.append("MAX_SPEED must be above 0 and at most 1.5 (m/s)")
except ValueError: problems.append("MAX_SPEED must be a number")
try:
    if not 0.3 <= float(radius) <= 20: problems.append("TURN_RADIUS must be between 0.3 and 20 (m)")
except ValueError: problems.append("TURN_RADIUS must be a number")
if vehicle not in ("car", "legged"): problems.append("VEHICLE must be car or legged")
for name, topic in (("CMD_VEL_TOPIC", cmd_vel), ("ODOM_TOPIC", odom), ("DRIVE_TOPIC", drive)):
    if not re.fullmatch(r"/[A-Za-z0-9_/]+", topic): problems.append(f"{name} must look like /name")
for p in problems: print("Setting not accepted:", p)
sys.exit(1 if problems else 0)
CHECK

ping -c 2 -t 4 "$ROBOT_IP" >/dev/null 2>&1 || { echo "Robot not reachable. Join its network, then run robot/check.sh."; exit 1; }

# The robot reaches the language model on this Mac, through the network interface that leads to it.
IFACE="$(route -n get "$ROBOT_IP" | awk '/interface:/{print $2}')"
MAC_IP="$(ipconfig getifaddr "$IFACE")"
echo "This Mac is $MAC_IP on $IFACE."

if ! curl -s --max-time 2 "http://$MAC_IP:11434/api/version" >/dev/null; then
    if curl -s --max-time 2 http://localhost:11434/api/version >/dev/null; then
        echo "Ollama is running but only for this Mac. Stop it (Ctrl+C in its terminal, or quit the app) and run this again."
        exit 1
    fi
    echo "Starting the language model so the robot can reach it (OLLAMA_HOST=0.0.0.0)..."
    OLLAMA_HOST=0.0.0.0:11434 ollama serve >/tmp/llm_ollama.log 2>&1 &
    OLLAMA_PID=$!
    trap 'kill $OLLAMA_PID 2>/dev/null; echo "Language model stopped."' EXIT
    for _ in $(seq 1 20); do curl -s --max-time 2 "http://$MAC_IP:11434/api/version" >/dev/null && break; sleep 1; done
fi

robot_ssh "curl -s --max-time 4 http://$MAC_IP:11434/api/version >/dev/null" || {
    echo "The robot cannot reach the language model at $MAC_IP:11434. Check the Mac's firewall (allow ollama)."; exit 1; }

echo "Copying the code to ~/$REMOTE_DIR on the robot (code only, never .env.local)..."
robot_ssh "mkdir -p ~/$REMOTE_DIR" || exit 1
robot_scp "$PROJECT/src/run_benchmark.py" "$PROJECT/src/safety.py" "$PROJECT/src/go2_command_node.py" \
          "$PROJECT/src/cmd_vel_node.py" "$PROJECT/src/chat.py" "$PROJECT/src/send.py" "$ROBOT_DIR/run_on_robot.sh" \
          "$ROBOT_DIR/twist_to_ackermann_node.py" \
          "$ROBOT_USER@$ROBOT_IP:$REMOTE_DIR/" || exit 1

echo "Starting on the robot. Type commands; empty line = stop, quit = leave."
robot_ssh_tty "OLLAMA_URL=http://$MAC_IP:11434 MAX_SPEED=$MAX_SPEED TURN_RADIUS=$TURN_RADIUS \
    VEHICLE=$VEHICLE CMD_VEL_TOPIC=$CMD_VEL_TOPIC ODOM_TOPIC=$ODOM_TOPIC \
    DRIVE_TOPIC=$DRIVE_TOPIC WHEELBASE=$WHEELBASE MAX_STEERING=$MAX_STEERING \
    bash ~/$REMOTE_DIR/run_on_robot.sh"
