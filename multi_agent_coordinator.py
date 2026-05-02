from __future__ import annotations

import argparse
from typing import Tuple

from agent_memory import AgentMemory
from agents.coder_agent import generate_code, revise_code
from agents.planner_agent import HardwareSpec, plan_hardware
from agents.reviewer_agent import ReviewResult, review_code


def run_workflow(user_request: str) -> Tuple[HardwareSpec, str, AgentMemory]:
    spec = plan_hardware(user_request)
    memory = AgentMemory()

    code = generate_code(spec)
    while True:
        review = review_code(code)
        memory.add_iteration(code, review)

        if review.passed or not memory.can_iterate:
            break

        code = revise_code(spec, code, memory.last_feedback)

    return spec, code, memory


def _format_review(review: ReviewResult) -> str:
    if review.passed:
        return "Pass"
    feedback_lines = "\n".join(f"- {item}" for item in review.feedback)
    return f"Fail with feedback:\n{feedback_lines}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Agent Autonomous Coding & Verification Framework"
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="Setup an I2C task for an OLED display with FreeRTOS",
        help="Natural language firmware request.",
    )
    args = parser.parse_args()

    spec, code, memory = run_workflow(args.request)

    print("=== Planner Output ===")
    print(spec.summary)
    print(f"Target MCU: {spec.target_mcu}")
    print(f"Pins: {spec.pins}")
    print(f"RTOS Tasks: {spec.rtos_tasks}")
    print(f"Memory Budget (KB): {spec.memory_kb}")
    print(f"Interfaces: {spec.interfaces}")
    print(f"Assumptions: {spec.assumptions}")

    print("\n=== Coder Output ===")
    print(code)

    print("\n=== Reviewer Output ===")
    if memory.history:
        print(_format_review(memory.history[-1].review))
        print(f"Iterations: {len(memory.history)} / {memory.max_iterations}")


if __name__ == "__main__":
    main()
