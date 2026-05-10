# 示例 stdio 子进程（MCP 起停参考）

本目录**不是**完整 MCP 协议实现，仅提供一个**极小的 stdio 进程**：阻塞读取标准输入直到 EOF，然后以状态码 0 退出。

用途：

- 在自动化测试里验证「拉起子进程 → 关闭 stdin → `wait`」无挂死、无僵尸（尽力）。
- 作为后续接入真实 MCP（JSON-RPC over stdio）时的占位目录名约定。

运行：

```bash
python echo_worker.py < /dev/null
```

Windows PowerShell：

```powershell
Get-Content NUL | python echo_worker.py
```

或直接：

```powershell
python -c "import sys; sys.stdin.read()" 
```

（与 `echo_worker.py` 行为等价。）
