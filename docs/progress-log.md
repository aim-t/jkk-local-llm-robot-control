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

- Which Go2 version is it, and does it carry a Jetson board? With how much memory?
- Is fine-tuning a required deliverable, or is comparing existing models enough?
