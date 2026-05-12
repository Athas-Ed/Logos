"""同步 MCP stdio 客户端（NDJSON JSON-RPC），供 :mod:`logos.harness.sg_layer.mcp_bridge` 在进程内工具注册表中转发调用。

与 ``mcp.client.stdio`` 的成帧约定一致：每行一条 JSON-RPC 消息。子进程回收顺序遵循 MCP 规范：先关 stdin，再 ``wait``，超时后强杀。
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO

from mcp.client.stdio import StdioServerParameters, get_default_environment
from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    CallToolResult,
    ClientCapabilities,
    Implementation,
    InitializeRequest,
    InitializeRequestParams,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    ListToolsRequest,
    LATEST_PROTOCOL_VERSION,
)

RequestId = str | int


class McpStdioJsonRpcSession:
    """最小 MCP 会话（initialize → tools/list → tools/call），全同步 API。"""

    def __init__(
        self,
        params: StdioServerParameters,
        *,
        stderr: TextIO | int | None = subprocess.DEVNULL,
    ) -> None:
        self._params = params
        self._stderr_target = stderr
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._stderr_thread: threading.Thread | None = None

    def __enter__(self) -> McpStdioJsonRpcSession:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            msg = "MCP 会话已启动"
            raise RuntimeError(msg)
        p = self._params
        env = {**get_default_environment(), **(p.env or {})}
        cmd = [p.command, *p.args]
        proc: subprocess.Popen[str] | None = None
        try:
            proc = subprocess.Popen(  # noqa: S603 — 参数由调用方与测试固定
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._stderr_target,
                text=True,
                encoding=p.encoding,
                errors=p.encoding_error_handler,
                cwd=p.cwd,
                env=env,
                bufsize=0,
            )
            self._proc = proc
            if self._stderr_target is subprocess.PIPE:
                self._stderr_thread = threading.Thread(
                    target=self._drain_stderr,
                    name="mcp-stderr-drain",
                    daemon=True,
                )
                self._stderr_thread.start()
            self._handshake()
        except Exception:
            if proc is not None and self._proc is not None:
                self._force_terminate(proc, wait_timeout=3)
            self._proc = None
            self._stderr_thread = None
            raise

    def _force_terminate(self, proc: subprocess.Popen[str], *, wait_timeout: float = 8) -> None:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except BrokenPipeError:
            pass
        try:
            proc.wait(timeout=wait_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for _line in proc.stderr:
            pass

    def _handshake(self) -> None:
        init = InitializeRequest(
            params=InitializeRequestParams(
                protocolVersion=LATEST_PROTOCOL_VERSION,
                capabilities=ClientCapabilities(),
                clientInfo=Implementation(name="logos-mcp-sync", version="0.1.0"),
            )
        )
        self._request_jsonrpc(init.method, init.params.model_dump(mode="json", by_alias=True, exclude_none=True))
        initialized = JSONRPCNotification(
            jsonrpc="2.0",
            method="notifications/initialized",
            params=None,
        )
        self._write_obj(initialized.model_dump(mode="json", by_alias=True, exclude_none=True))

    def _write_obj(self, obj: dict[str, Any]) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            msg = "MCP 子进程未就绪"
            raise RuntimeError(msg)
        line = json.dumps(obj, ensure_ascii=False)
        if "\n" in line:
            msg = "JSON-RPC 载荷不得含裸换行"
            raise ValueError(msg)
        proc.stdin.write(line + "\n")
        proc.stdin.flush()

    def _next_request_id(self) -> RequestId:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _request_jsonrpc(self, method: str, params: dict[str, Any] | None) -> dict[str, Any]:
        rid = self._next_request_id()
        req = JSONRPCRequest(jsonrpc="2.0", id=rid, method=method, params=params)
        self._write_obj(req.model_dump(mode="json", by_alias=True, exclude_none=True))
        return self._read_until_id(rid)

    def _read_until_id(self, expect_id: RequestId) -> dict[str, Any]:
        proc = self._proc
        if proc is None or proc.stdout is None:
            msg = "MCP 子进程未就绪"
            raise RuntimeError(msg)
        while True:
            line = proc.stdout.readline()
            if line == "":
                msg = "MCP 服务端在响应前关闭了 stdout"
                raise EOFError(msg)
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                bad = f"MCP 非 JSON 行: {line[:120]!r}"
                raise ValueError(bad) from exc
            if payload.get("id") == expect_id:
                if "error" in payload:
                    err_obj = payload.get("error")
                    raise RuntimeError(f"MCP JSON-RPC 错误: {err_obj!r}")
                resp = JSONRPCResponse.model_validate(payload)
                return dict(resp.result)
            # 其它 id 或 notification：忽略并继续读（与官方异步客户端行为类似）

    def list_tools(self) -> dict[str, Any]:
        inner = ListToolsRequest()
        params = inner.params.model_dump(mode="json", by_alias=True, exclude_none=True) if inner.params else None
        return self._request_jsonrpc(inner.method, params)

    def call_tool(self, name: str, arguments: Mapping[str, Any] | None) -> CallToolResult:
        inner = CallToolRequest(
            params=CallToolRequestParams(name=name, arguments=dict(arguments or {})),
        )
        p = inner.params.model_dump(mode="json", by_alias=True, exclude_none=True)
        raw = self._request_jsonrpc(inner.method, p)
        return CallToolResult.model_validate(raw)

    def call_tool_text(self, name: str, arguments: Mapping[str, Any] | None) -> str:
        result = self.call_tool(name, arguments)
        if result.isError:
            return f"error: MCP 工具 {name!r} 报告 isError"
        parts: list[str] = []
        for block in result.content:
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts) if parts else ""

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        self._force_terminate(proc, wait_timeout=8)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None


def stdio_params_for_example_skill(*, repo_root: Path, python_exe: str) -> StdioServerParameters:
    """启动 ``skills/example-stdio-mcp/server.py`` 的推荐参数（cwd 为仓库根，便于 ``src`` 在 PYTHONPATH）。"""
    script = repo_root / "skills" / "example-stdio-mcp" / "server.py"
    env = {**get_default_environment(), "PYTHONPATH": str(repo_root / "src")}
    return StdioServerParameters(
        command=python_exe,
        args=[str(script)],
        cwd=str(repo_root),
        env=env,
    )
