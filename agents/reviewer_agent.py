from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


PASS_STATUS = "Pass"
FAIL_STATUS = "Fail with feedback"


@dataclass(frozen=True)
class ReviewResult:
    status: str
    feedback: List[str]

    @property
    def passed(self) -> bool:
        return self.status == PASS_STATUS


def _detect_memory_leaks(code: str) -> List[str]:
    issues = []
    if re.search(r"\bmalloc\s*\(", code) and not re.search(r"\bfree\s*\(", code):
        issues.append(
            "Heuristic warning: malloc used without matching free; verify ownership."
        )
    if re.search(r"\bnew\b", code) and not re.search(r"\bdelete\b", code):
        issues.append("Potential memory leak: new used without matching delete.")
    return issues


def _detect_deadlocks(code: str) -> List[str]:
    issues = []
    if "portMAX_DELAY" in code:
        issues.append("Potential RTOS deadlock risk: blocking call uses portMAX_DELAY.")
    if re.search(r"xSemaphoreTake\([^,]+,\s*0[Uu]?\)", code):
        issues.append(
            "Heuristic warning: semaphore take uses a literal zero timeout."
        )
    return issues


def _detect_buffer_overflows(code: str) -> List[str]:
    issues = []
    if re.search(r"\bstrcpy\s*\(", code):
        issues.append("Potential buffer overflow: strcpy used without bounds checking.")
    if re.search(r"\bsprintf\s*\(", code):
        issues.append("Potential buffer overflow: sprintf used without bounds checking.")
    return issues


def review_code(code: str) -> ReviewResult:
    feedback: List[str] = []
    feedback.extend(_detect_memory_leaks(code))
    feedback.extend(_detect_deadlocks(code))
    feedback.extend(_detect_buffer_overflows(code))

    status = PASS_STATUS if not feedback else FAIL_STATUS
    return ReviewResult(status=status, feedback=feedback)
