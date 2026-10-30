#!/bin/bash
# Start everything for the Go2 web console with one command, from anywhere:
#     bash "sim_mujoco/start_gui.sh"
# Then use the page that opens at http://localhost:8765. Press Ctrl+C here to stop everything.
#
# It starts: Docker Desktop (if closed), the language model (ollama serve, if not running),
# the ROS 2 container with the bridge, cmd_vel_node.py and go2_command_node.py, and the
# simulation with its web page. On Ctrl+C it removes the container and stops what it started.

set -u
SIM_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(dirname "$SIM_DIR")"
CONTAINER=go2_sim
OLLAMA_PID=""

cleanup() {
    echo
    echo "Stopping..."
    docker rm -f "$CONTAINER" >/dev/null 2>&1
    if [ -n "$OLLAMA_PID" ]; then
        ollama stop llama3.2:3b >/dev/null 2>&1
        kill "$OLLAMA_PID" 2>/dev/null
    fi
    echo "Done."
}
trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
    echo "Starting Docker Desktop..."
    open -a Docker
    for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
    docker info >/dev/null 2>&1 || { echo "Docker did not start. Open Docker Desktop and try again."; exit 1; }
fi

if ! curl -s --max-time 2 http://localhost:11434/api/version >/dev/null; then
    echo "Starting the language model (ollama serve)..."
    ollama serve >/tmp/go2_ollama.log 2>&1 &
    OLLAMA_PID=$!
    for _ in $(seq 1 20); do curl -s --max-time 2 http://localhost:11434/api/version >/dev/null && break; sleep 1; done
fi

echo "Starting ROS 2 (bridge, cmd_vel_node.py, go2_command_node.py)..."
docker rm -f "$CONTAINER" >/dev/null 2>&1
docker run -d --name "$CONTAINER" -v "$PROJECT":/ws:ro -e PYTHONUNBUFFERED=1 \
    ros:jazzy-ros-base python3 /ws/sim_mujoco/src/ros_bridge_node.py >/dev/null || exit 1
docker exec -d "$CONTAINER" bash -c 'source /opt/ros/jazzy/setup.bash && cd /ws/src && python3 cmd_vel_node.py --ros-args -p max_angular_speed:=1.0 > /tmp/cmd_vel.log 2>&1'
docker exec -d "$CONTAINER" bash -c 'source /opt/ros/jazzy/setup.bash && cd /ws/src && OLLAMA_URL=http://host.docker.internal:11434 python3 go2_command_node.py > /tmp/language.log 2>&1'

[ -z "${NO_BROWSER:-}" ] && (sleep 4; open http://localhost:8765) &
echo "Starting the simulation and the web page..."
"$SIM_DIR/.venv/bin/python" "$SIM_DIR/src/web_gui.py"
