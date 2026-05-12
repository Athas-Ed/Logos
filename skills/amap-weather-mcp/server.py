"""高德开放平台实况天气 MCP（stdio）。密钥由宿主通过环境变量 ``AMAP_WEB_KEY`` 注入。"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logos-amap-weather")

_AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


def _read_web_key() -> str:
    return (os.environ.get("AMAP_WEB_KEY") or "").strip()


@mcp.tool()
async def query_weather(city: str) -> str:
    """查询中国境内城市或区域的实况天气。

    :param city: 支持中文/英文城市名、区名，或 6 位行政区划 adcode（如 ``110101``）。
    """
    key = _read_web_key()
    if not key:
        return (
            "error: 未配置高德 Web服务 Key。请在 Logos 的 config/local.yaml 中填写 "
            "skills.amap_weather.web_api_key，并设置 skills.amap_weather.enabled: true；"
            "或自行以环境变量 AMAP_WEB_KEY 启动本进程后重试。"
        )
    city_q = (city or "").strip()
    if not city_q:
        return "error: city 不能为空"

    params: dict[str, Any] = {
        "key": key,
        "city": city_q,
        "extensions": "base",
    }
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            trust_env=False,
        ) as client:
            r = await client.get(_AMAP_WEATHER_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as exc:
        return f"error: 请求高德接口失败 — {type(exc).__name__}: {exc}"
    except ValueError:
        return "error: 高德返回非 JSON 响应"

    status = str(data.get("status", ""))
    if status != "1":
        info = data.get("info") or data.get("infocode") or data
        return f"error: 高德接口返回异常 — {info!s}"

    lives = data.get("lives") or []
    if not lives:
        return f"error: 无实况数据（lives 为空），原始响应：{json.dumps(data, ensure_ascii=False)}"

    live = lives[0]
    lines = [
        f"城市：{live.get('city', city_q)}",
        f"天气：{live.get('weather', '')}",
        f"气温：{live.get('temperature', '')}℃",
        f"风向：{live.get('winddirection', '')}{live.get('windpower', '')}级",
        f"湿度：{live.get('humidity', '')}%",
        f"发布时间：{live.get('reporttime', '')}",
    ]
    return "；".join(lines)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
