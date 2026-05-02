"""
multi_agent_coordinator.py
===========================
Main entry point for the Multi-Agent Autonomous Coding & Verification
Framework for Embedded Systems.

Orchestration workflow
----------------------

    User (NL request)
         │
         ▼
    PlannerAgent  ──► HardwareSpec (JSON)
         │
         ▼
    CoderAgent    ──► C/C++ source code  ◄──────────────────────┐
         │                                                        │
         ▼                                                        │
    ReviewerAgent ──► ReviewResult                               │
         │                                                        │
         ├── PASS ──► Final Output                               │
         │                                                        │
         └── FAIL ──► (iterations_remaining > 0) ───────────────┘
                      Feedback → CoderAgent (fix & regenerate)

The loop is bounded by ``AgentMemory.max_iterations`` (default: 3).

Usage
-----
    # Interactive mode (prompts for input):
    python multi_agent_coordinator.py

    # Non-interactive / scripted mode:
    python multi_agent_coordinator.py --task "Setup an I2C task for an OLED display"

    # With custom iteration limit:
    python multi_agent_coordinator.py --task "..." --max-iterations 2

    # Save generated code to a file:
    python multi_agent_coordinator.py --task "..." --output my_task.c
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from typing import Optional

from agent_memory import AgentMemory
from agents import CoderAgent, PlannerAgent, ReviewerAgent


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BLUE   = "\033[34m"


def _banner(text: str, colour: str = CYAN) -> None:
    width = 72
    print(f"\n{colour}{BOLD}{'─' * width}{RESET}")
    print(f"{colour}{BOLD}  {text}{RESET}")
    print(f"{colour}{BOLD}{'─' * width}{RESET}\n")


def _section(label: str, colour: str = BLUE) -> None:
    print(f"\n{colour}{BOLD}▶ {label}{RESET}")


def _success(msg: str) -> None:
    print(f"{GREEN}{BOLD}✅  {msg}{RESET}")


def _failure(msg: str) -> None:
    print(f"{RED}{BOLD}❌  {msg}{RESET}")


def _info(msg: str) -> None:
    print(f"{YELLOW}ℹ  {msg}{RESET}")


def _print_spec(spec: dict) -> None:
    """Pretty-print the hardware spec."""
    print(json.dumps(spec, indent=2))


def _print_code(code: str, max_lines: int = 60) -> None:
    """Print code with a line limit indicator."""
    lines = code.splitlines()
    if len(lines) > max_lines:
        print("\n".join(lines[:max_lines]))
        print(f"\n{YELLOW}... [{len(lines) - max_lines} more lines truncated for display] ...{RESET}\n")
    else:
        print(code)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class MultiAgentCoordinator:
    """
    Orchestrates the full Planner → Coder ↔ Reviewer pipeline.

    Parameters
    ----------
    max_iterations:
        Maximum Coder ↔ Reviewer loop iterations (default: 3).
    strict_review:
        When ``True``, warnings also cause a FAIL verdict.
    verbose:
        When ``True``, print detailed step output.
    """

    def __init__(
        self,
        max_iterations: int = 3,
        strict_review: bool = False,
        verbose: bool = True,
    ) -> None:
        self.max_iterations = max_iterations
        self.verbose = verbose

        self._planner  = PlannerAgent()
        self._coder    = CoderAgent()
        self._reviewer = ReviewerAgent(strict_mode=strict_review)

    # ------------------------------------------------------------------
    def run(self, user_request: str) -> dict:
        """
        Execute the complete multi-agent pipeline for a given user request.

        Parameters
        ----------
        user_request:
            Free-form natural-language task description.

        Returns
        -------
        dict with keys:
            - ``request``   : original user request
            - ``spec``      : HardwareSpec from Planner
            - ``final_code``: best C/C++ code produced
            - ``status``    : "PASS" | "FAIL" | "BEST_EFFORT"
            - ``iterations``: number of Coder ↔ Reviewer cycles
            - ``history``   : list of iteration records
        """
        memory = AgentMemory(
            task_description=user_request,
            max_iterations=self.max_iterations,
        )

        # ── Step 1: Planning ───────────────────────────────────────────────
        if self.verbose:
            _banner("STEP 1 — PLANNER AGENT", CYAN)
            _info(f"Request: {user_request}")

        try:
            spec = self._planner.plan(user_request)
            memory.spec = spec
        except ValueError as exc:
            _failure(f"PlannerAgent failed: {exc}")
            return {"request": user_request, "spec": None,
                    "final_code": None, "status": "FAIL",
                    "iterations": 0, "history": []}

        if self.verbose:
            _section("Hardware Specification")
            _print_spec(spec)

        # ── Steps 2–N: Coder ↔ Reviewer loop ──────────────────────────────
        final_status = "FAIL"
        last_feedback: Optional[str] = None

        while not memory.is_exhausted:
            iteration_num = memory.current_iteration + 1

            # ── Coder ─────────────────────────────────────────────────────
            if self.verbose:
                _banner(
                    f"STEP 2 — CODER AGENT  (iteration {iteration_num} / {self.max_iterations})",
                    BLUE,
                )
                if last_feedback:
                    _info("Regenerating code with reviewer feedback applied…")

            code = self._coder.generate(spec, previous_feedback=last_feedback)

            if self.verbose:
                _section("Generated C/C++ Code")
                _print_code(code)

            # ── Reviewer ──────────────────────────────────────────────────
            if self.verbose:
                _banner(
                    f"STEP 3 — REVIEWER AGENT  (iteration {iteration_num} / {self.max_iterations})",
                    YELLOW if iteration_num == 1 else RED,
                )

            result = self._reviewer.review(code)

            if self.verbose:
                _section("Review Result")
                print(result.feedback)

            # Record this iteration
            memory.record_iteration(
                code=code,
                review_status=result.status,
                review_feedback=result.feedback,
            )

            if result.passed:
                final_status = "PASS"
                if self.verbose:
                    _success(
                        f"Code PASSED review on iteration {iteration_num}."
                    )
                break
            else:
                last_feedback = result.feedback
                if self.verbose:
                    _failure(
                        f"Code FAILED review on iteration {iteration_num}.  "
                        f"{'Re-trying…' if not memory.is_exhausted else 'Max iterations reached.'}"
                    )

        # If we exhausted iterations without a pass
        if final_status != "PASS":
            final_status = "BEST_EFFORT"

        best_code = memory.best_code()

        # ── Final output ───────────────────────────────────────────────────
        if self.verbose:
            _banner("FINAL OUTPUT", GREEN if final_status == "PASS" else YELLOW)
            _section("Session Summary")
            print(memory.summary())
            _section("Final Code")
            _print_code(best_code or "")
            if final_status == "PASS":
                _success("Pipeline completed successfully — code passed all review checks.")
            else:
                _info(
                    f"Pipeline completed with status '{final_status}' after "
                    f"{memory.current_iteration} iteration(s).  "
                    f"The best-effort code is returned; manual review is recommended."
                )

        return {
            "request":    user_request,
            "spec":       spec,
            "final_code": best_code,
            "status":     final_status,
            "iterations": memory.current_iteration,
            "history":    memory.export_history(),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="multi_agent_coordinator",
        description=textwrap.dedent("""\
            Multi-Agent Autonomous Coding & Verification Framework
            for Embedded Systems (ESP32 / STM32 + FreeRTOS)
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Example tasks:
              "Setup an I2C task for an OLED display with FreeRTOS"
              "Create a SPI DMA transfer task for ESP32"
              "Implement a UART echo task on STM32 with FreeRTOS"
              "Blink an LED on GPIO2 every 500ms"
              "Read ADC sensor data with moving average filter"
        """),
    )
    parser.add_argument(
        "--task", "-t",
        type=str,
        default=None,
        help="Natural-language task description (interactive prompt if omitted).",
    )
    parser.add_argument(
        "--max-iterations", "-n",
        type=int,
        default=3,
        dest="max_iterations",
        help="Maximum Coder ↔ Reviewer loop iterations (default: 3).",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="File path to save the final generated C/C++ code.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Enable strict review mode (warnings also cause FAIL).",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress verbose output (only print final code).",
    )
    parser.add_argument(
        "--export-history",
        type=str,
        default=None,
        dest="export_history",
        help="File path to export the full iteration history as JSON.",
    )
    return parser.parse_args()


def _interactive_prompt() -> str:
    """Prompt the user for a task description."""
    _banner("Multi-Agent Autonomous Coding & Verification Framework", CYAN)
    print("Welcome!  Describe the embedded task you want to generate code for.\n")
    print("Examples:")
    examples = [
        "Setup an I2C task for an OLED display with FreeRTOS",
        "Create a SPI DMA transfer task for ESP32",
        "Implement a UART echo task on STM32",
        "Blink an LED on GPIO2 every 500ms",
        "Read ADC sensor data with a moving average filter",
    ]
    for i, ex in enumerate(examples, start=1):
        print(f"  {i}. {ex}")

    print()
    try:
        task = input("Enter your task (or a number 1-5 for an example): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNo input received.  Using default task.")
        return examples[0]

    if task.isdigit() and 1 <= int(task) <= len(examples):
        return examples[int(task) - 1]
    return task or examples[0]


def main() -> int:
    args = _parse_args()

    task = args.task or _interactive_prompt()
    if not task:
        print("Error: No task provided.", file=sys.stderr)
        return 1

    coordinator = MultiAgentCoordinator(
        max_iterations=args.max_iterations,
        strict_review=args.strict,
        verbose=not args.quiet,
    )

    result = coordinator.run(task)

    # Save generated code if requested
    if args.output and result["final_code"]:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(result["final_code"])
            print(f"\n{GREEN}Code saved to: {args.output}{RESET}")
        except OSError as exc:
            print(f"\n{RED}Failed to save code: {exc}{RESET}", file=sys.stderr)

    # Export history if requested
    if args.export_history and result["history"]:
        try:
            with open(args.export_history, "w", encoding="utf-8") as fh:
                json.dump(result["history"], fh, indent=2)
            print(f"{GREEN}History exported to: {args.export_history}{RESET}")
        except OSError as exc:
            print(f"{RED}Failed to export history: {exc}{RESET}", file=sys.stderr)

    # In quiet mode, just print the code
    if args.quiet and result["final_code"]:
        print(result["final_code"])

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
