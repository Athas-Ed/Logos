"""commit-msg：若暂存区包含 API 契约相关路径，则提交说明须含「契约：」行。

与 ``original_docs/重要子系统开发文档/API终极文档.md`` 第 4.1 节一致。
安装：仓库根执行 ``git config core.hooksPath .githooks``（见该文档）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 与 .cursor/rules/logos-api-contract.mdc 对齐；用 POSIX 风格路径与 git 输出比对
CONTRACT_PATHS: frozenset[str] = frozenset(
    {
        "src/logos/platform/ii_layer/api_v1.py",
        "src/logos/platform/ii_layer/deps.py",
        "original_docs/重要子系统开发文档/API-V0.2.md",
        "tests/test_stream5_api.py",
        "src/gui/src/api/sseChat.ts",
        "src/gui/src/api/bootstrap.ts",
        "src/gui/src/api/developer.ts",
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


def _touches_contract(staged: list[str]) -> bool:
    norm = {p.replace("\\", "/") for p in staged}
    return bool(norm & CONTRACT_PATHS)


def _has_contract_line(message: str) -> bool:
    for line in message.splitlines():
        s = line.strip()
        if s.startswith("契约：") or s.startswith("契约:"):
            return True
    return False


def _should_skip(message: str) -> bool:
    s = message.lstrip()
    if s.startswith("Merge "):
        return True
    if s.startswith("Revert "):
        return True
    return False


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: check_api_contract_commit_msg.py <提交说明文件路径>", file=sys.stderr)
        return 2
    msg_file = Path(sys.argv[1])
    if not msg_file.is_file():
        return 0

    text = msg_file.read_text(encoding="utf-8")
    if _should_skip(text):
        return 0
    if _has_contract_line(text):
        return 0

    repo_root = _repo_root()
    staged = _staged_paths(repo_root)
    if not staged:
        return 0
    if not _touches_contract(staged):
        return 0

    print(
        "【API 契约钩子】本次提交包含以下一类或多类文件的暂存变更：\n"
        "  api_v1 / ii_layer deps / API-V0.2.md / test_stream5_api / sseChat / bootstrap / developer\n"
        "请在提交说明中单独写一行（与《API终极文档》第 4.1 节一致）：\n"
        "  契约：无变更\n"
        "或\n"
        "  契约：已更新 API-V0.2（摘要：……）\n"
        "\n"
        "若确需跳过（不推荐）：git commit --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
