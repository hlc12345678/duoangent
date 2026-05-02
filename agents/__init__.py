"""
Multi-Agent Autonomous Coding & Verification Framework for Embedded Systems.

agents/ package — exposes the three core agent roles:
  - PlannerAgent : natural-language → structured hardware spec
  - CoderAgent   : hardware spec → C/C++ source code
  - ReviewerAgent: C/C++ source code → Pass / Fail + feedback
"""

from .planner_agent import PlannerAgent
from .coder_agent import CoderAgent
from .reviewer_agent import ReviewerAgent

__all__ = ["PlannerAgent", "CoderAgent", "ReviewerAgent"]
