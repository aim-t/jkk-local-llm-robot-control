#!/bin/bash
# Look at what is installed on the robot, to find out how its driver is started. Read-only:
# it lists files and settings, starts nothing and changes nothing.
#     bash robot/explore.sh
source "$(dirname "$0")/env.sh"

robot_ssh 'bash -s' <<'REMOTE'
section() { echo; echo "=== $1 ==="; }
section "board"
tr -d '\0' < /proc/device-tree/model 2>/dev/null; echo
head -1 /etc/nv_tegra_release 2>/dev/null || echo "(no Jetson release file)"
df -h ~ | awk 'NR==2 {print "disk free in home: " $4}'

section "home folder"
ls -1 ~

section "ROS workspaces and their packages"
for ws in ~/*_ws ~/*ws ~/ros*; do
    [ -d "$ws/src" ] || continue
    echo "$ws:"
    find "$ws/src" -maxdepth 4 -name package.xml -printf '  %h\n' 2>/dev/null | sed "s#$ws/src/##" | sort | head -60
done

section "launch files mentioning drive, car, base, bringup, wheeltec, vesc or ackermann"
find ~ -maxdepth 7 -path '*/install' -prune -o -name '*launch.py' -print 2>/dev/null \
  | grep -iE 'drive|car|base|bring|wheeltec|robot|vesc|ackermann|f1|racecar|teleop|start' | head -30

section "ROS lines in .bashrc (shortcuts the lab set up)"
grep -nE 'ros|source|alias|ROS_|RMW|export|function' ~/.bashrc 2>/dev/null | grep -viE 'pass|token|secret|key=' | tail -40

section "helper scripts in home"
find ~ -maxdepth 2 -name '*.sh' 2>/dev/null | head -20

section "services that start on boot"
systemctl list-unit-files --type=service --state=enabled 2>/dev/null | grep -iE 'ros|robot|car|drive|wheel|start|launch|jupyter|docker' || echo "(none related)"

section "ROS-related programs running now"
ps -eo pid,etime,cmd | grep -iE 'ros2|launch|_node|python3' | grep -v grep | head -20 || true

section "serial and USB devices (motor board, lidar)"
ls -l /dev/ttyUSB* /dev/ttyACM* /dev/ttyTHS* 2>/dev/null || echo "(none)"
ls /dev/serial/by-id 2>/dev/null

section "F1TENTH driver: launch files and settings (if present)"
STACK=$(find ~ -maxdepth 6 -type d -name f1tenth_stack -path '*/src/*' 2>/dev/null | head -1)
if [ -n "$STACK" ]; then
    echo "launch files:"; ls -1 "$STACK/launch" 2>/dev/null | sed 's/^/  /'
    for f in "$STACK"/config/*.yaml; do
        [ -f "$f" ] || continue
        case "$(basename "$f")" in *mux*|*joy*|*vesc*|*teleop*)
            echo "--- $(basename "$f") ---"; grep -vE '^[[:space:]]*(#|$)' "$f" | head -60 ;;
        esac
    done
else
    echo "(no f1tenth_stack package found)"
fi

section "docker containers"
docker ps -a --format '{{.Names}}  {{.Image}}  {{.Status}}' 2>/dev/null || echo "(docker not available to this user)"
REMOTE
