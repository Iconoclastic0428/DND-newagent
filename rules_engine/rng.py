from __future__ import annotations

import hashlib
import random


def seeded_random(seed: str, counter: int) -> random.Random:
    material = f"{seed}:{counter}".encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return random.Random(int(digest, 16))
