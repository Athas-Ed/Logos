"""读到 stdin EOF 后退出（退出码 0）。用于 MCP 类 stdio 子进程生命周期测试占位。"""

from __future__ import annotations

import sys


def main() -> None:
    sys.stdin.read()


if __name__ == "__main__":
    main()
