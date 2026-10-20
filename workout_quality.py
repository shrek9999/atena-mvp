"""Deterministic validation helpers for structured ATENA workout plans.

These helpers are intentionally separate from free-form model output. They can
be wired into a structured workout schema in a later change; they do not yet
validate or modify conversational replies.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class WorkoutBlock:
    """A workout block whose duration is explicitly specified in seconds."""
    name: str
    duration_seconds: int


def total_duration_seconds(blocks: Iterable[WorkoutBlock]) -> int:
    """Sum declared block durations, rejecting invalid durations."""
    total = 0
    found = False
    for block in blocks:
        found = True
        if not block.name.strip():
            raise ValueError("Each workout block must have a name.")
        if isinstance(block.duration_seconds, bool) or not isinstance(block.duration_seconds, int):
            raise ValueError("Block duration must be an integer number of seconds.")
        if block.duration_seconds <= 0:
            raise ValueError("Block duration must be greater than zero.")
        total += block.duration_seconds
    if not found:
        raise ValueError("A workout must contain at least one timed block.")
    return total


def duration_matches(blocks: Iterable[WorkoutBlock], advertised_minutes: int) -> bool:
    """Return true only when declared durations equal the advertised duration exactly."""
    if isinstance(advertised_minutes, bool) or not isinstance(advertised_minutes, int) or advertised_minutes <= 0:
        raise ValueError("Advertised duration must be a positive integer number of minutes.")
    return total_duration_seconds(blocks) == advertised_minutes * 60
