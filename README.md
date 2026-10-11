# Local LLMs for the Unitree Go2

This project tests whether small open-source language models can turn spoken-style commands such as "turn left 90 degrees" into safe, structured robot commands, running entirely on local hardware with no cloud service.

It is an internship project at the Vehicle Industry Research Center (JKK), Széchenyi István University.

## Internship task

> The intern will investigate the use of fine-tuned open-source large language models (LLMs) in mobile robotics applications. The work will include selecting suitable models, deploying and evaluating them for robotics-related tasks, and, where feasible, running optimized models on the robot’s local computing hardware. Particular attention will be given to inference speed, resource usage, and integration with the robot’s software stack.

## Current status

One model runs locally and is measured by a repeatable benchmark. It has not yet been connected to ROS 2 or run on the robot.

| Measure | Result |
|---|---|
| Model | Llama 3.2 3B, 4-bit (Q4_K_M), run with Ollama |
| Correct commands | 57 of 60 held-out commands (95%) |
| Time per command | 0.65 s (median) |
| Generation speed | 47 tokens per second |
| Memory used | 2.55 GB |
| Model file size | 2.02 GB |

Measured on a MacBook Pro (Apple M4, 16 GB memory). The 60 held-out commands were not used to adjust the prompt. Speed and memory will differ on the robot's own computer.

The [progress log](docs/progress-log.md) describes every step taken so far, including the comparison with three other models.

## Features

- Sends each test command to a local model and forces the reply into a fixed JSON shape.
- Checks the reply against the expected answer.
- Records accuracy, time to first token, total time, tokens per second, memory use and model file size.
- Saves each run with the exact model version, prompt and settings so it can be repeated.

Example:

```text
"Rotate a quarter turn to the right."
-> {"action": "turn", "distance_m": 0, "direction": "right", "angle_deg": 90}
```

## Installation

These steps are for a Mac with Apple Silicon. You need [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/).

```bash
brew install ollama
ollama serve
```

Leave that terminal open. In a second terminal, download the model (about 2 GB) and create the Python environment from the project folder:

```bash
ollama pull llama3.2:3b
uv venv --python 3.12
```

The benchmark uses only the Python standard library, so there are no packages to install.

## Quickstart

With `ollama serve` running, start the benchmark from the project folder:

```bash
.venv/bin/python src/run_benchmark.py
```

It prints one line per command, then a summary, and saves a JSON file in `results/`.

## Usage

Test a different model that you have already pulled with Ollama:

```bash
.venv/bin/python src/run_benchmark.py --model qwen2.5:3b
```

Change how many times each command is sent (the default is 3):

```bash
.venv/bin/python src/run_benchmark.py --repeats 5
```

Use your own test file:

```bash
.venv/bin/python src/run_benchmark.py --data data/my_commands.jsonl
```

Chat with the model directly, without the robot instructions:

```bash
ollama run llama3.2:3b
```

To stop Ollama, press Ctrl+C in the terminal running `ollama serve`.

## Test commands

Each line of [data/go2_commands.jsonl](data/go2_commands.jsonl) is one command with its expected answer:

```json
{"id": 7, "command": "Turn right by 45 degrees.", "expected": {"action": "turn", "distance_m": 0, "angle_deg": -45}}
```

In the expected answer, a positive distance is forward and a positive angle is a left turn. The available actions are `move`, `turn`, `stand_up`, `sit`, `lie_down`, `stop` and `unknown`. `unknown` is the correct answer for anything the robot cannot do.

There are three command files:

| File | Commands | Purpose |
|---|---|---|
| `go2_commands.jsonl` | 20 | The first small set, kept so early results can be repeated |
| `go2_commands_dev.jsonl` | 40 | For adjusting the prompt |
| `go2_commands_test.jsonl` | 60 | Held out. Used only for final scores, never for adjusting the prompt |

The two larger files label each command with a category (`move`, `turn`, `posture`, `stop`, `units`, `noisy`, `hungarian`, `unsupported`, `unsafe`), and the benchmark reports accuracy for each one.

## Project layout

| Folder | Contents |
|---|---|
| `research/` | Literature spreadsheet (119 papers exported from Consensus) |
| `data/` | Test commands |
| `src/` | Benchmark script |
| `experiments/` | Experiment notes and configurations (empty so far) |
| `results/` | One JSON file per benchmark run |
| `docs/` | Progress log and reports |

## Next steps

1. Confirm which computer the Go2 carries and how much memory it has.
2. Score the model on the held-out test commands.
3. Compare other small models and quantization levels with the same benchmark.
4. Connect the model's output to ROS 2.
5. Fine-tune the best model.

## Contributing

This is an individual internship project. 

## License

No license has been chosen yet. The Llama 3.2 model is covered by Meta's Llama 3.2 Community License.
