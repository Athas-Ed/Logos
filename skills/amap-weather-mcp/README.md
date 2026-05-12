# 高德实况天气 MCP（测试用 Skill）

基于 **Model Context Protocol** 的 stdio Server，向 Logos Agent 暴露工具 **`query_weather`**（调用高德开放平台 [天气查询](https://lbs.amap.com/api/webservice/guide/api/weatherinfo) Web 服务）。

## 配置放哪里（密钥）

**推荐：走 Logos 应用配置（`config/local.yaml`）**，由宿主在拉起子进程时注入环境变量 `AMAP_WEB_KEY`。理由：密钥与运行环境一致、不入库、可统一用 `LOGOS_SKILLS__AMAP_WEATHER__WEB_API_KEY` 覆盖；Skill 包保持可移植、不包含私密文件。

若将 Key 只写在 Skill 目录内的文件（选项 b），容易出现误提交、多环境重复配置，且与「S&G 统一治理」分叉。

若从 **非仓库目录** 启动、或 ``logos`` 安装在 site-packages（非 ``pip install -e .``），请设置环境变量 **`LOGOS_REPO_ROOT`** 指向本仓库根目录，否则宿主找不到 ``skills/amap-weather-mcp/server.py``。

**工具调用失败排查**：宿主在 **uvicorn 异步上下文** 里若直接 ``asyncio.run`` 会触发嵌套事件循环错误；本仓库已将 MCP 客户端隔离到工作线程。若仍失败，请检查本机是否为 LLM 配置了 **HTTP(S) 代理**——子进程访问高德时会剥离常见代理环境变量，且 httpx 使用 ``trust_env=False``，避免走本地代理。

## 启用方式

1. 在高德开放平台申请 **Web服务** Key（非 JS API Key）。
2. 在 `config/local.yaml`（从 `config/local.example.yaml` 参考）中设置：

```yaml
skills:
  amap_weather:
    enabled: true
    web_api_key: "你的Key"
```

3. 重启后端；对话中模型可选用 `query_weather`，参数 `city` 为城市名或 6 位 `adcode`。

## 独立调试（不经 Logos）

在 shell 中导出 `AMAP_WEB_KEY` 后，可用任意 MCP Client 以 stdio 指向本目录的 `server.py`。

```powershell
$env:AMAP_WEB_KEY="你的Key"
python server.py
```

（stdio 模式下进程会等待 JSON-RPC，适合由 MCP Inspector / Cursor MCP 配置连接，而非手工敲命令行交互。）

## 依赖

与主工程一致：需已安装 `mcp`、`httpx`（见仓库根 `pyproject.toml`）。
