"""ZEUS coordinator prototype.

This package is deliberately isolated from the ATENA Flask application.
It has no network, model, database, or deployment side effects.
"""

from .hermes_research import HermesResearchAdapter

from .coordinator import (
    Coordinator,
    LedgerPersistenceUnavailable,
    SpecialistUnavailable,
    TaskRequest,
    TaskStatus,
)

__all__ = [
    "Coordinator",
    "LedgerPersistenceUnavailable",
    "SpecialistUnavailable",
    "TaskRequest",
    "TaskStatus",
    "HermesResearchAdapter",
]
