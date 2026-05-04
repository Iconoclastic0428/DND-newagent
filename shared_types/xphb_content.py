from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class XphbContentEntry:
    content_id: str
    display_name: str
    source_id: str
    category: str
    implementation_path: str
    runtime_status: str
    test_status: str
    blocker_status: str
    option_coverage_status: str
    level: int | None = None
    class_id: str | None = None


@dataclass(frozen=True)
class XphbManifest:
    source: str
    count: int
    entries: tuple[XphbContentEntry, ...]
