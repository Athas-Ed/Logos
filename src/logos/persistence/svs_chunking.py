"""KSFS 正文分块与 chunk_id（`KSFS开发.md` §5、§5.5）。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from ._hash import content_hash_hex

_TOKEN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]+")
_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def tokenize(text: str) -> list[str]:
    """§5.3：按词符切分。"""
    return _TOKEN.findall(text)


def normalize_for_substring_match(text: str) -> str:
    """§4.2 用途 B / §5.4：小写、去空白与常见标点 → `norm_text`。"""
    s = text.lower()
    skip = frozenset(
        ".,;:!?。，；：！？【】「」『』《》\"'\"()[]{}、…—_\\/-"
    )
    return "".join(ch for ch in s if not ch.isspace() and ch not in skip)


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """§5.2 建议字段（实现期钉死供 SVS / 调试）。"""

    rel_path: str
    chunk_index: int
    heading: str
    heading_level: int
    text: str
    norm_text: str
    tokens: int


def compute_chunk_id(*, entity_id: str, chunk_index: int, chunk_text: str) -> str:
    """§5.5：用途 A 哈希写入 payload，再 SHA-256 得稳定 ``chunk_id``。"""
    norm_chunk = content_hash_hex(chunk_text)
    payload = f"v1\n{entity_id}\n{chunk_index}\n{norm_chunk}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"ck_{digest}"


def _merge_small_chunks(chunks: list[str], *, min_chars: int) -> list[str]:
    if not chunks:
        return []
    out: list[str] = [chunks[0]]
    for piece in chunks[1:]:
        if len(piece) < min_chars and out:
            out[-1] = f"{out[-1]}\n\n{piece}".strip()
        else:
            out.append(piece)
    return out


def _split_oversized(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text] if text else []
    parts: list[str] = []
    i = 0
    while i < len(text):
        parts.append(text[i : i + max_chars])
        i += max_chars
    return parts


def chunk_markdown_body(
    body: str,
    *,
    min_chars: int = 120,
    max_chars: int = 1000,
) -> list[str]:
    """
    §5.1：对 **正文**（不含 front matter）分块。

    - 有 ATX 标题：标题至下一同级或更高级标题前为一节；过短节与上一节合并。
    - 无标题：空行分段后再合并；单段超过 ``max_chars`` 硬切。
    """
    raw = body.strip()
    if not raw:
        return []

    lines = raw.split("\n")
    has_heading = any(
        _ATX_HEADING.match(line.strip()) for line in lines if line.strip()
    )

    if has_heading:
        sections: list[str] = []
        buf: list[str] = []
        for line in lines:
            stripped = line.strip()
            m = _ATX_HEADING.match(stripped) if stripped else None
            if m:
                if buf:
                    sections.append("\n".join(buf).strip())
                buf = [line]
            else:
                buf.append(line)
        if buf:
            sections.append("\n".join(buf).strip())
        sections = [s for s in sections if s]
        return _merge_small_chunks(sections, min_chars=min_chars)

    paras = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
    pieces: list[str] = []
    for p in paras:
        pieces.extend(_split_oversized(p, max_chars=max_chars))
    merged: list[str] = []
    buf2 = ""
    for piece in pieces:
        if not buf2:
            buf2 = piece
            continue
        cand = f"{buf2}\n\n{piece}"
        if len(cand) <= max_chars and (len(buf2) < min_chars or len(piece) < min_chars):
            buf2 = cand
        else:
            merged.append(buf2)
            buf2 = piece
    if buf2:
        merged.append(buf2)
    out = _merge_small_chunks(merged, min_chars=min_chars)
    return [s for s in out if s]


def build_chunk_records(rel_path: str, body: str) -> list[ChunkRecord]:
    """由正文生成带 ``norm_text`` / ``tokens`` 的分块记录。"""
    texts = chunk_markdown_body(body)
    recs: list[ChunkRecord] = []
    for idx, text in enumerate(texts):
        nt = normalize_for_substring_match(text)
        toks = len(tokenize(text))
        heading = ""
        level = 0
        first = text.lstrip().split("\n", 1)[0].strip()
        m = _ATX_HEADING.match(first)
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()
        recs.append(
            ChunkRecord(
                rel_path=rel_path,
                chunk_index=idx,
                heading=heading,
                heading_level=level,
                text=text,
                norm_text=nt,
                tokens=toks,
            )
        )
    return recs
