"""Deterministic content hashing for incremental HDL sync."""

from __future__ import annotations

import hashlib


def normalize_text_for_storage(text: str) -> str:
    """Normalize newlines to LF (LKC canonical form)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def content_hash_hex(text: str) -> str:
    """SHA-256 over UTF-8 of normalized text (matches bytes written to LKC)."""
    normalized = normalize_text_for_storage(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
