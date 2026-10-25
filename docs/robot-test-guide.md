# Robot test guide

A step-by-step guide for the first test of the language pipeline on the Unitree Go2, and a record of how the project was built up to this point.

The robot's setup is documented in the lab's repository, [JKK_UNITREE_GO2](https://github.com/jkk-research/JKK_UNITREE_GO2). Facts below marked **(lab repo)** come from its README as of 26 October 2026.

Things marked **(confirm)** are not known yet and must be checked with the mentor or the lab's robot documentation before or at the start of the test.

## 1. How the system works

```
You type or say:  "Walk forward one metre."
        |
        v
/voice_command            (ROS 2 topic, plain text)
        |
go2_command_node.py       asks the language model (Llama 3.2 3B, served by Ollama)
        |                 and runs the safety check (src/safety.py)
        v
/go2/command              approved command, e.g. {"action": "move", "distance_m": 1.0, ...}
        |                 refused commands go to /go2/command_blocked instead
cmd_vel_node.py           turns it into speeds and watches /odom to know when to stop
        |
        v
/cmd_vel                  geometry_msgs/Twist: forward speed and turning speed
        |
        v
The robot walks. It reports its position on /odom.
```

Sit, stand up and lie down cannot travel on `/cmd_vel`. They need the Unitree Python API, or possibly the `/mode` service of the `go2_robot` driver in the lab repo (which documents modes such as `sit`, `stand_up`, `stand_down`, `stop_move` and `damp`). Neither is connected yet, so in this test those commands do nothing.

## 2. What has been done so far, and how

### 2.1 Running a language model on the Mac

| Step | Command | What it did |
|---|---|---|
| Install Ollama | `brew install ollama` | The program that loads a model and answers requests on `localhost:11434` |
| Start it | `ollama serve` | Keeps running in its own terminal |
| Download the model | `ollama pull llama3.2:3b` | About 2 GB, stored in `~/.ollama` |
| Project Python | `uv venv --python 3.12` | A private Python in `.venv`, leaving the system Python untouched |

### 2.2 Measuring the model

- `src/run_benchmark.py` sends each test command to the model, forces the reply into a fixed JSON shape, and records accuracy, time, speed and memory in `results/`.
- Test commands live in `data/`: 40 for adjusting the prompt (`go2_commands_dev.jsonl`) and 60 kept unseen for fair scores (`go2_commands_test.jsonl`).
- Result: Llama 3.2 3B got 57 of 60 held-out commands right, in about 0.65 s each, using 2.55 GB of memory. Three other models were compared and did not do better.

Run it with:

```bash
.venv/bin/python src/run_benchmark.py --data data/go2_commands_test.jsonl
```

### 2.3 The safety check

`src/safety.py` inspects every answer before it can reach the robot. It refuses moves over 5 m, turns over 180 degrees, unknown actions and confused answers. Run it on a saved result to see what it would block:

```bash
.venv/bin/python src/safety.py results/20261012-004724_llama3.2-3b.json
```

### 2.4 ROS 2 on the Mac

ROS 2 is built for Linux, so on the Mac it runs inside Docker:

```bash
docker pull ros:jazzy-ros-base
```

The project folder is shared into the container read-only, and the container reaches Ollama on the Mac at `host.docker.internal:11434`.

### 2.5 The ROS 2 nodes

| File | Job |
|---|---|
| `src/go2_command_node.py` | Text in on `/voice_command`, checked command out on `/go2/command` |
| `src/cmd_vel_node.py` | Command in, speeds out on `/cmd_vel` until `/odom` shows the target is reached |
| `src/fake_go2_node.py` | Stand-in robot for testing: turns `/cmd_vel` into `/odom` |
| `src/send.py` | Sends one command from a terminal: `text`, `move`, `turn` or `stop` |

`cmd_vel_node.py` settings:

| Parameter | Default | Meaning |
|---|---|---|
| `max_linear_speed` | 0.6 | Walking speed in m/s (the lab's suggested start) |
| `max_angular_speed` | 0.5 | Turning speed in rad/s (about 29 degrees per second) |
| `use_odom` | true | Stop based on measured position; `false` uses timing instead |

Without `/odom` the node refuses to move. If `/odom` stops during a movement, it stops the robot.

### 2.6 Tests so far (no robot)

- Full chain in ROS 2 Humble and Jazzy containers: text commands became the right speeds; over-limit and impossible commands were blocked.
- Against the stand-in robot: a 1.0 m move measured 1.04 m, a 90 degree turn 93 degrees, and stop interrupted a move. These numbers show the code works, not how the real robot behaves.

## 3. Before the test day

Agree these with the mentor in advance, ideally in writing:

1. **Where the code runs.** Recommended for the first test: the ROS 2 nodes run on the robot's Jetson, and the model stays on your Mac, reached over the network. This needs only four Python files copied to the Jetson and nothing installed, but copying them still needs the mentor's agreement.
2. **ROS 2 version on the robot** (confirm): the lab repo lists ROS 2 Humble, installed directly with workspaces in `/home/unitree` that load automatically from `~/.bashrc`. The mentor said the dog uses Jazzy. The code works on both, but ask which is current.
3. **Network** (lab repo): the robot's computer is at `192.168.123.18`, reached over a cable to the robot's back port, with your computer set to a fixed address such as `192.168.123.200`. The login is in the lab repo README. ROS 2 there uses CycloneDDS with no `ROS_DOMAIN_ID`.
4. **Which driver turns `/cmd_vel` into leg movement** (confirm). The lab repo includes two candidates: `go2_ros2_sdk` and `go2_robot`. Ask which one is started for tests, and what mode the robot must be in to obey it.
5. **Emergency stop procedure** (confirm). There is no physical button. Agree exactly who stops the robot through the Unitree API or app, and how, before anything moves.
6. **The test space**: a clear, flat area of at least 3 x 3 m, with no people in the robot's path.

Why not run everything on the Mac? ROS 2 inside Docker on a Mac usually cannot find ROS 2 programs on other machines, because Docker on a Mac runs inside a hidden virtual machine. This is a known limitation, not tested here, and running the nodes on the Jetson avoids it.

### What to bring

- The Mac, charged, with this project and the model already downloaded.
- A tape measure (to compare real distance with `/odom`).
- A phone for video, if the lab allows it.
- A printed or open copy of the record sheet in section 6.

## 4. On the day, step by step

### Step 1. Safety briefing (before anything else)

- Agree who holds the emergency stop and practise it once with the robot standing still.
- Agree a spoken word, such as "stop", that anyone can call. Whoever holds the stop acts on it immediately.
- Keep everyone out of the robot's path.

### Step 2. Connect the Mac to the robot's network

Connect a network cable from the Mac (through a USB-C to Ethernet adapter if needed) to the robot's back port. Then give the Mac a fixed address on the robot's network:

1. Open System Settings, Network, and select the Ethernet adapter.
2. Details, TCP/IP, set "Configure IPv4" to Manually.
3. IP address `192.168.123.200`, subnet mask `255.255.255.0`. Leave the router empty.

`<mac-ip>` is then `192.168.123.200`, and `<jetson-ip>` is `192.168.123.18` (lab repo). Check you can reach the robot's computer:

```bash
ping 192.168.123.18
```

Press Ctrl+C to stop the ping.

### Step 3. Start the model on the Mac, open to the network

By default Ollama only answers requests from the Mac itself. This makes it answer the robot too:

```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Leave this terminal open. If macOS asks whether to allow incoming connections, choose Allow. Keep the Mac awake and plugged in.

### Step 4. Copy the code to the Jetson (with the mentor's agreement)

From the project folder on the Mac:

```bash
scp src/run_benchmark.py src/safety.py src/go2_command_node.py src/cmd_vel_node.py src/send.py unitree@192.168.123.18:~/go2_llm/
```

Create the `~/go2_llm` folder on the Jetson first if it does not exist (`mkdir -p ~/go2_llm`). The files need only Python and ROS 2, which the robot already has.

### Step 5. Check the robot's topics (on the Jetson)

Log in. According to the lab repo, ROS 2 and CycloneDDS load automatically when you log in, so no `source` line should be needed (confirm):

```bash
ssh unitree@192.168.123.18
cd ~/go2_llm
```

Check the model is reachable from the robot:

```bash
curl http://<mac-ip>:11434/api/version
```

Check the robot's topics exist and `/odom` is live:

```bash
ros2 topic list | grep -E "cmd_vel|odom"
ros2 topic echo --once /odom
```

If `/odom` prints a position, continue. If not, stop here and ask the mentor.

### Step 6. Dry run: the robot does not move

Each node runs in its own terminal on the Jetson (repeat the `ssh` and `cd` lines in each).

Terminal A, the language node, pointed at the Mac:

```bash
OLLAMA_URL=http://<mac-ip>:11434 python3 go2_command_node.py
```

Terminal B, the movement node, with its output redirected to a test topic the robot ignores:

```bash
python3 cmd_vel_node.py --ros-args -r /cmd_vel:=/cmd_vel_dry_run
```

Terminal C, watch what would be sent:

```bash
ros2 topic echo /cmd_vel_dry_run
```

Terminal D, send commands:

```bash
python3 send.py text "Walk forward one metre."
python3 send.py text "Make me a cup of coffee."
python3 send.py stop
```

Expected: Terminal A shows APPROVED for the first and BLOCKED for the second, and Terminal C shows `linear: x: 0.6` messages. The robot does not move, so `/odom` never shows the target reached, and the time limit ends the movement after a few seconds.

Stop Terminal B with Ctrl+C before the next step.

### Step 7. First real movement, without the language model

The robot must be standing and in the mode that obeys `/cmd_vel` (the mentor sets this up). Everyone in position, emergency stop ready.

Terminal B, now publishing to the real `/cmd_vel`. For the very first move you may want a lower speed; agree this with the mentor:

```bash
python3 cmd_vel_node.py --ros-args -p max_linear_speed:=0.6
```

Terminal D, a short move first:

```bash
python3 send.py move 0.3
```

Measure the real distance with the tape and write it down with what `/odom` reported (Terminal B prints "measured ... m"). Then try:

```bash
python3 send.py turn 90
python3 send.py move 1.0
python3 send.py move -0.5
```

Test stop during a longer move:

```bash
python3 send.py move 2.0
python3 send.py stop
```

Run the stop line a second after the move starts. `stop` also sends zero speed straight on `/cmd_vel`, but it does not replace the Unitree emergency stop.

### Step 8. With the language model

With Terminal A still running:

```bash
python3 send.py text "Walk forward one metre."
python3 send.py text "Turn right 90 degrees."
python3 send.py text "Stop!"
python3 send.py text "Walk forward 50 metres."
```

The last one must be blocked and the robot must not move.

### Step 9. Shut down

1. `python3 send.py stop`
2. Ctrl+C in Terminals B and A. `cmd_vel_node.py` also sends zero speed when it closes.
3. The mentor puts the robot into a safe pose.
4. Ctrl+C in the Mac's `ollama serve` terminal.

## 5. If something goes wrong

| Problem | Likely cause | What to try |
|---|---|---|
| `curl` from the Jetson to the Mac fails | Ollama only listening locally, or the Mac firewall | Restart Ollama with `OLLAMA_HOST=0.0.0.0:11434`; allow incoming connections in macOS settings |
| `ros2 topic list` shows no `/odom` | Wrong ROS 2 setup, or a different `ROS_DOMAIN_ID` | Ask the mentor for the right setup command and domain ID |
| Node says "no recent /odom message ... movement refused" | `/odom` not arriving in this terminal | Check `ros2 topic echo --once /odom` in the same terminal |
| Messages appear on `/cmd_vel` but the robot does not move | Robot not standing or not in the right mode | Mentor checks the robot's mode |
| Robot moves noticeably further than asked | It needs distance to slow down | Lower `max_linear_speed`, record the overshoot |
| Anything unexpected | | Emergency stop first, then investigate |

## 6. Test record sheet

Fill one row per command. The real distance comes from the tape measure.

| # | Command | Via model? | Speed setting | Model answer | Approved? | `/odom` reported | Real measured | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | move 0.3 | no | 0.6 m/s | | | | | |
| 2 | turn 90 | no | 0.5 rad/s | | | | | |
| 3 | move 1.0 | no | 0.6 m/s | | | | | |
| 4 | move 2.0, then stop | no | 0.6 m/s | | | | | |
| 5 | "Walk forward one metre." | yes | 0.6 m/s | | | | | |
| 6 | "Turn right 90 degrees." | yes | 0.5 rad/s | | | | | |
| 7 | "Walk forward 50 metres." | yes | | | | | | must be blocked |

Also note the date, the Jetson's JetPack version, the network used, and anything the mentor changes on the robot.

## 7. After the test

- Add the results to `docs/progress-log.md`.
- Compare real distance against `/odom` and against the requested distance.
- List what did not work and what to change before the next test.
