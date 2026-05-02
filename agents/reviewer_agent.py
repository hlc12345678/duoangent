"""
reviewer_agent.py
=================
Role: Reviewer Agent
Responsibility:
    Performs a strict static analysis of the generated C/C++ source code.
    Issues checked:
        1. Memory leaks        — heap allocations without NULL-guard or matching free()
        2. RTOS task deadlocks — tasks that never yield / block indefinitely
        3. Buffer overflows    — fixed-size buffers used with unbounded writes
        4. Task hygiene        — task functions that can return without vTaskDelete()
        5. ISR safety          — ISR code calling non-ISR-safe FreeRTOS APIs

    Returns a structured ``ReviewResult`` with:
        - ``status``:   "PASS" | "FAIL"
        - ``issues``:   list of ``CodeIssue`` dicts
        - ``feedback``: human-readable summary for the Coder Agent

LLM backend
-----------
Real deployments should replace ``mock_zhipu_call`` with an authenticated
call to the ZhipuAI GLM-4 (or equivalent) API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CodeIssue:
    """A single issue found during code review."""
    severity: str        # "ERROR" | "WARNING" | "INFO"
    category: str        # e.g. "MEMORY_LEAK", "DEADLOCK", "BUFFER_OVERFLOW"
    line_hint: str       # Brief description of the offending line/pattern
    description: str     # Detailed explanation
    suggestion: str      # How to fix the issue


@dataclass
class ReviewResult:
    """Outcome of a single review pass."""
    status: str                          # "PASS" | "FAIL"
    issues: List[CodeIssue] = field(default_factory=list)
    feedback: str = ""                   # Consolidated text for the Coder Agent

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


# ---------------------------------------------------------------------------
# Mock LLM back-end
# ---------------------------------------------------------------------------

def mock_zhipu_call(system_prompt: str, user_message: str) -> str:
    """
    Simulate a ZhipuAI GLM-4 code-review API call.

    In production replace the body of this function with a real API call.
    The mock performs deterministic heuristic checks so that the multi-agent
    loop can exercise the full Coder ↔ Reviewer correction cycle.
    """
    # The actual analysis is performed by ReviewerAgent._heuristic_review.
    # The mock LLM simply echoes the code back so the agent can analyse it.
    return user_message


# ---------------------------------------------------------------------------
# Reviewer Agent
# ---------------------------------------------------------------------------

class ReviewerAgent:
    """
    Analyses C/C++ source code for correctness and safety issues.

    Parameters
    ----------
    llm_backend:
        Callable with signature ``(system_prompt: str, user_message: str) -> str``.
        Defaults to ``mock_zhipu_call``.
    strict_mode:
        When ``True``, any WARNING-level issue causes a FAIL verdict.
        When ``False`` (default), only ERROR-level issues cause FAIL.
    """

    SYSTEM_PROMPT = (
        "You are a Principal Embedded Software Safety Engineer.  "
        "Your sole task is to review C/C++ source code for RTOS-based embedded systems.  "
        "For each issue found, output a JSON array of objects with keys: "
        "severity (ERROR|WARNING|INFO), category, line_hint, description, suggestion.  "
        "Categories to check: MEMORY_LEAK, DEADLOCK, BUFFER_OVERFLOW, TASK_HYGIENE, "
        "ISR_SAFETY, UNINITIALISED_VAR, MISSING_ERROR_CHECK.  "
        "If the code passes all checks, output an empty JSON array: []."
    )

    # -- Heuristic patterns ------------------------------------------------
    # Each entry: (regex_pattern, severity, category, description, suggestion)
    _PATTERNS = [
        # Heap allocation without NULL check
        (
            r"\b(pvPortMalloc|malloc|calloc|realloc)\s*\(",
            r"if\s*\(\s*\w+\s*(?:==|!=)\s*NULL\s*\)",
            "ERROR",
            "MEMORY_LEAK",
            "Heap allocation without NULL guard",
            "Check the return value of every allocation; free on failure path.",
        ),
        # Missing vTaskDelete — task function with for(;;) that could exit
        (
            r"vTaskDelete\s*\(\s*NULL\s*\)",
            None,
            "WARNING",
            "TASK_HYGIENE",
            "Task function may exit without calling vTaskDelete(NULL)",
            "Ensure every FreeRTOS task calls vTaskDelete(NULL) before returning.",
        ),
        # ISR calling non-ISR-safe API
        (
            r"\bISRAM_ATTR\b|\bICACHE_RAM_ATTR\b",
            r"\b(xQueueSend|xSemaphoreGive|xSemaphoreTake|vTaskDelay)\b(?!FromISR)",
            "ERROR",
            "ISR_SAFETY",
            "Non-ISR-safe FreeRTOS API called from ISR context",
            "Use the *FromISR() variants inside ISR functions.",
        ),
        # Unbounded string operations
        (
            r"\b(strcpy|strcat|sprintf|gets)\s*\(",
            None,
            "ERROR",
            "BUFFER_OVERFLOW",
            "Unbounded string function that may cause buffer overflow",
            "Replace with safe alternatives: strncpy, strncat, snprintf, fgets.",
        ),
        # Infinite loop without any yield / delay
        (
            r"for\s*\(\s*;;\s*\)|while\s*\(\s*1\s*\)|while\s*\(\s*true\s*\)",
            r"vTaskDelay|vTaskDelayUntil|ulTaskNotifyTake|xQueueReceive|xSemaphoreTake",
            "ERROR",
            "DEADLOCK",
            "Infinite loop with no FreeRTOS yield/block call detected",
            "Add vTaskDelay() or a blocking FreeRTOS primitive inside the loop.",
        ),
        # Mutex/semaphore taken but not released on error path
        (
            r"xSemaphoreTake\s*\(",
            r"xSemaphoreGive\s*\(",
            "WARNING",
            "DEADLOCK",
            "Semaphore take without confirmed give on all exit paths",
            "Ensure xSemaphoreGive() is called on every exit path after a successful take.",
        ),
    ]

    def __init__(self, llm_backend=None, strict_mode: bool = False):
        self._llm = llm_backend or mock_zhipu_call
        self.strict_mode = strict_mode

    # ------------------------------------------------------------------
    def review(self, code: str) -> ReviewResult:
        """
        Review the supplied C/C++ source code.

        Parameters
        ----------
        code:
            Complete C/C++ source code string.

        Returns
        -------
        ReviewResult
            Contains status ("PASS"/"FAIL"), list of issues, and feedback text.
        """
        issues = self._heuristic_review(code)

        # Determine overall verdict
        has_errors   = any(i.severity == "ERROR"   for i in issues)
        has_warnings = any(i.severity == "WARNING" for i in issues)

        if has_errors or (self.strict_mode and has_warnings):
            status = "FAIL"
        else:
            status = "PASS"

        feedback = self._build_feedback(issues, status)
        return ReviewResult(status=status, issues=issues, feedback=feedback)

    # ------------------------------------------------------------------
    def _heuristic_review(self, code: str) -> List[CodeIssue]:
        """
        Apply deterministic heuristic checks to the code.

        These checks do NOT require a live LLM and cover the most
        critical embedded-systems defects.
        """
        issues: List[CodeIssue] = []

        # 1. Heap allocation without NULL check
        alloc_calls = list(re.finditer(
            r"\b(pvPortMalloc|malloc|calloc|realloc)\s*\(", code))
        for match in alloc_calls:
            # Grab the next 200 chars to see if there's a NULL check nearby
            context = code[match.start(): match.start() + 300]
            if not re.search(r"if\s*\(.*?==\s*NULL|if\s*\(.*?!=\s*NULL|if\s*\(!",
                              context, re.DOTALL):
                issues.append(CodeIssue(
                    severity="ERROR",
                    category="MEMORY_LEAK",
                    line_hint=match.group(0),
                    description=(
                        f"Heap allocation via '{match.group(1)}()' is not followed "
                        f"by a NULL-pointer guard.  If allocation fails, the pointer "
                        f"will be dereferenced, causing a crash or undefined behaviour."
                    ),
                    suggestion=(
                        "Add: if (ptr == NULL) { ESP_LOGE(TAG, \"alloc failed\"); "
                        "/* cleanup and */ return; }"
                    ),
                ))

        # 2. Infinite loop without yield / blocking call
        loop_matches = list(re.finditer(
            r"for\s*\(\s*;;\s*\)|while\s*\(\s*1\s*\)|while\s*\(\s*true\s*\)", code))
        for match in loop_matches:
            # Find matching brace block
            start = code.find("{", match.end())
            if start == -1:
                continue
            block = _extract_brace_block(code, start)
            if block and not re.search(
                r"vTaskDelay|vTaskDelayUntil|ulTaskNotifyTake|"
                r"xQueueReceive|xSemaphoreTake|portYIELD|taskYIELD|"
                r"xStreamBufferReceive|xStreamBufferSend|"
                r"uart_read_bytes|HAL_UART_Receive|osDelay",
                block
            ):
                issues.append(CodeIssue(
                    severity="ERROR",
                    category="DEADLOCK",
                    line_hint=match.group(0),
                    description=(
                        "Infinite task loop contains no FreeRTOS blocking/yield "
                        "primitive.  This will starve lower-priority tasks and may "
                        "trigger the watchdog timer."
                    ),
                    suggestion=(
                        "Insert vTaskDelay(pdMS_TO_TICKS(N)) or a blocking queue/semaphore "
                        "call inside the loop."
                    ),
                ))

        # 3. Unbounded string functions
        unsafe_str = list(re.finditer(r"\b(strcpy|strcat|sprintf|gets)\s*\(", code))
        for match in unsafe_str:
            issues.append(CodeIssue(
                severity="ERROR",
                category="BUFFER_OVERFLOW",
                line_hint=match.group(0),
                description=(
                    f"'{match.group(1)}()' does not perform bounds checking and can "
                    f"write past the end of the destination buffer, causing stack or "
                    f"heap corruption."
                ),
                suggestion=(
                    f"Replace with: "
                    f"{'strncpy' if match.group(1)=='strcpy' else 'strncat' if match.group(1)=='strcat' else 'snprintf' if match.group(1)=='sprintf' else 'fgets'}()"
                ),
            ))

        # 4. ISR safety — non-ISR-safe calls inside ISR-marked functions.
        # Match only the specific function decorated with IRAM_ATTR/ICACHE_RAM_ATTR
        # by restricting the prefix match to a single logical source line
        # (i.e. no newline allowed between the attribute and the function name).
        isr_func_pattern = re.compile(
            r"(IRAM_ATTR|ICACHE_RAM_ATTR)[^\n]*void\s+(\w+)\s*\([^)]*\)\s*\n?\{"
        )
        for isr_match in isr_func_pattern.finditer(code):
            func_start = code.find("{", isr_match.end() - 1)
            if func_start == -1:
                continue
            func_body = _extract_brace_block(code, func_start)
            if func_body:
                unsafe = re.findall(
                    r"\b(xQueueSend|xSemaphoreGive|xSemaphoreTake|vTaskDelay)"
                    r"(?!FromISR)\s*\(", func_body)
                for fn in unsafe:
                    issues.append(CodeIssue(
                        severity="ERROR",
                        category="ISR_SAFETY",
                        line_hint=fn + "()",
                        description=(
                            f"'{fn}()' is NOT safe to call from an ISR context.  "
                            f"Calling it from an ISR can corrupt the FreeRTOS kernel state."
                        ),
                        suggestion=f"Use '{fn}FromISR()' with a BaseType_t pxHigherPriorityTaskWoken parameter.",
                    ))

        # 5. Task function that may return without vTaskDelete
        task_func_pattern = re.compile(
            r"static\s+void\s+(\w+_task|task_\w+)\s*\(\s*void\s*\*[^)]*\)\s*\{",
            re.IGNORECASE
        )
        for task_match in task_func_pattern.finditer(code):
            func_start = code.find("{", task_match.end() - 1)
            if func_start == -1:
                continue
            func_body = _extract_brace_block(code, func_start)
            if func_body and "vTaskDelete" not in func_body:
                issues.append(CodeIssue(
                    severity="WARNING",
                    category="TASK_HYGIENE",
                    line_hint=task_match.group(0)[:60],
                    description=(
                        f"Task '{task_match.group(1)}' does not call vTaskDelete(NULL).  "
                        f"If the task function returns, FreeRTOS behaviour is undefined."
                    ),
                    suggestion="Add vTaskDelete(NULL) at the end of the task function (before the closing brace).",
                ))

        return issues

    # ------------------------------------------------------------------
    @staticmethod
    def _build_feedback(issues: List[CodeIssue], status: str) -> str:
        """Format issues into a readable feedback string for the Coder Agent."""
        if not issues:
            return "✅ PASS — No issues found.  The code meets all quality standards."

        lines = [
            f"{'✅ PASS' if status == 'PASS' else '❌ FAIL'} — "
            f"{len(issues)} issue(s) found:\n"
        ]
        for idx, issue in enumerate(issues, start=1):
            lines.append(
                f"[{idx}] [{issue.severity}] {issue.category}\n"
                f"    Pattern : {issue.line_hint}\n"
                f"    Problem : {issue.description}\n"
                f"    Fix     : {issue.suggestion}\n"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper — extract brace-balanced block
# ---------------------------------------------------------------------------

def _extract_brace_block(code: str, open_brace_pos: int) -> Optional[str]:
    """
    Return the content between the opening ``{`` at ``open_brace_pos`` and
    its matching closing ``}``, or ``None`` if the braces are unbalanced.
    """
    if open_brace_pos >= len(code) or code[open_brace_pos] != "{":
        return None

    depth = 0
    for i in range(open_brace_pos, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[open_brace_pos + 1: i]
    return None
