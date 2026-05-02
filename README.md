# Multi-Agent Autonomous Coding & Verification Framework for Embedded Systems

> **An enterprise-grade, Python-based agentic AI pipeline that automatically generates, reviews, and optimises production-quality C/C++ firmware for RTOS-based microcontrollers (ESP32, STM32).**

---

## Table of Contents

1. [Background](#background)
2. [Architecture Overview](#architecture-overview)
3. [Agent Interaction Sequence](#agent-interaction-sequence)
4. [Project Structure](#project-structure)
5. [Agent Roles & Responsibilities](#agent-roles--responsibilities)
6. [Key Framework Capabilities](#key-framework-capabilities)
7. [Getting Started](#getting-started)
8. [Usage](#usage)
9. [Configuration](#configuration)
10. [Extending to Production LLMs](#extending-to-production-llms)
11. [Technical Deep-Dive](#technical-deep-dive)
12. [Roadmap](#roadmap)
13. [License](#license)

---

## Background

### The Problem: High-Latency Iteration in IoT Hardware Development

Traditional embedded firmware development for RTOS-based microcontrollers (ESP32, STM32, NXP i.MX RT, etc.) is plagued by painfully slow, human-gated iteration cycles:

```
 Engineer writes code  ──►  Compile  ──►  Flash  ──►  Runtime test
         ▲                                                   │
         └──────────── Manual code review & fix ────────────┘
                         (hours to days per cycle)
```

This model imposes several critical bottlenecks in production IoT development:

| Bottleneck | Impact |
|---|---|
| Manual code review latency | 4–48 hours per cycle in a typical team |
| Context switching between firmware logic and RTOS internals | High cognitive load; missed edge cases (deadlocks, memory leaks) |
| Domain expertise required | Senior engineers are scarce; junior developers introduce subtle RTOS bugs |
| Lack of automated RTOS-aware static analysis | Tools like PC-lint or MISRA checkers are expensive and environment-specific |

### The Solution: Multi-Agent Agentic Self-Correction

This framework replaces the slow, human-in-the-loop review cycle with a **Multi-Agent Autonomous Coding & Verification System**. Multiple specialised LLM agents collaborate in a closed loop, each with a distinct role and responsibility:

- **PlannerAgent** — Transforms free-form natural language into a precise, structured hardware specification (MCU, RTOS, peripheral pins, task parameters, memory constraints).
- **CoderAgent** — Generates production-quality, compilable C/C++ code that follows ESP-IDF or STM32 HAL standards with full FreeRTOS task hygiene.
- **ReviewerAgent** — Performs strict automated code review targeting the most critical embedded-systems defect categories: memory leaks, RTOS deadlocks, buffer overflows, ISR safety violations, and task hygiene issues.

The system's **Agentic Self-Correction loops** allow the Coder and Reviewer to iterate autonomously — the Reviewer feeds structured feedback back to the Coder, which regenerates corrected code — up to a configurable maximum of 3 iterations. This eliminates the human bottleneck for the majority of common defect patterns.

**Net result:** What previously took an experienced firmware team 1–3 business days (requirements clarification → first code → review → fixes) can now be completed in seconds, with guaranteed coverage of the most critical RTOS defect classes.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│              Multi-Agent Coordinator (Orchestration Layer)           │
│                    multi_agent_coordinator.py                        │
├──────────────┬──────────────────────────────┬───────────────────────┤
│  Planner     │        Coder Agent            │     Reviewer Agent    │
│  Agent       │     agents/coder_agent.py     │  agents/reviewer_agent│
│  agents/     │                               │          .py          │
│  planner_    │  • ESP-IDF / STM32 HAL code   │                       │
│  agent.py    │  • FreeRTOS task primitives   │  • Memory leak check  │
│              │  • Guarded heap allocation    │  • Deadlock detection │
│  • NL → JSON │  • Mutex/semaphore protection │  • Buffer overflow    │
│    spec      │  • MISRA-C naming             │  • ISR safety check   │
│              │                               │  • Task hygiene       │
└──────────────┴──────────────────────────────┴───────────────────────┘
                              │         ▲
                              │  AgentMemory (agent_memory.py)
                              │  • Stores iteration history
                              │  • Enforces max 3-loop limit
                              │  • Provides feedback context
                              ▼         │
                        ┌─────────────────┐
                        │  Final Output   │
                        │  C/C++ Source   │
                        │  (PASS / BEST   │
                        │   EFFORT)       │
                        └─────────────────┘
```

---

## Agent Interaction Sequence

The following ASCII sequence diagram illustrates the complete multi-agent interaction flow, from user input to verified code output:

```
User          Coordinator     PlannerAgent    CoderAgent    ReviewerAgent   AgentMemory
 │                │                │               │               │              │
 │  NL Request    │                │               │               │              │
 │───────────────►│                │               │               │              │
 │                │  plan(request) │               │               │              │
 │                │───────────────►│               │               │              │
 │                │                │  mock_zhipu_  │               │              │
 │                │                │  call(prompt) │               │              │
 │                │                │──────────────►│(LLM API)      │              │
 │                │                │◄──────────────│               │              │
 │                │   HardwareSpec │               │               │              │
 │                │◄───────────────│               │               │              │
 │                │                │               │               │              │
 │                │════════════════ ITERATION LOOP (max 3) ════════│══════════════│
 │                │                │               │               │              │
 │                │  generate(spec,│feedback?)     │               │              │
 │                │───────────────────────────────►│               │              │
 │                │                │               │mock_doubao_   │              │
 │                │                │               │call(prompt)   │              │
 │                │                │               │──────────────►│(LLM API)     │
 │                │                │               │◄──────────────│              │
 │                │   C/C++ Code   │               │               │              │
 │                │◄───────────────────────────────│               │              │
 │                │                │               │               │              │
 │                │  review(code)  │               │               │              │
 │                │───────────────────────────────────────────────►│              │
 │                │                │               │    mock_zhipu_│              │
 │                │                │               │    call(code) │              │
 │                │                │               │              ─┤ heuristic    │
 │                │                │               │               │ analysis     │
 │                │  ReviewResult  │               │               │              │
 │                │◄───────────────────────────────────────────────│              │
 │                │                │               │               │              │
 │                │  record_iter() │               │               │              │
 │                │─────────────────────────────────────────────────────────────►│
 │                │                │               │               │              │
 │                │  ┌─────────────────────────────┐               │              │
 │                │  │ PASS? ──────────────────────┼──────────────►│ Exit loop    │
 │                │  │ FAIL + iterations_remaining? │               │              │
 │                │  │  Yes ──► feedback → Coder   │               │              │
 │                │  │  No  ──► Best Effort output │               │              │
 │                │  └─────────────────────────────┘               │              │
 │                │════════════════ END LOOP ═══════════════════════│══════════════│
 │                │                │               │               │              │
 │  Final Code    │                │               │               │              │
 │◄───────────────│                │               │               │              │
 │  + Status      │                │               │               │              │
 │  + History     │                │               │               │              │
```

---

## Project Structure

```
duoangent/
├── multi_agent_coordinator.py   # Main entry point & orchestration engine
├── agent_memory.py              # Shared context & iteration management
├── agents/
│   ├── __init__.py              # Package exports
│   ├── planner_agent.py         # NL → HardwareSpec (ZhipuAI backend)
│   ├── coder_agent.py           # HardwareSpec → C/C++ code (Doubao backend)
│   └── reviewer_agent.py        # Code → Pass/Fail + feedback (ZhipuAI backend)
├── requirements.txt             # Python dependencies
└── README.md                    # This document
```

---

## Agent Roles & Responsibilities

### 1. PlannerAgent (`agents/planner_agent.py`)

**Input:** Free-form natural-language task description  
**Output:** Structured `HardwareSpec` JSON dictionary

The Planner Agent acts as the *Requirements Analyst*. It transforms ambiguous human intent into a precise, machine-readable hardware specification that covers:

- Target MCU (`ESP32`, `STM32F4`, etc.)
- RTOS selection (`FreeRTOS`)
- Peripheral configuration (interface type, GPIO pins, bus parameters)
- FreeRTOS task parameters (name, priority, stack size, period)
- Memory constraints (heap and stack budgets)
- Safety and timing constraints

**Mock backend:** `mock_zhipu_call()` — Keyword-based spec generation covering I2C, SPI, UART, GPIO, and ADC patterns.  
**Production backend:** ZhipuAI GLM-4 via the `zhipuai` SDK.

**Example output:**
```json
{
  "mcu": "ESP32",
  "rtos": "FreeRTOS",
  "peripherals": [
    {
      "name": "SSD1306_OLED",
      "interface": "I2C",
      "pins": {"SDA": "GPIO21", "SCL": "GPIO22"},
      "address": "0x3C"
    }
  ],
  "tasks": [
    {
      "name": "oled_display_task",
      "priority": 5,
      "stack_size": 4096,
      "period_ms": 100
    }
  ],
  "memory": {"heap_kb": 32, "stack_kb": 4},
  "constraints": ["I2C bus frequency: 400 kHz", "Use mutex for I2C bus"]
}
```

---

### 2. CoderAgent (`agents/coder_agent.py`)

**Input:** `HardwareSpec` (+ optional Reviewer feedback)  
**Output:** Complete, compilable C source code

The Coder Agent acts as the *Senior Firmware Engineer*. It generates code that:

- Follows ESP-IDF or STM32 HAL library conventions
- Wraps logic in properly-configured FreeRTOS tasks
- Guards every heap allocation with a `NULL` check
- Uses mutexes/semaphores to protect shared peripheral resources
- Uses ISR-safe FreeRTOS APIs within interrupt handlers
- Calls `vTaskDelete(NULL)` before any task function exit path

**Mock backend:** `mock_doubao_call()` — Template-based code generation with full peripheral support.  
**Production backend:** ByteDance Doubao `doubao-pro-128k` (OpenAI-compatible API).

**Supported peripheral templates:**
| Interface | MCU | Key FreeRTOS primitives |
|---|---|---|
| I2C (SSD1306 OLED) | ESP32 | Mutex, task, pvPortMalloc |
| SPI (DMA) | ESP32 | Semaphore, task, spi_device |
| UART (echo) | ESP32/STM32 | StreamBuffer, dual tasks |
| GPIO (LED + button) | ESP32 | Queue, ISR handler, tasks |
| ADC (moving average) | STM32 | Queue, oneshot ADC, task |

---

### 3. ReviewerAgent (`agents/reviewer_agent.py`)

**Input:** C/C++ source code string  
**Output:** `ReviewResult` (`PASS` / `FAIL` + structured feedback)

The Reviewer Agent acts as the *Principal Safety Engineer*. It performs strict heuristic analysis covering five defect categories:

| Category | Severity | Description |
|---|---|---|
| `MEMORY_LEAK` | ERROR | Heap allocation without `NULL` guard |
| `DEADLOCK` | ERROR | Infinite task loop with no FreeRTOS yield/block |
| `BUFFER_OVERFLOW` | ERROR | Use of unbounded string functions (`strcpy`, `sprintf`, etc.) |
| `ISR_SAFETY` | ERROR | Non-ISR-safe FreeRTOS APIs called from ISR context |
| `TASK_HYGIENE` | WARNING | Task function missing `vTaskDelete(NULL)` |

A **FAIL** verdict is returned if any `ERROR`-level issue is detected. In `strict_mode`, `WARNING`-level issues also cause `FAIL`.

---

### 4. AgentMemory (`agent_memory.py`)

**Manages:** Shared context, iteration history, and loop termination

The memory module is the *State Manager* of the framework:

- Stores every `MemoryEntry` (code, review status, feedback, timestamp)
- Enforces the **maximum 3-iteration** constraint
- Provides `best_code()` — returns the first `PASS` code, or the final iteration's code if no pass was achieved
- Supports `export_history()` for full audit trails (JSON-serialisable)
- Thread-safe by design (single-threaded coordinator pattern)

---

## Key Framework Capabilities

This framework is engineered around three core AI infrastructure paradigms that enable reliable, automated firmware generation at scale:

### 🔁 Agentic Self-Correction Loops

The Coder ↔ Reviewer feedback loop is the system's central innovation. Rather than producing code once and hoping for correctness, the framework implements a structured **agentic self-correction** cycle:

1. The Coder generates an initial code version
2. The Reviewer analyses it and produces structured, actionable feedback
3. The Coder receives the full feedback context and regenerates a corrected version
4. This cycle repeats until either a `PASS` verdict is achieved or the 3-iteration budget is exhausted

This mechanism mirrors the self-play training paradigm from reinforcement learning — the agent learns from its own mistakes within a single inference session.

### 📊 High-Frequency Token Consumption

Each iteration of the Coder ↔ Reviewer loop involves:
- **Planning call:** ~800–1,200 tokens (NL → structured spec)
- **Code generation call:** ~2,000–8,000 tokens (spec → full C file)
- **Review call:** ~2,000–8,000 tokens (code → issue analysis)
- **Correction call (if needed):** ~3,000–10,000 tokens (code + feedback → corrected code)

Over 3 iterations, a single pipeline run may consume **15,000–35,000 tokens**. This makes the framework a genuine **high-frequency token consumer** — appropriate for enterprise API quota allocations that support sustained, high-throughput agentic workloads.

### 🧠 Deep Context Windows

The framework is architected to exploit **deep context window** capabilities of modern LLMs (e.g., GLM-4-128k, Doubao-pro-128k):

- The **CoderAgent** receives the full `HardwareSpec` + the complete previous code + the full reviewer feedback in a single prompt, enabling true context-aware correction without losing information across turns.
- The **ReviewerAgent** analyses the complete source file in one shot — no chunking, no summarisation loss.
- **AgentMemory** preserves the full iteration transcript, which can be injected back into future calls for cross-session continuity.

This deep-context architecture is essential for embedded firmware tasks where the relationship between a memory allocation on line 45 and its usage on line 180 must be understood holistically.

---

## Getting Started

### Prerequisites

- Python 3.9 or later
- `pip` package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/hlc12345678/duoangent.git
cd duoangent

# (Recommended) Create a virtual environment
python -m venv .venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Quick Start (Mock Mode — No API Key Required)

The framework ships with fully-functional mock LLM backends. You can run the complete pipeline without any API credentials:

```bash
python multi_agent_coordinator.py --task "Setup an I2C task for an OLED display with FreeRTOS"
```

---

## Usage

### Interactive Mode

```bash
python multi_agent_coordinator.py
```

You will be prompted to enter a task description or select from the built-in examples.

### Command-Line Options

```
usage: multi_agent_coordinator [-h] [--task TASK] [--max-iterations N]
                               [--output FILE] [--strict] [--quiet]
                               [--export-history FILE]

Options:
  --task, -t TASK           Natural-language task description
  --max-iterations, -n N    Maximum Coder↔Reviewer iterations (default: 3)
  --output, -o FILE         Save final C/C++ code to file
  --strict                  Treat warnings as errors (strict review mode)
  --quiet, -q               Suppress verbose output; print only final code
  --export-history FILE     Export full iteration history as JSON
```

### Example Commands

```bash
# Generate I2C OLED display code and save to file
python multi_agent_coordinator.py \
  --task "Setup an I2C task for an OLED display with FreeRTOS" \
  --output oled_display_task.c

# SPI DMA task with strict review, 2 max iterations
python multi_agent_coordinator.py \
  --task "Create a SPI DMA transfer task for ESP32" \
  --max-iterations 2 \
  --strict \
  --output spi_dma_task.c

# UART echo task — quiet mode, export history
python multi_agent_coordinator.py \
  --task "Implement a UART echo task on STM32 with FreeRTOS" \
  --quiet \
  --output uart_echo.c \
  --export-history uart_session.json

# GPIO blink + button task
python multi_agent_coordinator.py \
  --task "Blink an LED on GPIO2 every 500ms with button debouncing"

# ADC sampling with moving average
python multi_agent_coordinator.py \
  --task "Read temperature sensor ADC data with 16-point moving average filter"
```

### Programmatic API

```python
from multi_agent_coordinator import MultiAgentCoordinator

coordinator = MultiAgentCoordinator(
    max_iterations=3,
    strict_review=False,
    verbose=True,
)

result = coordinator.run("Setup an I2C task for an OLED display with FreeRTOS")

print(f"Status     : {result['status']}")
print(f"Iterations : {result['iterations']}")
print(f"Final Code :\n{result['final_code']}")

# Access full iteration history
for entry in result['history']:
    print(f"  Iter {entry['iteration']}: {entry['review_status']}")
```

---

## Configuration

### AgentMemory

```python
from agent_memory import AgentMemory

memory = AgentMemory(
    task_description="My task",
    max_iterations=3,   # Default; increase for more correction attempts
)
```

### ReviewerAgent Strict Mode

```python
from agents import ReviewerAgent

# Default: only ERRORs cause FAIL
reviewer = ReviewerAgent(strict_mode=False)

# Strict: WARNINGs also cause FAIL
reviewer = ReviewerAgent(strict_mode=True)
```

---

## Extending to Production LLMs

### ZhipuAI GLM-4 (PlannerAgent & ReviewerAgent)

Replace `mock_zhipu_call` in `agents/planner_agent.py` and `agents/reviewer_agent.py`:

```python
import os
from zhipuai import ZhipuAI

def zhipu_call(system_prompt: str, user_message: str) -> str:
    client = ZhipuAI(api_key=os.environ["ZHIPU_API_KEY"])
    response = client.chat.completions.create(
        model="glm-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content
```

Then inject the backend:
```python
planner  = PlannerAgent(llm_backend=zhipu_call)
reviewer = ReviewerAgent(llm_backend=zhipu_call)
```

### ByteDance Doubao (CoderAgent)

Replace `mock_doubao_call` in `agents/coder_agent.py`:

```python
import os
from openai import OpenAI

def doubao_call(system_prompt: str, user_message: str) -> str:
    client = OpenAI(
        api_key=os.environ["DOUBAO_API_KEY"],
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    response = client.chat.completions.create(
        model="doubao-pro-128k",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content
```

Then inject:
```python
coder = CoderAgent(llm_backend=doubao_call)
```

---

## Technical Deep-Dive

### Why Three Agents?

The three-agent architecture maps directly onto the three phases of professional firmware development:

| Phase | Human Role | Agent Equivalent |
|---|---|---|
| Requirements analysis | Systems architect | PlannerAgent |
| Implementation | Senior firmware engineer | CoderAgent |
| Quality assurance | Principal safety engineer | ReviewerAgent |

Separating these concerns into distinct agents with separate system prompts prevents prompt contamination — each agent is laser-focused on its specific domain, resulting in higher-quality outputs than a monolithic "generate and review" prompt.

### Reviewer Heuristics

The `ReviewerAgent` uses five deterministic heuristic patterns that cover the most prevalent RTOS firmware defect classes (based on embedded systems defect taxonomy literature):

1. **Heap allocation without NULL guard** — `pvPortMalloc`/`malloc` calls checked for downstream NULL dereference
2. **Infinite loop without yield** — `for(;;)` / `while(1)` blocks checked for `vTaskDelay`, `xQueueReceive`, or similar blocking calls
3. **Unbounded string functions** — `strcpy`, `strcat`, `sprintf`, `gets` flagged unconditionally
4. **ISR safety** — Functions marked `IRAM_ATTR` / `ICACHE_RAM_ATTR` checked for non-ISR-safe FreeRTOS API calls
5. **Task hygiene** — `*_task` functions checked for `vTaskDelete(NULL)` before exit

### AgentMemory Design

The `AgentMemory` class uses a simple append-only list of `MemoryEntry` dataclasses. The `is_exhausted` property provides a clean loop-termination condition. The `best_code()` method implements a "return first PASS, or last attempt" strategy — ensuring the coordinator always has something useful to return even when the code never fully passes review.

---

## Roadmap

- [ ] **Real LLM integration** — ZhipuAI GLM-4 and Doubao backend swap-in
- [ ] **Extended MISRA-C checks** — Integrate `cppcheck` or `PC-lint` output parsing
- [ ] **CMake project scaffolding** — Auto-generate `CMakeLists.txt` and `sdkconfig` alongside source
- [ ] **Multi-file output** — Split header (`.h`) and implementation (`.c`) files
- [ ] **Streaming output** — Real-time token streaming for long code generation calls
- [ ] **Web UI** — FastAPI + React dashboard for task submission and code visualisation
- [ ] **CI/CD integration** — GitHub Actions workflow to auto-review PRs containing firmware changes
- [ ] **STM32CubeIDE project export** — Generate `.ioc` configuration files alongside code

---

## License

This project is released under the **MIT License**.

---

*Built with the Multi-Agent Autonomous Coding & Verification Framework — accelerating embedded systems development through Agentic Self-Correction loops, High-Frequency Token Consumption, and Deep Context Windows.*
