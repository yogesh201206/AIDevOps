"""
Local storage for investigation history.

Provides in-memory and local disk persistence suitable for development in Phase 3.
Designed with clean interface abstraction so it can be swapped for PostgreSQL/SQLite
in future phases without altering domain logic.
"""

import json
import logging
import os
from threading import Lock
from typing import Dict, List, Optional

from app.services.investigation.schemas import InvestigationListItem, InvestigationResponse

logger = logging.getLogger(__name__)


class InvestigationStorage:
    """Thread-safe storage repository for completed investigations."""

    _instance: Optional["InvestigationStorage"] = None
    _lock = Lock()

    def __init__(self, persistence_file: Optional[str] = None):
        self._items: Dict[str, InvestigationResponse] = {}
        self._persistence_file = persistence_file
        self._load_from_disk()

    @classmethod
    def get_instance(cls) -> "InvestigationStorage":
        """Singleton accessor to ensure shared investigation state."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _load_from_disk(self) -> None:
        """Attempt to restore previous session history if file exists."""
        if not self._persistence_file or not os.path.exists(self._persistence_file):
            return
        try:
            with open(self._persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item_dict in data:
                    inv = InvestigationResponse.model_validate(item_dict)
                    self._items[inv.investigation_id] = inv
            logger.info("Restored %d investigations from local history file.", len(self._items))
        except Exception as exc:
            logger.warning("Could not load investigation history from %s: %s", self._persistence_file, exc)

    def _save_to_disk(self) -> None:
        """Persist items to disk if path is set."""
        if not self._persistence_file:
            return
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                serializable = [item.model_dump() for item in self._items.values()]
                json.dump(serializable, f, indent=2)
        except Exception as exc:
            logger.warning("Failed to persist investigation history: %s", exc)

    def save(self, investigation: InvestigationResponse) -> None:
        """Save or update an investigation record."""
        with self._lock:
            self._items[investigation.investigation_id] = investigation
            self._save_to_disk()

    def get(self, investigation_id: str) -> Optional[InvestigationResponse]:
        """Retrieve an investigation by ID."""
        with self._lock:
            return self._items.get(investigation_id)

    def list(
        self,
        repository: Optional[str] = None,
        limit: int = 50,
    ) -> List[InvestigationListItem]:
        """
        List investigations sorted newest first, optionally filtered by repository.
        """
        with self._lock:
            records = list(self._items.values())

        if repository:
            records = [r for r in records if r.repository.lower() == repository.lower()]

        # Sort newest first (by created_at ISO string)
        records.sort(key=lambda x: x.created_at, reverse=True)
        sliced = records[:limit]

        return [
            InvestigationListItem(
                investigation_id=r.investigation_id,
                repository=r.repository,
                workflow_run_id=r.workflow_run_id,
                workflow_name=r.workflow_name,
                status=r.status,
                summary=r.summary,
                severity=r.severity,
                confidence=r.confidence,
                model=r.model,
                provider=r.provider,
                created_at=r.created_at,
            )
            for r in sliced
        ]

    def clear(self) -> None:
        """Clear all stored investigations (useful for test resets)."""
        with self._lock:
            self._items.clear()
            self._save_to_disk()
