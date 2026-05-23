"""pre-commit：若暂存区包含「实现或 GUI 侧的 API 契约载体」之一，则必须同时暂存 API-V0.2 与 test_stream5。

与 ``original_docs/重要子系统开发文档/API终极文档.md`` 第 4.1 节一致。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 任一命中即要求「契约文 + 契约测」同批暂存（不含二者自身作为唯一触发）
BUNDLE_TRIGGER_PATHS: frozenset[str] = frozenset(
    {
        "src/logos/platform/ii_layer/api_v1.py",
        "src/logos/platform/ii_layer/deps.py",
        "src/gui/src/api/sseChat.ts",
        "src/gui/src/api/bootstrap.ts",
        "src/gui/src/api/developer.ts",
    }
)

REQUIRED_STAGED: frozenset[str] = frozenset(
    {
        "original_docs/重要子系统开发文档/API-V0.2.md",
        "tests/test_stream5_api.py",
    }
)


def _repo_root() -> Path:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return Path(__file__).resolve().parents[1]


def _staged_paths(repo_root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--cached", "--name-only", "-z"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return []
    raw = r.stdout or ""
    return [p for p in raw.split("\0") if p]


def main() -> int:
    repo_root = _repo_root()
    staged = _staged_paths(repo_root)
    if not staged:
        return 0

    norm = {p.replace("\\", "/") for p in staged}
    if not (norm & BUNDLE_TRIGGER_PATHS):
        return 0

    missing = sorted(REQUIRED_STAGED - norm)
    if not missing:
        return 0

    req_lines = "\n".join(f"  - {m}" for m in sorted(REQUIRED_STAGED))
    print(
        "【API 契约 pre-commit】本次暂存包含以下一类或多类文件：\n"
        "  api_v1.py / ii_layer deps.py / sseChat.ts / bootstrap.ts / developer.ts\n"
        "须**同时**暂存下列文件（可与上一提交相比仅有修订记录或注释级 diff，但必须出现在本提交的暂存区）：\n"
        f"{req_lines}\n"
        f"\n当前未暂存：{', '.join(missing)}\n"
        "\n确需跳过（不推荐）：git commit --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
