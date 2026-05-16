"""第四阶段 §9.3 S12：API 热路径微压测（便于 cProfile 采样）。

在仓库根目录执行（将 ``N`` 换为循环次数，默认 200）::

    .venv\\Scripts\\python.exe scripts/perf_baseline_bootstrap.py 500
    .venv\\Scripts\\python.exe -m cProfile -s tottime scripts/perf_baseline_bootstrap.py 800

说明：首次 ``import`` 仍含模块装载成本；增大 ``N`` 可让单次 ``bootstrap`` 路由在
``tottime`` 中更突出。完整场景与对比摘要见 ``original_docs/DEVLOG.md``。
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def _load_make_ports():
    p = ROOT / "tests" / "test_stream5_api.py"
    spec = importlib.util.spec_from_file_location("_stream5_api_bench", p)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load test_stream5_api")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._make_ports


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    tmp = Path(tempfile.mkdtemp())
    make_ports = _load_make_ports()
    ports = make_ports(tmp)
    from logos.harness.ii_layer.app import create_app

    app = create_app(ports)
    with TestClient(app) as client:
        for _ in range(n):
            r = client.get("/api/v1/bootstrap")
            if r.status_code != 200:
                raise SystemExit(f"unexpected status {r.status_code}")
    print(f"perf_baseline_bootstrap: {n} GET /api/v1/bootstrap ok tmp={tmp}")


if __name__ == "__main__":
    main()
