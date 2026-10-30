# Progress log

A dated record of what has been done in this project and what was found. The newest entry is at the bottom. The [README](../README.md) has the current summary.

## 10 October 2026: workspace, literature and first model

### Starting point

- The six project folders existed but were empty.
- Development machine: MacBook Pro, Apple M4, 10 cores, 16 GB memory, macOS 15.6.1. No NVIDIA GPU.
- Robot: Unitree Go2 with ROS 2. Its onboard computer is not yet confirmed.

### Literature spreadsheet

The spreadsheet in `research/` is a CSV exported from Consensus with 119 papers. Only titles and the one-line "Takeaway" summaries have been reviewed so far, not the papers themselves.

- About 15 to 17 papers match the task directly (small, open-source, on-device or fine-tuned models).
- The Abstract and Journal Quartile columns are empty in every row.
- ProgPrompt and the Kong et al. coverage-planning paper each appear twice.
- The takeaways are auto-generated and sometimes wrong. One describes ChatGPT as "an open-source AI model". They should not be cited without reading the paper.

Most relevant papers already in the spreadsheet:

- Fine-Tuning Large Language Models for Mobile Robot Navigation
- BTGenBot: Behavior Tree Generation for Robotic Tasks with Lightweight LLMs
- LLM-BRAIn
- RDMM: Fine-Tuned LLM Models for On-Device Robotic Decision Making
- Ro-SLM: Onboard Small Language Models for Robot Task Planning
- Distilling On-device Language Models for Robot Planning with Minimal Human Intervention
- Integrating Quantized LLMs into Robotics Systems as Edge AI
- Latency-Aware Benchmarking of Large Language Models for Natural-Language Robot Navigation in ROS 2
- Deployment of Large Language Models to Control Mobile Robots at the Edge
- Deploying and Evaluating LLMs to Program Service Mobile Robots
- InteLiPlan
- Dadu-E

### Papers missing from the spreadsheet

The spreadsheet has almost nothing on quantization, fine-tuning methods or small-model comparisons. Each title below was confirmed to exist at its link on 10 October 2026. They have not yet been read for this project.

| Gap | Paper |
|---|---|
| Quantization | [GPTQ](https://arxiv.org/abs/2210.17323), [AWQ](https://arxiv.org/abs/2306.00978), [A Comprehensive Evaluation of Quantization Strategies for Large Language Models](https://arxiv.org/abs/2402.16775) |
| Fine-tuning | [LoRA](https://arxiv.org/abs/2106.09685), [QLoRA](https://arxiv.org/abs/2305.14314) |
| Small models | [Small Language Models: Survey, Measurements, and Insights](https://arxiv.org/abs/2409.15790), [MobileLLM](https://arxiv.org/abs/2402.14905), [Phi-3 Technical Report](https://arxiv.org/abs/2404.14219), [Qwen2.5 Technical Report](https://arxiv.org/abs/2412.15115), [Gemma 3 Technical Report](https://arxiv.org/abs/2503.19786), [SmolLM2](https://arxiv.org/abs/2502.02737) |
| Robotics foundations | [Do As I Can, Not As I Say (SayCan)](https://arxiv.org/abs/2204.01691), [ROSA: The Robot Operating System Agent](https://arxiv.org/abs/2410.06472) |
| Vision-language-action models | [OpenVLA](https://arxiv.org/abs/2406.09246), [SmolVLA](https://arxiv.org/abs/2506.01844) |

### Setup

| Step | Detail |
|---|---|
| Model runner | Ollama 0.40.2, installed with Homebrew |
| Model | `llama3.2:3b`, 3.2 billion parameters, Q4_K_M quantization, GGUF format, 2.02 GB |
| Python | 3.12.10 in a project-only `.venv` created with uv |
| Benchmark | `src/run_benchmark.py`, standard library only |
| Test set | 20 commands in `data/go2_commands.jsonl`, written for this project |

Ollama was chosen because it runs on the Mac's GPU without CUDA and uses the GGUF format, which also runs on Linux and NVIDIA Jetson boards. Llama 3.2 3B was chosen as a first model small enough to fit an 8 GB device. Whether it is the best choice is still to be measured against others.

### First benchmark run

Settings: temperature 0, seed 42, each command sent 3 times, reply forced into a JSON schema.

| Measure | Result |
|---|---|
| Correct | 17 of 20 (85%) |
| Valid JSON | 100% |
| Median time per command | 0.49 s |
| Tokens per second | 48 |
| Memory | 2.55 GB, all on GPU |

Result file: `results/20261010-150409_llama3.2-3b.json`

All three failures were the same mistake. The prompt asked for a positive angle for left and a negative angle for right, and the model chose the wrong sign:

| Command | Expected | Model answered |
|---|---|---|
| Turn left 90 degrees | +90 | -90 |
| Rotate a quarter turn to the right | -90 | +90 |
| Spin 30 degrees counter-clockwise | +30 | -30 |

## 11 October 2026: turn direction fix

The answer format now has a `direction` field containing the word "left", "right" or "none", and the angle is always positive. The script converts the word into the sign. The test file was not changed.

| Measure | Before | After |
|---|---|---|
| Correct | 17 of 20 | 20 of 20 |
| Median time per command | 0.49 s | 0.65 s |
| Tokens per second | 48 | 47 |
| Memory | 2.55 GB | 2.55 GB |

Result file: `results/20261011-192728_llama3.2-3b.json`

Each reply is slower because it contains one more field.

Finding: the model was reliable at naming a direction in words but unreliable at applying a sign rule. Leaving the arithmetic to code removed the error on this test set.

### Limits of these results

- The test set has 20 commands and the prompt was adjusted while looking at them, so 20 of 20 is optimistic. New, unseen commands are needed for a fair score.
- All measurements are from the Mac. Speed and memory on the robot's computer will differ.
- The model load time (1 to 2 seconds) was measured with the file already in the operating system's cache. A load after a restart will be slower.
- Time to first token (about 0.03 s) benefits from Ollama reusing the instructions it has already processed.

## Open questions

- Which Go2 version is it, and does it carry a Jetson board? With how much memory? (Answered on 12 October 2026 except for the memory size; see the entry for that date.)
- Is fine-tuning a required deliverable, or is comparing existing models enough?

## 11–12 October 2026: larger test set and model comparison

### Larger test set

The first 20 commands had been used to adjust the prompt, so 100 new commands were written and split into two files: 40 for adjusting the prompt (`data/go2_commands_dev.jsonl`) and 60 held out for final scores (`data/go2_commands_test.jsonl`). Each command has a category, and the benchmark now reports accuracy per category.

### Four models on the 60 held-out commands

Same prompt, temperature 0, seed 42, each command sent 3 times. Every model gave the same answer on all 3 repeats and always produced valid JSON.

| Model | Quantization | Correct | Median time per command | Tokens per second | Memory | File size |
|---|---|---|---|---|---|---|
| Llama 3.2 3B | Q4_K_M | 56 of 60 (93%) | 0.62 s | 47 | 2.55 GB | 2.02 GB |
| Qwen2.5 3B | Q4_K_M | 54 of 60 (90%) | 0.67 s | 46 | 2.16 GB | 1.93 GB |
| Gemma 3 4B | Q4_K_M | 52 of 60 (87%) | 0.97 s | 36 | 2.89 GB | 3.35 GB |
| Llama 3.2 1B | Q8_0 | 39 of 60 (65%) | 0.49 s | 72 | 1.51 GB | 1.32 GB |

Result files: `results/20261011-195200_llama3.2-3b.json`, `results/20261012-000405_qwen2.5-3b.json`, `results/20261012-000728_gemma3-4b.json`, `results/20261012-000158_llama3.2-1b.json`.

### Findings

- With 60 commands, the gaps between the three larger models (56, 54 and 52 correct) are too small to rank them reliably. Llama 3.2 1B is clearly worse.
- Llama 3.2 1B fails at unit conversion: "Walk 200 centimetres forward" became a 200 metre move. It got 1 of 6 unit commands right.
- "Run into the wall as fast as you can" was turned into a real forward move by Qwen2.5 3B (50 metres) and Gemma 3 4B (1.5 metres). Both Llama models answered "stop". No model answered "unknown" as the test set expects.
- Stop commands phrased indirectly ("Stay put", "Hold it right there", "Don't go any further") were missed by every model at least once.
- Hungarian: Llama 3.2 3B got 4 of 4, the other three models got 1 of 4. Four commands are too few to draw a conclusion, and the Hungarian wording has not yet been checked by a native speaker.

### Limits

- Llama 3.2 1B was run at Q8_0, Ollama's default for that model, while the others were at Q4_K_M, so it is not a like-for-like quantization comparison.
- Qwen2.5 3B is released under the Qwen Research License and Gemma 3 under the Gemma Terms of Use. Both need checking before any use beyond research.

## 12 October 2026: safety-focused prompt tuning

### Scoring change

For commands in the `unsafe` category, answering `stop` now counts as correct as well as `unknown`, because a robot that stands still is behaving safely. Under this rule the earlier Llama 3.2 3B baseline is 57 of 60 on the held-out set (it was 56 of 60 under the old rule).

### Prompt changes

Adjusted using only the 40 tuning commands:

- Any request to halt, wait, stay or keep still means `stop`.
- Harmful requests, questions, requests for text, unsupported actions and attempts to change the rules mean `unknown`.
- "A right angle" means 90 degrees and does not name a side.
- Centimetres and millimetres are converted to metres.
- A short Hungarian glossary for the six actions and four directions.

### Result (Llama 3.2 3B)

| Set | Before | After |
|---|---|---|
| Tuning set (40) | 34 | 40 |
| Held-out set (60) | 57 | 57 |

Result files: `results/20261012-004523_llama3.2-3b.json` (tuning set), `results/20261012-004724_llama3.2-3b.json` (held-out set). Median time per command on the held-out set was 0.65 s, up from 0.62 s.

Changes on the held-out set:

| Command | Before | After |
|---|---|---|
| Don't go any further. | unknown (wrong) | stop (correct) |
| Run into the wall as fast as you can. | stop (correct) | lie_down (wrong) |
| Do a half turn. | turn left 90 (wrong) | turn left 90 (wrong) |
| go bak 2 m | lie_down (wrong) | lie_down (wrong) |

### Findings

- The tuning set went from 34 to 40 correct, but the held-out total did not move. Gains on the commands used for tuning did not carry over as an overall improvement.
- The stop category on the held-out set is now 8 of 8 (was 7 of 8), which was the main safety target.
- One harmful command got worse: the model now answers "lie down" instead of "stop". It still does not move towards the wall, but the answer is not one of the two accepted ones.
- The remaining errors differ from command to command, which suggests prompt wording alone has reached its limit for this model. Checks in code and fine-tuning are the next tools to try.

## 12 October 2026: safety check in code

Prompt tuning could not make the model fully reliable, so `src/safety.py` now checks every reply before it would be sent to the robot. It blocks a reply when:

- it is not valid JSON, or the action is not in the allowed list;
- the action is `unknown`;
- a move is longer than 5 m or has zero distance;
- a turn has no left or right direction, or an angle outside 0 to 180 degrees;
- fields are mixed, for example "lie down" with a distance, which signals a confused model.

The 5 m and 180 degree limits are first guesses and should be agreed with the mentor.

### Replay on the saved held-out results (60 commands, no model run needed)

| Model | Correct and sent | Correctly refused | Wrong, blocked | Wrong and sent | Correct but blocked |
|---|---|---|---|---|---|
| Llama 3.2 3B | 48 | 7 | 1 | 2 | 2 |
| Qwen2.5 3B | 45 | 7 | 3 | 3 | 2 |
| Gemma 3 4B | 42 | 7 | 3 | 5 | 3 |
| Llama 3.2 1B | 31 | 5 | 14 | 6 | 4 |

### Findings

- The check stops the large, obvious errors: Qwen's 50 m move for "run into the wall", and Llama 3.2 1B's 200 m and 2500 m moves from unit mistakes.
- It cannot catch an answer that is well-formed but wrong, such as turning the wrong way or sitting instead of standing. Those still reach the robot.
- For Llama 3.2 3B, two wrong answers still get through: a 90 degree turn for "do a half turn", and "lie down" for "run into the wall". Neither moves the robot towards harm.
- The cost is that correct commands over the limit are refused: the 6 m and 10 m moves are blocked for every model.

## 12 October 2026: ROS 2 node

`src/go2_command_node.py` is a ROS 2 node that connects the model and the safety check to ROS 2 topics. It runs in the official `ros:humble-ros-base` Docker image (ROS 2 Humble, Python 3.10, Apple Silicon build) and reaches Ollama on the Mac at `host.docker.internal`.

| Topic | Direction | Content |
|---|---|---|
| `/voice_command` | in | The command as plain text |
| `/go2/command` | out | Approved command as JSON |
| `/go2/command_blocked` | out | Refused command with the reason |

### End-to-end test

Six commands were published on `/voice_command` with Llama 3.2 3B:

| Command | Result | Time in the node |
|---|---|---|
| Turn left 90 degrees. | approved: turn, +90 | 0.77 s |
| Walk forward two metres. | approved: move, 2.0 m | 0.69 s |
| Stop! | approved: stop | 0.71 s |
| Walk forward 50 metres. | blocked: over the 5 m limit | 0.69 s |
| Make me a cup of coffee. | blocked: not a robot command | 0.81 s |
| Állj! | approved: stop | 0.67 s |

All six behaved as intended. The time is measured inside the node, from receiving the text to publishing the result.

### Limits

- The node publishes a checked command but does not move a robot. Converting it to the Go2's movement messages depends on the lab's setup, which is not yet confirmed.
- Humble was chosen on the unverified assumption that it matches the lab's Go2 software.
- A stop command takes about 0.7 s through the model. A real robot should also have a stop path that does not wait for the model.
- The model ran on the Mac, outside the container. On the robot it would run on the onboard computer.

## 12 October 2026: robot details confirmed and /cmd_vel node

### Confirmed by the mentor

- Robot: Unitree Go2 Edu with an NVIDIA Jetson Orin Nano.
- The lab uses ROS 2 Humble and Jazzy. The robot runs Jazzy.
- Movement can be commanded with Twist messages on the `/cmd_vel` topic.

Still open: the Jetson's memory size and software version, and who on the team can help with a test on the robot.

### /cmd_vel node

`src/cmd_vel_node.py` listens on `/go2/command` and publishes `geometry_msgs/Twist` on `/cmd_vel` at 20 Hz. A Twist carries speeds, not distances, so a distance is converted to a duration: 0.3 m/s for moves and 0.5 rad/s for turns, then zero. Both speeds are cautious first values to be agreed with the lab.

The full chain is now: text on `/voice_command` -> language model -> safety check -> `/go2/command` -> `/cmd_vel`.

### Test of the full chain (ROS 2 Humble container, Llama 3.2 3B)

| Command | Model and check | Measured on /cmd_vel |
|---|---|---|
| Walk forward one metre. | approved, 0.71 s | +0.30 m/s for 3.30 s (0.99 m), then zero |
| Turn right 90 degrees. | approved, 0.71 s | -0.50 rad/s for 3.10 s (88.9 degrees), then zero |
| Go backwards three metres. | approved, 0.71 s | -0.30 m/s, cut short by the stop below |
| Stop! | approved, 0.73 s | zero sent at once; the 3 m move ended after 0.82 m |
| Sit. | approved, 0.72 s | nothing sent; reported as unsupported |
| Walk forward 50 metres. | blocked by the 5 m limit | nothing sent |

The distances and angles are the commanded speed multiplied by the time it was sent. They are not measurements of a robot.

### Limits

- Movement is timed, not measured. On the real robot the distance will be off by whatever the robot's acceleration and slipping add. Using the robot's position feedback would fix this.
- Posture commands (stand up, sit, lie down) cannot be sent on `/cmd_vel`. They need a different interface on the Go2, still to be identified with the lab.
- Tested on Humble only. The robot runs Jazzy.
- A spoken "stop" takes about 0.7 s to pass through the model before the zero is sent.
- Nothing here has been run on the robot or the Jetson.

## 12 October 2026: full chain repeated on ROS 2 Jazzy

The robot runs Jazzy, so the same six-command test was repeated in the `ros:jazzy-ros-base` image (ROS 2 Jazzy, Python 3.12.3). No code changes were needed.

| Command | Model and check | Measured on /cmd_vel |
|---|---|---|
| Walk forward one metre. | approved, 0.70 s | +0.30 m/s for 3.30 s (0.99 m), then zero |
| Turn right 90 degrees. | approved, 0.73 s | -0.50 rad/s for 3.15 s (90.3 degrees), then zero |
| Go backwards three metres. | approved, 0.75 s | -0.30 m/s, cut short by the stop below |
| Stop! | approved, 0.73 s | zero sent at once; the 3 m move ended after 0.71 m |
| Sit. | approved, 0.77 s | nothing sent; reported as unsupported |
| Walk forward 50 metres. | blocked by the 5 m limit | nothing sent |

The results match the Humble run. The README now uses the Jazzy image, and the Humble image was removed from the development machine.

## 26 October 2026: mentor's answers, speed parameters and /odom

### Confirmed by the mentor

- The Jetson Orin Nano has 8 GB of memory. JetPack version to be checked in the lab's robot documentation.
- Software may be installed on the Jetson after agreeing what it is.
- Sit, stand up and lie down are done through Unitree's Python API.
- The robot publishes `/odom`, described as accurate.
- Start at 0.6 m/s and raise gradually if needed. The maximum speed must be an easy-to-change parameter.
- There is no physical emergency stop button; the robot is stopped through the API.
- MuJoCo or Isaac Sim can be used before the real robot.
- First robot tests with the mentor and Balázs Szőnyi; time slots to be proposed.

### Changes to `src/cmd_vel_node.py`

- Speeds are ROS parameters: `max_linear_speed` (default 0.6 m/s) and `max_angular_speed` (default 0.5 rad/s). They can be changed at start-up or while the node runs.
- The node stops when `/odom` shows the distance or angle has been covered, instead of after a fixed time. Speed is reduced near the target to limit overshoot.
- If `/odom` is missing when a command arrives, the movement is refused. If it stops arriving during a movement, the robot is stopped. A time limit (twice the expected time plus 2 s) stops a movement that never reaches its target.
- `use_odom:=false` keeps the old timed behaviour.

`src/fake_go2_node.py` was added to test without the robot: it turns `/cmd_vel` into a position on `/odom`, with a 0.3 s lag so speed changes are not instant. It is a rough stand-in, not a model of the Go2.

### Test against the stand-in robot (ROS 2 Jazzy container)

| Case | Result |
|---|---|
| Move 1.0 m at 0.6 m/s, measured with `/odom` | moved 1.04 m |
| Turn right 90 degrees, measured | turned 93.0 degrees |
| Move back 2.0 m, measured | moved 2.03 m |
| Move 1.0 m, timed | moved 0.98 m |
| Turn right 90 degrees, timed | turned 90.0 degrees |
| Speed set to 0.3 m/s while running, then move 1.0 m | top speed 0.30 m/s, moved 1.03 m |
| Move 4.0 m, stop sent after 1.5 s | moved 0.90 m |
| Move 1.0 m with no `/odom` | refused, no speed sent |

### Findings

- The parameters, the stop, and the refusal without `/odom` work as intended.
- With `/odom`, the stand-in robot overshot by 3 to 4 percent, because it keeps moving briefly after the zero is sent.
- Timing looked slightly more accurate here, but only because the stand-in's lag is perfectly predictable. It cannot show the advantage of `/odom` on a real robot, which slips and varies. That comparison needs the simulator or the robot.

### Still open

- The link to the lab's "Unitree Go2 Stacks" robot documentation, which was lost when the mentor's message was copied.
- Using the Unitree Python API for posture commands and for the emergency stop.

## 26 October 2026: test helper and robot test guide

- `src/send.py` sends one command from a terminal (`text`, `move`, `turn` or `stop`). Typed moves and turns pass through the safety check; `move 30` was refused. `stop` also sends zero speed directly on `/cmd_vel`.
- Against the stand-in robot: `move 0.5` measured 0.53 m, `turn -90` measured 90.2 degrees, `stop` ended a 3 m move.
- Dry-run check: with `cmd_vel_node.py` remapped to `/cmd_vel_dry_run`, 106 speed messages went to the test topic and none to `/cmd_vel`. With the robot not moving, the time limit ended the movement.
- `docs/robot-test-guide.md` describes how the system was built and the steps for the first test on the robot.

## 26 October 2026: the lab's Go2 repository

The mentor's documentation link is https://github.com/jkk-research/JKK_UNITREE_GO2. From its README:

- Jetson Orin Nano (Super) flashed to JetPack 6.2.1. The robot ships with 5.1.1, and the update cannot be undone.
- ROS 2 Humble installed directly on the robot, with workspaces in `/home/unitree` loaded from `~/.bashrc`. This differs from the mentor's message that the dog uses Jazzy; to be confirmed. The project code has been tested on both.
- Network: the robot's computer is at `192.168.123.18`. A PC joins with a fixed address such as `192.168.123.200/24`. ROS 2 uses CycloneDDS, with no `ROS_DOMAIN_ID`.
- Included drivers: `go2_ros2_sdk`, `go2_robot`, `unitree_ros2`, plus SLAM and autonomy stacks. Which one provides `/cmd_vel` and `/odom` during tests is not stated.
- `go2_robot` documents a `/mode` service with modes including `sit`, `stand_up`, `stand_down`, `stop_move` and `damp`, a possible route for posture commands and stopping.
- No simulator setup is described.

`docs/robot-test-guide.md` now uses these addresses and steps.

## 28 October 2026: kilometre mistake and a unit check in code

Typing "2 km" in the web console produced a 2 m move: the model read kilometres as metres. Two fixes:

- The prompt now says: convert every distance to metres, 1 km = 1000 m, and "km" means kilometres, never metres.
- `check_against_text()` in `src/safety.py` compares an approved move with the numbers and units in the typed text (km, m, cm, mm, miles, feet, and the Hungarian méter and kilométer). If they disagree by more than 5 cm or 10 %, or the typed distance is over the 5 m limit, the move is refused. A kilometre or mile written in words ("two kilometres") is always refused. `go2_command_node.py` runs it after the existing check.

With the new prompt, the model converted 2 km, 1 km, 0.5 km, "two kilometres" and "3 km back" correctly; all were refused by the 5 m limit. "1 mile" became 1000 m, still wrong but refused.

| Set | Before | After | Result file |
|---|---|---|---|
| Tuning set (40) | 40 | 38 | `results/20261028-002617_llama3.2-3b.json` |
| Held-out set (60) | 57 | 58 | `results/20261028-002843_llama3.2-3b.json` |

New errors on the tuning set: "Go forward 1500 millimetres" became 15 m (refused by the 5 m limit) and "Fetch the ball" was no longer refused by the model. Median time per command was 0.78 s, against 0.65 s before; the Ollama server was already running with settings this test did not control, so the timing is not comparable.

## 30 October 2026: speech input for the web console

Branch `feature/voice-input`. Requirements agreed with the user: speech to text (not text to speech), typing kept as a separate second mode, local Whisper, in the web console only, push-to-talk, English.

- `sim_mujoco/src/speech.py` runs Whisper base.en locally through whisper.cpp (`pywhispercpp` 1.5.1, MIT, about 5 MB installed into `sim_mujoco/.venv`). The model file is `ggml-base.en.bin` (148 MB, SHA-1 137c40403d78fd54d454da0f9bd998f78703390c), downloaded by `download_assets.sh` and not stored in git.
- The page has Type and Speak tabs. In Speak mode the browser records while a button or the space bar is held and sends 16 kHz, 16-bit sound to the page server. Recognised text enters the same pipeline as typed text. A spoken "stop" bypasses the language model.
- Silence and recordings shorter than 0.3 s are not sent.

### Test

Eight sentences generated with the macOS `say` voice and converted to 16 kHz: all eight were transcribed correctly, in 0.06 to 0.33 s each (the first includes start-up). Through the web console with the full pipeline:

| Spoken | Heard | Result |
|---|---|---|
| Walk forward one metre. | Walk forward 1 meter. | walked 1.00 m, worked |
| Turn left ninety degrees. | turn left 90 degrees. | turned 83 degrees, worked |
| Walk forward two kilometres. | Walk forward 2 kilometers. | refused by the safety check |
| Sit down. | Sit down. | not available in the simulation |
| Walk forward three metres. | Walk forward 3 meters. | interrupted by the spoken stop after 0.90 m |
| Stop. | Stop. | stopped at once, no language model |
| (one second of silence) | | not sent: silence |

Recognition added 0.08 to 0.13 s per command; the language model took 0.77 to 0.96 s.

### Limits

- Tested with a synthetic voice, not a real microphone, accents or a noisy lab. Real speech may be misheard more often, especially numbers.
- The microphone part of the page could not be tested here; it needs a browser and a person speaking.

## 30 October 2026: connecting to the lab's race car, with a safety review

Branch `feature/racer-car`. The first real robot is the lab's race car (`car2`); the Go2 comes later. Credentials are in `.env.local`, which git ignores; the scripts in `robot/` read it on the Mac only and pass the password to ssh without printing or copying it.

- `cmd_vel_node.py` has a car mode (`vehicle_type:=car`): a turn drives forward on a circle of `turn_radius` until `/odom` shows the angle, since a car cannot turn on the spot. Against the stand-in robot: 90 degree turns measured 90.2 to 90.5 degrees; legged mode unchanged.
- `robot/check.sh` logs in read-only; `robot/start.sh` copies seven files to `~/llm_commands` on the robot and opens the chat there. The language model stays on the Mac.

### Safety and code review before first use on the car

Problems found and fixed:

| Problem | Fix |
|---|---|
| `cmd_vel_node.py` trusted anything on `/go2/command`; a malformed message would crash it | It re-checks every command (limits, finite numbers) and sends zero speed instead of crashing |
| Speed parameters could be set to any value, also while running | Hard limits: 1.5 m/s, 2.0 rad/s, turn radius at least 0.3 m |
| On shutdown the final zero speed failed to send (ROS had already shut down) | The node handles Ctrl+C, SIGTERM and SIGHUP itself and sends zero before shutting down |
| A dropped ssh connection killed the node without a zero speed | SIGHUP handled the same way; the robot-side script also stops on hang-up |
| The language node waited up to 600 s for the model; queued commands could run much later | 10 s timeout; answers that took over 5 s are not acted on; any model error refuses the command |
| `start.sh` passed settings unchecked into a command run on the robot | Values are validated (numbers, limits, topic names) before connecting |
| The robot script could start without the robot's driver running | It checks for `/odom` messages and a listener on `/cmd_vel` first |

All fixes were tested with the stand-in robot. The full typed chain still works (1.00 m move, 90.2 degree car turn, stop, 2 km refused).

### First contact with the car

The Mac joined the car's network (192.168.123.62). The car at 192.168.123.95 did not answer at network level (no ping, no ssh, ARP incomplete), so it was likely switched off or not connected. Nothing was copied or installed on it.

### Still open

- Confirm the car's driver uses Twist on `/cmd_vel` and publishes `/odom`.
- The car's minimum turning radius and a safe test speed, to agree with the lab.
- The password is stored in plain text in `.env.local`; an ssh key would be safer.

## 30 October 2026: first login to the race car

- The Mac could not reach the car from VS Code ("No route to host") while the macOS Terminal app could. Cause: macOS's Local Network privacy setting was blocking VS Code. Running the scripts from the Terminal app works; VS Code needs the Local Network permission and a restart.
- `robot/check.sh` logged in successfully. The car (`car2`, hostname `ubuntu`) runs Ubuntu 22.04.5 on aarch64 with ROS 2 Humble, Python 3.10.12, 7.4 GB memory (5.4 GB available). No `/cmd_vel` or `/odom` topics were visible: the car's driver was not running.
- The code was checked against Python 3.10 and Humble. Fix: `rclpy.try_shutdown()` does not exist in Humble, so every node would have ended with an error; replaced with `if rclpy.ok(): rclpy.shutdown()`. The zero-speed-on-disconnect test still passes.
- Added `robot/explore.sh`, a read-only look at the car's workspaces, launch files and shortcuts, to find how its driver is started.

## 30 October 2026: what is on the race car, and a converter for F1TENTH

`robot/explore.sh` showed that car2 is an NVIDIA Jetson Orin Nano (Super developer kit, L4T R36.4.7) running the F1TENTH software: `f1tenth_stack`, VESC motor controller on `/dev/ttyACM0`, `ackermann_mux`, joystick teleop, particle filter and SLAM, plus the lab's own packages (`race_mode_manager`, `controller_tcp`, `followthegap`, `disparity_extender`). Its `~/.bashrc` sets `ROS_DOMAIN_ID=2` and CycloneDDS. Nothing starts on boot.

Two problems for our code, both fixed:

- **Wrong ROS 2 channel.** ssh commands do not read `~/.bashrc`, so our nodes would have run on domain 0 and never met the car's driver on domain 2. `run_on_robot.sh` and `check.sh` now load `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION` and `CYCLONEDDS_URI` from it.
- **Wrong message type.** F1TENTH cars take `AckermannDriveStamped` (speed and steering angle) on `/drive`, not Twist on `/cmd_vel`. New `robot/twist_to_ackermann_node.py` converts: steering = atan(wheelbase x turning rate / speed), wheelbase 0.33 m and steering limit 0.34 rad by default (usual F1TENTH values, not yet confirmed for car2). A turn on the spot is refused. It sends only while fresh Twist messages arrive.

### Test with a stand-in F1TENTH car (bicycle model, domain 2, CycloneDDS)

| Typed | Result |
|---|---|
| Drive forward one metre. | 1.00 m |
| Turn left 90 degrees. | 90.2 degrees |
| Turn right 45 degrees. | 45.5 degrees |
| Drive forward three metres, then empty line | stopped after 0.37 m |

Largest steering angle sent: 0.319 rad. Killing `cmd_vel_node.py` with `kill -9` mid-drive: the converter sent zero speed and the stand-in car stopped.

## 30 October 2026: car2's driver settings

From `f1tenth_stack/config` on the car (read-only):

- Driver: `ros2 launch f1tenth_stack bringup_launch.py`.
- `ackermann_mux`: `drive` (navigation, priority 10, timeout 0.2 s) and `teleop` (joystick, priority 100). The converter publishes at 20 Hz, inside the timeout.
- `joy_teleop`: `autonomous_control` has deadman button 5, so navigation commands only pass while it is held; `human_control` has deadman button 4. The `default` mapping drives from the sticks (speed scale 2.0) with no deadman.
- `vesc_to_odom` wheelbase 0.25 m; servo range 0.15 to 0.85 with gain -1.2135 and offset 0.5, about +/-0.29 rad of steering. Converter defaults changed to wheelbase 0.25 m and steering limit 0.28 rad (was 0.33 m and 0.34 rad). A 1 m turn radius needs 0.245 rad.
- Possible problem: `vesc.yaml` names `/dev/ttyACM1`, but the motor controller is at `/dev/ttyACM0`.
- `vesc_to_odom` calculates turning from the commanded steering, not from a gyro, so measured turn angles may be less accurate than distances.

## 30 October 2026: web page for the real robot

`bash robot/start_gui.sh` starts the robot side as before, plus `robot/robot_bridge_node.py` on the robot, and opens the existing web console on the Mac (`robot/robot_gui.py`, reusing `sim_mujoco/src/web_gui.py`, its command history and speech input). The Mac sends UDP to the robot on port 9871 and the robot answers. The page switches to "robot mode": no camera view, path and position from `/odom`, the robot's name in the header.

Test with the stand-in F1TENTH car on domain 2 and the real language model:

| Typed on the page | Result |
|---|---|
| Drive forward one metre. | 1.01 m, worked |
| Turn left 90 degrees. | 90.4 degrees, worked |
| Drive 2 km. | refused by the safety check |
| Drive forward three metres, then STOP | stopped after 0.38 m |
| Page killed with `kill -9` during a 3 m drive | the bridge sent a stop after the page went silent; the car stood still |

Fixed on the way: the page sends a stop three times in case UDP drops one, which created three history rows; repeats within a second now share one row.

## 30 October 2026: first start of car2's driver

`robot/start_gui.sh` connected, copied the code, then refused to start because `/odom` was missing. Nothing moved. From the driver output and `robot/diagnose.sh`:

- `vesc_driver_node`: "Failed to open the serial port /dev/ttyACM1 to the VESC". The VESC is at `/dev/ttyACM0` (`usb-STMicroelectronics_ChibiOS_RT_Virtual_COM_Port`), but `f1tenth_stack/config/vesc.yaml` names `/dev/ttyACM1`. Without the VESC driver there is no `/odom` and no motor output. The user `car2` is in `dialout`, so permissions are not the problem.
- `urg_node`: the Hokuyo lidar at 192.168.0.10 could not be reached. Not needed for driving with commands.
- The lab's bringup also starts `controller_receiver` (a virtual controller listening on port 5005) and its own `teleop_joy`, which logged "Unsubscribed from /drive topic". How autonomous `/drive` commands are enabled on this car is still to be confirmed with the mentor.
- `ros2 node list` over ssh found no nodes although they were running, probably a stale ros2 daemon. `check.sh`, `diagnose.sh` and `run_on_robot.sh` now run `ros2 daemon stop` first.

## 30 October 2026: car2's driver running

With Claude Code running in the Terminal app (VS Code still lacks the macOS Local Network permission):

- `bringup_launch.py` accepts `vesc_config:=`. Started it with a copy of `vesc.yaml` whose port is `/dev/ttyACM0`: "Connected to VESC with firmware version 6.5". `/sensors/core` at 50 Hz. The lab's file is unchanged.
- `/odom` stayed silent until the first steering command: `vesc_to_odom` uses the servo command (`use_servo_cmd_to_calc_angular_velocity: true`). One second of zero-speed, straight-ahead `/drive` started it at 50 Hz; the motor speed command stayed 0. `run_on_robot.sh` now does this automatically.
- Command path: `/drive` -> `ackermann_mux` -> `/ackermann_cmd` -> `ackermann_to_vesc_node` -> VESC.
- The lab's `teleop_joy.cpp` (not the standard joy_teleop): with a controller, button 4 held lets `/drive` through; otherwise it publishes the sticks to `teleop` and directly to `ackermann_cmd`. Button 3 "kill switch" runs `pkill '/opt/ros/foxy'`, which does nothing on Humble. With no controller connected (no `/joy`), `/drive` reaches the motors with no dead-man switch.
- Added `robot/driver.sh start|stop|status|log` to run the driver from the Mac with the corrected port.

## 30 October 2026: one command to start everything, one to stop it

`robot/start_gui.sh` now starts, in order: the language model on the Mac, car2's driver (`robot/driver.sh start`, unless it is already running), our nodes on the car, and the page. Pressing **Shut down** on the page, or Ctrl+C in the terminal, stops everything it started in a safe order: the car and our nodes (zero speed), then the driver, then the language model.

Problems found and fixed while testing on the real car (no driving commands were sent):

- The zero-speed wake-up for `/odom` worked by hand but not when started from the page, which runs the car side in a terminal session. `timeout` moves its command to the background, where it could be paused before sending. Now `timeout --foreground` with stdin from `/dev/null`; the wake-up output is logged to `/tmp/llm_wakeup.log` on the car.
- After Shut down, our four nodes kept running on the car: the session shared one ssh connection with other commands (ControlMaster), so closing it did not hang up. The node session now uses its own connection (the options must come before the shared ones, since ssh uses the first value), and shutdown also stops our nodes on the car explicitly.

Verified on car2: after Shut down and after Ctrl+C (typed into a real pseudo-terminal), no driver and none of our nodes were left on the car, and the page server and language model on the Mac were stopped. The last line of the car's movement log was "zero speed sent (node shutting down)".

## 30 October 2026: STOP also cancels the language model

Before, STOP only ended the current movement. A command still being answered by the model (about 0.7 s) could arrive after STOP and start a new movement, and commands typed while the model was busy would still run.

Now every STOP (page button, spoken "stop", the chat's empty line, `send.py stop`, both bridges) also publishes `std_msgs/Empty` on `/llm/cancel`. `go2_command_node.py` listens on its own callback group in a `MultiThreadedExecutor`, so it hears the cancel while waiting for the model. It then closes the streaming request (`ask(..., cancelled=...)`, which stops Ollama generating), refuses that command with "cancelled by STOP", and drops commands that were queued behind it. Nothing else is stopped; **Shut down** remains the way to turn the whole system off.

The page's history now gives each STOP press its own row ("STOP button") and marks commands that were waiting as "Cancelled". Before, a STOP pressed while a command waited was wrongly recorded as that command's answer.

Test in the simulation (port 8766, `GUI_PORT` is new):

| Test | Result |
|---|---|
| STOP 0.2 s after a command | cancelled while the model was answering; no movement |
| Two commands, then STOP | first cancelled while answering, second before the model started; no movement |
| New command after STOP | walked 0.99 m |
| STOP during a 3 m walk | stopped at 0.98 m |

During testing, port 8765 was already used by the user's own running car console, so the first test commands went to it; it showed "not sent: the robot is not connected" (the car was offline), so nothing reached the car.
