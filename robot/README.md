# Connecting to a real robot

Scripts that copy the project's code to a robot and let you type commands to it. First used with the lab's race car (`car2`); the Go2 will follow.

## Credentials

The robot's details live in `.env.local` in the project folder, which git ignores:

```
robot_name=car2
robot_ip=192.168.123.95
robot_user=<login name on the robot>
robot_password=<password>
```

The scripts read this file on the Mac only. The password is handed straight to `ssh` by `askpass.sh` and is never printed, saved elsewhere, or copied to the robot.

## How it fits together

```
Mac                                          Robot
ollama serve (language model)  <-- network --  go2_command_node.py  (text -> checked command)
                                               cmd_vel_node.py      (command -> /cmd_vel, watches /odom)
ssh: you type here  ------------------------>  chat.py
```

The language model stays on the Mac; the two ROS 2 nodes and the chat run on the robot, next to its driver. Only six Python files and one script are copied, to `~/llm_commands` on the robot. Nothing is installed there.

## Steps

1. **Join the robot's network** on the Mac (its Wi-Fi or a cable), so the Mac can reach `robot_ip`.
2. **Start the robot's own driver** the way the lab does, so `/cmd_vel` and `/odom` exist.
3. **Check the connection** (read-only, changes nothing on the robot):
   ```bash
   bash robot/check.sh
   ```
   It shows the robot's ROS 2 version, memory, and whether `/cmd_vel` and `/odom` are there and what types they use.
4. **Start typing commands:**
   ```bash
   bash robot/start.sh
   ```
   It starts the language model on the Mac so the robot can reach it, copies the code, and opens the chat on the robot. An empty line stops the robot at once; `quit` stops the nodes and sends zero speed.

## Settings

Put them in front of `start.sh`, for example `MAX_SPEED=0.2 bash robot/start.sh`.

| Setting | Default | Meaning |
|---|---|---|
| `MAX_SPEED` | 0.3 | Driving speed in m/s. Start low and agree the value with the lab. |
| `TURN_RADIUS` | 1.0 | Car turns drive on a circle of this radius in metres. Must not be below the car's minimum. |
| `VEHICLE` | car | `car` turns while driving forward; `legged` turns on the spot (Go2). |
| `CMD_VEL_TOPIC` | /cmd_vel | Where speed commands go, if the robot uses another name. |
| `ODOM_TOPIC` | /odom | Where the robot reports its position, e.g. `/odom_combined`. |

## Safety behaviour

Checked on 30 October 2026 with a stand-in robot in Docker:

| Situation | What happens |
|---|---|
| Robot's driver not running (no `/odom`, or nothing listening on `/cmd_vel`) | `run_on_robot.sh` starts nothing and says why |
| Empty line or "stop" in the chat | Stop sent directly, without the language model |
| Command over 5 m or 180 degrees, unreadable, or not a finite number, even if published by another program | Refused by `cmd_vel_node.py`, zero speed sent |
| Speed setting above 1.5 m/s or 2.0 rad/s, or not positive, at start or while running | Rejected |
| ssh connection drops (e.g. Wi-Fi lost) while driving | `cmd_vel_node.py` sends zero speed and exits |
| Chat ended with `quit`, or the script is stopped | Stop sent, then both nodes stopped, zero speed on shutdown |
| `/odom` stops arriving during a movement | Zero speed |
| Model unreachable or slower than 10 s | Command refused; an answer that took over 5 s is not acted on |
| Unsafe values in `start.sh` settings | Refused before connecting |

None of this replaces the lab's own emergency stop. Someone must be ready to stop the car by its own means during every test.

## Limits

- The robot side was tested in a Docker container acting as the robot, not on the car.
- A car turn of 90 degrees drives a quarter circle: about `TURN_RADIUS` metres forward and to the side. It needs that much free space.
- If the car's driver expects Ackermann messages on another topic (`/drive`) instead of Twist on `/cmd_vel`, a converter is needed; `check.sh` shows which.
- `OLLAMA_HOST=0.0.0.0` lets any device on the robot's network use the language model on the Mac while `start.sh` runs.
