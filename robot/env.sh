# Shared settings for the robot scripts. Sourced, not run.
# Reads the robot's name, address, login and password from ../.env.local (kept out of git).
# The password is never printed or written anywhere: ssh asks askpass.sh for it when needed.

ROBOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(dirname "$ROBOT_DIR")"
ENV_FILE="$PROJECT/.env.local"
[ -f "$ENV_FILE" ] || { echo "Missing $ENV_FILE"; exit 1; }

env_value() {  # env_value name -> the value from .env.local, without quotes
    grep -E "^[[:space:]]*$1[[:space:]]*=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -E 's/^[[:space:]"'\'']+|[[:space:]"'\'']+$//g'
}

ROBOT_NAME="$(env_value robot_name)"
ROBOT_IP="$(env_value robot_ip)"
ROBOT_USER="$(env_value robot_user)"
[ -n "$ROBOT_IP" ] || { echo "Add robot_ip=... to .env.local"; exit 1; }
[ -n "$ROBOT_USER" ] || { echo "Add robot_user=<login name on the robot> to .env.local"; exit 1; }

REMOTE_DIR="llm_commands"   # folder in the robot user's home that receives the code
SSH_OPTS=(-o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new
          -o ControlMaster=auto -o "ControlPath=/tmp/llm-robot-%r@%h" -o ControlPersist=120)
export SSH_ASKPASS="$ROBOT_DIR/askpass.sh" SSH_ASKPASS_REQUIRE=force ENV_FILE

robot_ssh() { ssh "${SSH_OPTS[@]}" "$ROBOT_USER@$ROBOT_IP" "$@"; }
# Sessions that run our nodes get their own connection (no sharing), so closing them really hangs
# (ssh uses the first value of a repeated -o option, so these must come before SSH_OPTS)
# up and the robot side stops its nodes.
OWN_CONNECTION=(-o ControlMaster=no -o ControlPath=none)
robot_ssh_tty() { ssh -t "${OWN_CONNECTION[@]}" "${SSH_OPTS[@]}" "$ROBOT_USER@$ROBOT_IP" "$@"; }  # for interactive use
robot_scp() { scp "${SSH_OPTS[@]}" "$@"; }
