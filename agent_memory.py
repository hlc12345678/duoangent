"""
agent_memory.py
===============
Manages the shared conversation history and iterative context between the
Coder Agent and the Reviewer Agent.

Design
------
The memory module is intentionally lightweight: it stores a list of
``MemoryEntry`` objects (each capturing one complete Code → Review cycle)
and enforces a configurable maximum iteration count.

Key constraints
---------------
- Maximum **3** Code ↔ Review iterations per session (configurable via
  ``max_iterations``).
- Once the limit is reached, the last generated code is returned as the
  "best effort" output regardless of review status.
- The full history is preserved in memory so the Coordinator can export it
  for audit purposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

HardwareSpec = Dict[str, Any]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """A single Code → Review iteration record."""
    iteration: int
    code: str
    review_status: str          # "PASS" | "FAIL" | "PENDING"
    review_feedback: str        # Human-readable feedback from ReviewerAgent
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "iteration":       self.iteration,
            "review_status":   self.review_status,
            "review_feedback": self.review_feedback,
            "timestamp":       self.timestamp,
            # Truncate code in the dict for readability; full code kept in object
            "code_preview":    self.code[:120] + "..." if len(self.code) > 120 else self.code,
        }


# ---------------------------------------------------------------------------
# AgentMemory
# ---------------------------------------------------------------------------

class AgentMemory:
    """
    Manages shared context and iteration control for the Coder ↔ Reviewer loop.

    Parameters
    ----------
    max_iterations:
        Maximum number of Code → Review cycles allowed.  Defaults to 3.
    task_description:
        The original natural-language request from the user.
    spec:
        The ``HardwareSpec`` produced by the Planner Agent.
    """

    def __init__(
        self,
        task_description: str = "",
        spec: Optional[HardwareSpec] = None,
        max_iterations: int = 3,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1.")
        self.task_description: str = task_description
        self.spec: Optional[HardwareSpec] = spec
        self.max_iterations: int = max_iterations

        self._history: List[MemoryEntry] = []
        self._current_iteration: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_iteration(self) -> int:
        """Current loop count (0-indexed)."""
        return self._current_iteration

    @property
    def iterations_remaining(self) -> int:
        """How many more Code → Review cycles are allowed."""
        return self.max_iterations - self._current_iteration

    @property
    def is_exhausted(self) -> bool:
        """``True`` when the maximum iteration count has been reached."""
        return self._current_iteration >= self.max_iterations

    @property
    def history(self) -> List[MemoryEntry]:
        """Read-only view of the full iteration history."""
        return list(self._history)

    @property
    def last_entry(self) -> Optional[MemoryEntry]:
        """The most recent ``MemoryEntry``, or ``None`` if history is empty."""
        return self._history[-1] if self._history else None

    @property
    def last_feedback(self) -> Optional[str]:
        """Feedback text from the most recent review, or ``None``."""
        entry = self.last_entry
        return entry.review_feedback if entry else None

    @property
    def last_code(self) -> Optional[str]:
        """Source code from the most recent iteration, or ``None``."""
        entry = self.last_entry
        return entry.code if entry else None

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def record_iteration(
        self,
        code: str,
        review_status: str,
        review_feedback: str,
    ) -> MemoryEntry:
        """
        Record the outcome of one Code → Review cycle.

        Parameters
        ----------
        code:
            The C/C++ source code that was generated in this iteration.
        review_status:
            ``"PASS"`` or ``"FAIL"``.
        review_feedback:
            Human-readable feedback from the Reviewer Agent.

        Returns
        -------
        MemoryEntry
            The newly created history entry.

        Raises
        ------
        RuntimeError
            If called after the maximum iteration count has been reached.
        """
        if self.is_exhausted:
            raise RuntimeError(
                f"AgentMemory: Maximum iteration count ({self.max_iterations}) "
                f"has been reached.  No further iterations are allowed."
            )

        self._current_iteration += 1
        entry = MemoryEntry(
            iteration=self._current_iteration,
            code=code,
            review_status=review_status,
            review_feedback=review_feedback,
        )
        self._history.append(entry)
        return entry

    def reset(self) -> None:
        """
        Clear all history and reset the iteration counter.

        Useful for running a new task without creating a new ``AgentMemory``
        instance.
        """
        self._history.clear()
        self._current_iteration = 0

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def best_code(self) -> Optional[str]:
        """
        Return the source code from the first ``PASS`` iteration, or — if no
        iteration passed — the code from the final iteration.
        """
        for entry in self._history:
            if entry.review_status == "PASS":
                return entry.code
        return self._history[-1].code if self._history else None

    def summary(self) -> str:
        """Return a compact human-readable summary of the session."""
        if not self._history:
            return "AgentMemory: No iterations recorded yet."

        lines = [
            f"AgentMemory Summary",
            f"  Task       : {self.task_description or '(not set)'}",
            f"  Iterations : {self._current_iteration} / {self.max_iterations}",
        ]
        for entry in self._history:
            lines.append(
                f"  [{entry.iteration}] {entry.review_status:4s}  "
                f"@ {entry.timestamp}  |  "
                f"{entry.review_feedback.splitlines()[0][:80]}"
            )
        return "\n".join(lines)

    def export_history(self) -> List[dict]:
        """Export the full history as a list of plain dicts (JSON-serialisable)."""
        return [e.to_dict() for e in self._history]
