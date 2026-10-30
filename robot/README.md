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
2. **The robot's own driver** must run so its topics exist. For car2, `start.sh` and `start_gui.sh` start it automatically (`robot/driver.sh`); for other robots, start it the way the lab does.
3. **If the Mac cannot reach the robot from VS Code** ("No route to host", while the Terminal app can), macOS is blocking VS Code: turn on System Settings > Privacy & Security > Local Network > Visual Studio Code, then quit VS Code with Cmd+Q and reopen it. Until then, run these scripts from the Terminal app.
4. **Check the connection** (read-only, changes nothing on the robot):
   ```bash
   bash robot/check.sh
   ```
   It shows the robot's ROS 2 version, memory, and whether `/cmd_vel` and `/odom` are there and what types they use.
5. **See how the robot's driver is started** (read-only): `bash robot/explore.sh`
6. **Start typing commands:**
   ```bash
   bash robot/start.sh
   ```
   It starts the language model on the Mac so the robot can reach it, copies the code, and opens the chat on the robot. An empty line stops the robot at once; `quit` stops the nodes and sends zero speed.

## The web page for a real robot

`bash robot/start_gui.sh` does everything `start.sh` does, then starts `robot_bridge_node.py` on the robot instead of the terminal chat, and opens the same web page as the simulation (`robot_gui.py`, which needs the `sim_mujoco` folder and its Python). Type or speak commands there. The page shows the robot's position and path from `/odom`, its speed against the commanded speed, and for each command what the model understood, the target, what was achieved and whether it worked. There is no camera view.

The Mac only sends to the robot (UDP port 9871); the robot answers. If the page stops sending for 1.5 s while the robot is moving, the bridge on the robot sends a stop.

## Settings

Put them in front of `start.sh`, for example `MAX_SPEED=0.2 bash robot/start.sh`.

| Setting | Default | Meaning |
|---|---|---|
| `MAX_SPEED` | 0.3 | Driving speed in m/s. Start low and agree the value with the lab. |
| `TURN_RADIUS` | 1.0 | Car turns drive on a circle of this radius in metres. Must not be below the car's minimum. |
| `VEHICLE` | car | `car` turns while driving forward; `legged` turns on the spot (Go2). |
| `DRIVE_TOPIC` | /drive | F1TENTH cars listen for speed and steering here. Set `none` for robots driven by Twist on `/cmd_vel` (e.g. the Go2). |
| `WHEELBASE` | 0.25 | Distance between front and rear axles in metres, for converting turns to steering angles. |
| `MAX_STEERING` | 0.28 | Steering limit in radians (car2's servo allows about 0.29). A sharper turn becomes a wider curve. |
| `CMD_VEL_TOPIC` | /cmd_vel | Where speed commands go, if the robot uses another name. |
| `ODOM_TOPIC` | /odom | Where the robot reports its position, e.g. `/odom_combined`. |

## F1TENTH cars (car2)

The race car runs the F1TENTH software (`f1tenth_stack`, VESC motor controller, `ackermann_mux`). It is steered with `AckermannDriveStamped` messages (speed and steering angle) on `/drive`, not with Twist on `/cmd_vel`. `twist_to_ackermann_node.py` converts between them: steering angle = atan(wheelbase x turning rate / speed), limited to `MAX_STEERING`. It only sends while fresh commands arrive, so if `cmd_vel_node.py` stops for any reason the car is sent zero speed.

The car's ROS 2 channel is set in its `~/.bashrc` (`ROS_DOMAIN_ID=2`, CycloneDDS). ssh commands do not read that file, so the scripts load these two lines from it; otherwise our nodes and the car's driver would not see each other.

## First test with car2, step by step

What car2 actually does (read from its software on 30 October 2026):

- **Driver:** `f1tenth_stack`'s `bringup_launch.py`. Its VESC settings name `/dev/ttyACM1`, but the motor controller is at `/dev/ttyACM0`, so `robot/driver.sh start` runs it with a corrected copy (`~/vesc_llm.yaml`). The lab's files are not changed.
- **Position reports (`/odom`)** only start after the first steering command. `run_on_robot.sh` sends a one-second zero-speed command to wake them up; the car does not move.
- **The lab's own joystick program (`teleop_joy`)** decides who drives when a controller is connected: holding **button 4** passes our `/drive` commands through ("autonomous mode"); releasing it gives control back to the sticks (centred = stop). Its kill switch (button 3) runs `pkill '/opt/ros/foxy'`, which matches nothing on this Humble car, so **it does not work**.
- **With no controller connected, nothing overrides `/drive`:** our commands reach the motors without any button held. The only stops are then ours (STOP on the page, empty line in the chat, closing the page) and `robot/driver.sh stop`. Ask the mentor which controller pairs with `controller_receiver` (port 5005) so button 4 can be used as a dead-man switch.

Steps, with the mentor present:

1. **Wheels off the ground first.** Put the car on a box so the wheels spin freely.
2. **Start everything with one command:** `bash robot/start_gui.sh` (speed 0.3 m/s by default). It starts the language model on the Mac, the car's driver, and our nodes on the car, then opens the page. The header should show "car2 connected". Prefer the terminal chat? `bash robot/start.sh`.
3. **If a controller is connected, hold button 4**, then type (or speak) `Drive forward half a metre.` The wheels should spin forward and stop. Try `Turn left 45 degrees.` (wheels steer left and spin), then STOP.
4. **Only then on the floor**, in a clear area of at least 3 x 3 m.
5. **To stop the car at any time:** press STOP on the page, let go of button 4 (if a controller is used), or close the page (the car stops within 1.5 s).
6. **To shut everything down:** press **Shut down** on the page, or Ctrl+C in the terminal. In that order it stops the car and our nodes, then the car's driver, then the language model. A driver that was already running before you started is left running.

Run all robot scripts from the **Terminal app** unless VS Code has the macOS Local Network permission.

## Safety behaviour

Checked on 30 October 2026 with a stand-in robot in Docker:

| Situation | What happens |
|---|---|
| Robot's driver not running (no `/odom`, or nothing listening on `/cmd_vel`) | `run_on_robot.sh` starts nothing and says why |
| Empty line or "stop" in the chat | Stop sent directly, without the language model |
| Command over 5 m or 180 degrees, unreadable, or not a finite number, even if published by another program | Refused by `cmd_vel_node.py`, zero speed sent |
| Speed setting above 1.5 m/s or 2.0 rad/s, or not positive, at start or while running | Rejected |
| Web page closed or Mac disconnected mid-drive | `robot_bridge_node.py` sends a stop after 1.5 s of silence |
| `cmd_vel_node.py` dies without warning (F1TENTH) | The converter notices the missing commands and sends zero speed |
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
