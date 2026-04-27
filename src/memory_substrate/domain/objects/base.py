from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BaseObject:
    id: str
    created_at: str
    updated_at: str
