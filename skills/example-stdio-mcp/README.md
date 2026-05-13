# 示例 stdio MCP（`echo`）

本目录提供两类用途：

1. **`server.py`** — 真实的 **MCP stdio** 进程（FastMCP），暴露工具 **`echo`**，用于验证宿主侧 ``skills.mcp_servers`` 通用挂载与自动化测试。
2. **`echo_worker.py`** — 非 MCP 的极简子进程：读 stdin 至 EOF 后以状态码 0 退出，供「纯进程生命周期」类测试使用（与 MCP JSON-RPC 无关）。

## 启用示例 MCP（`local.yaml`）

```yaml
skills:
  mcp_servers:
    - id: example_echo
      enabled: true
      entrypoint: skills/example-stdio-mcp/server.py
      strip_http_proxy: false
      env: {}
```

`entrypoint` 相对于仓库根；宿主使用当前解释器执行该脚本。

## 依赖

与主工程一致：需已安装 `mcp`（见仓库根 `pyproject.toml`）。
