from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from agents.reviewer_agent import ReviewResult


@dataclass
class IterationRecord:
    iteration: int
    code_snapshot: str
    review: Optional[ReviewResult] = None


@dataclass
class AgentMemory:
    max_iterations: int = 3
    history: List[IterationRecord] = field(default_factory=list)
    termination_reason: Optional[str] = None

    def add_iteration(self, code_snapshot: str, review: ReviewResult) -> None:
        record = IterationRecord(
            iteration=len(self.history) + 1,
            code_snapshot=code_snapshot,
            review=review,
        )
        self.history.append(record)

    @property
    def can_iterate(self) -> bool:
        return len(self.history) < self.max_iterations

    @property
    def last_feedback(self) -> List[str]:
        if not self.history:
            return []
        review = self.history[-1].review
        return review.feedback if review else []
