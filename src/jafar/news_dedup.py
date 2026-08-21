from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NewsFingerprint:
    key: str


def fingerprint(title: str, source_url: str) -> NewsFingerprint:
    normalized_title = re.sub(r"\s+", " ", title.casefold()).strip()
    normalized_url = source_url.strip().rstrip("/")
    digest = hashlib.sha256(f"{normalized_title}|{normalized_url}".encode("utf-8")).hexdigest()
    return NewsFingerprint(digest)


class SeenNews:
    def __init__(self) -> None:
        self._keys: set[str] = set()

    def add_if_new(self, item: NewsFingerprint) -> bool:
        if item.key in self._keys:
            return False
        self._keys.add(item.key)
        return True
