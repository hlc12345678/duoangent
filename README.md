# Multi-Agent Autonomous Coding & Verification Framework for Embedded Systems

## Background
Embedded IoT teams frequently face high-latency iteration cycles: hardware constraints require precise firmware, while human review queues slow down verification. This framework shortens those loops by orchestrating multiple LLM-style agents that collaboratively plan, generate, and review RTOS firmware artifacts in a single automated flow. The system explicitly embraces "High-Frequency Token Consumption", "Deep Context Windows", and "Agentic Self-Correction loops" to accelerate convergence from requirements to verified C/C++ output without waiting on long manual handoffs.

## Architecture Overview
The coordinator drives a structured conversation between independent agent roles: the Planner converts natural language into a hardware spec, the Coder synthesizes RTOS-ready C/C++ firmware, and the Reviewer performs safety checks before producing a final artifact or requesting a fix. A compact memory module ensures no more than three code-review-fix cycles.

```
User
  |
  v
Planner Agent
  |
  v
Coder Agent <-----> Reviewer Agent
  |
  v
Final Output
```

## Project Structure
```
.
├── agents/
│   ├── coder_agent.py
│   ├── planner_agent.py
│   └── reviewer_agent.py
├── agent_memory.py
├── multi_agent_coordinator.py
├── requirements.txt
└── README.md
```

## Getting Started
1. Ensure Python 3.9+ is available.
2. Install dependencies (none required beyond the standard library):
   ```bash
   pip install -r requirements.txt
   ```
3. Run the coordinator with a request:
   ```bash
   python multi_agent_coordinator.py "Setup an I2C task for an OLED display with FreeRTOS"
   ```

## How It Works
- **Planner Agent** produces a structured hardware specification (pins, RTOS tasks, memory budget).
- **Coder Agent** generates ESP-IDF or STM32 HAL style firmware using mock LLM calls.
- **Reviewer Agent** scans for memory leaks, deadlocks, and buffer overflows, returning Pass or Fail with feedback.
- **Agent Memory** enforces a maximum of three corrective iterations.

## Enterprise Notes
This repository is intentionally designed as a runnable reference for multi-agent embedded firmware workflows. The LLM calls are mocked for safety and reproducibility, while the routing logic and review loop are fully implemented.
