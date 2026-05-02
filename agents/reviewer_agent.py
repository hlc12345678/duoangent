from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List


@dataclass(frozen=True)
class ReviewResult:
    status: str
    feedback: List[str]

    @property
    def passed(self) -> bool:
        return self.status == "Pass"


def _detect_memory_leaks(code: str) -> List[str]:
    issues = []
    if re.search(r"\bmalloc\s*\(", code) and not re.search(r"\bfree\s*\(", code):
        issues.append("Potential memory leak: malloc used without matching free.")
    if re.search(r"\bnew\b", code) and not re.search(r"\bdelete\b", code):
        issues.append("Potential memory leak: new used without matching delete.")
    return issues


def _detect_deadlocks(code: str) -> List[str]:
    issues = []
    if "portMAX_DELAY" in code:
        issues.append("Potential RTOS deadlock risk: blocking call uses portMAX_DELAY.")
    if re.search(r"xSemaphoreTake\([^,]+,\s*0\)", code):
        issues.append("Potential starvation risk: semaphore take with zero timeout.")
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

    status = "Pass" if not feedback else "Fail with feedback"
    return ReviewResult(status=status, feedback=feedback)
