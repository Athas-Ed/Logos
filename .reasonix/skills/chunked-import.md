---
name: chunked-import
description: Split large content into chunks (~2500 words), process sequentially with overlap, structured splitting, and optional two-phase summary-first mode. Avoids content fragmentation.
---

# chunked-import

Automatically split large content into ~2500-word chunks and process them sequentially, with strategies to avoid content fragmentation.

## When to use

When you need to pass a large block of text (e.g., body for `install_skill`, content for `write_file`) and a previous attempt failed with a JSON parse error or LLM output corruption due to content being too large.

## Detection

If `len(content.split()) > 2500`, trigger chunking. Otherwise pass through as-is.

## Layered strategy to avoid fragmentation

### Step 1 — Structured chunking (primary)

Before falling back to word-count splitting, try to identify **natural boundaries** in the content:

| Content type | Split by | Example |
|---|---|---|
| Markdown | `##` or `###` headings | Each section as one chunk |
| Numbered rules | Every 5-7 list items | Chunk each rule group |
| Skill body | Semantic paragraphs (separated by blank lines) | Each logical segment as one chunk |
| Plain prose | Sentence breaks (。.!?） | Prefer paragraph → sentence over arbitrary word-cut |

Aim: **each chunk is a self-contained semantic unit.** This alone prevents most fragmentation.

### Step 2 — Overlapping context

When processing chunk N, **append the last 3-5 sentences of chunk N-1** as leading context. This gives the LLM the conversational/semantic bridge:

```
Chunk 1: [first 2500 words]
  → result R1

Chunk 2: [last 3 sentences of chunk 1 + next 2500 words]
  → result R2 (builds on R1's tail)

Chunk 3: [last 3 sentences of chunk 2 + next 2500 words]
  → result R3
```

### Step 3 — Two-phase mode (for highly interconnected content) ⚡

If the content requires **global understanding** (e.g., a skill body with 10 interdependent rules where rule 3 references rule 8):

**Phase 1 — Summarize**: Feed each chunk to the LLM independently and ask for a concise summary of its key points.

**Phase 2 — Execute**: Feed all summaries + the current chunk's full text together. The summaries provide global context; the full text provides local precision.

```
Phase 1: S1 = summarize(chunk1), S2 = summarize(chunk2), S3 = summarize(chunk3)
Phase 2: process([S1+S2+S3, chunk1]) → process([S1+S2+S3, chunk2]) → process([S1+S2+S3, chunk3])
```

Cost: one extra LLM round per chunk. Use only when the content is highly cross-referential.

## Decision flow

```
Receive large content
    │
    ├── ≤ 2500 words? → process directly, done
    │
    └── > 2500 words?
            │
            ├── Can detect natural structure (headings / numbered list / paragraphs)?
            │       ├── Yes → split on structured boundaries (Step 1)
            │       └── No  → split on sentence/paragraph breaks at ~2500 words
            │
            ├── Content highly cross-referential (rules reference each other)?
            │       ├── Yes → use **two-phase mode** (Step 3)
            │       └── No  → use **overlapping context** (Step 2)
            │
            └── Process each chunk sequentially, retry failed chunk up to 2 times
                Report progress: "Chunk 3/5..."
```

## Error recovery

- Each chunk: retry up to **2 times** on failure.
- If a chunk fails after 2 retries, **report which chunk number and the error message**, stop processing.
- Previously succeeded chunks are not discarded.

## Notes

- Word count: `len(text.split())` for English; for CJK text, use `len(re.findall(r'[\w\u4e00-\u9fff]+', text))` (count both alphabetic words and Chinese characters).
- When using overlapping context, be careful not to exceed the model's context window: trim overlap if the chunk + overlap is too large.
