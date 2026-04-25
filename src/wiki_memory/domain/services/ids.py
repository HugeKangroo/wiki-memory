from __future__ import annotations

import hashlib
import re
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


def stable_id(prefix: str, identity_key: str) -> str:
    digest = hashlib.sha1(identity_key.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"
