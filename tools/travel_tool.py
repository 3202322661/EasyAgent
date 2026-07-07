"""
旅游与天气查询工具模块。

提供实时天气查询和基于天气的旅游景点推荐：
  - get_weather: 通过 wttr.in API 获取城市天气
  - get_attraction: 通过 Tavily 搜索引擎推荐景点
"""

import logging
import os
from typing import Optional, Dict

import requests
from tavily import TavilyClient

logger = logging.getLogger(__name__)

# ────────────────────────── 常量 ──────────────────────────

WTTR_URL: str = "https://wttr.in/{city}?format=j1"
REQUEST_TIMEOUT: int = 10  # 秒


def _get_proxies() -> Optional[Dict[str, str]]:
    """从环境变量读取代理配置。"""
    proxies: Dict[str, str] = {}
    http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    if https_proxy:
        proxies["https"] = https_proxy
    if http_proxy:
        proxies["http"] = http_proxy

    return proxies if proxies else None


def get_weather(city: str) -> str:
    """获取指定城市的实时天气信息。

    通过 wttr.in 公开 API 获取数据，包含天气状况、温度、湿度和风速。

    Args:
        city: 城市名称（中文或英文），如 '北京', 'London'

    Returns:
        格式化的天气信息字符串
    """
    if not city or not city.strip():
        return "[ERROR] 城市名称不能为空。"

    try:
        url = WTTR_URL.format(city=city.strip())
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            proxies=_get_proxies(),
        )
        response.raise_for_status()
        data = response.json()

        current = data.get("current_condition", [{}])[0]
        weather_desc = (current.get("weatherDesc", [{}])[0]
                        .get("value", "未知"))
        temp = current.get("temp_C", "未知")
        humidity = current.get("humidity", "未知")
        wind_speed = current.get("windspeedKmph", "未知")
        feels_like = current.get("FeelsLikeC", "未知")
        visibility = current.get("visibility", "未知")

        return (
            f"🌤️ {city} 天气:\n"
            f"  天气: {weather_desc}\n"
            f"  温度: {temp}°C (体感 {feels_like}°C)\n"
            f"  湿度: {humidity}%\n"
            f"  风速: {wind_speed} km/h\n"
            f"  能见度: {visibility} km"
        )

    except requests.Timeout:
        return f"[ERROR] 请求 {city} 天气超时（{REQUEST_TIMEOUT}秒），请检查网络连接。"
    except requests.ConnectionError:
        return f"[ERROR] 无法连接到天气服务，请检查网络或代理设置。"
    except requests.HTTPError as e:
        return f"[ERROR] 天气服务返回错误 (HTTP {e.response.status_code})。"
    except Exception as e:
        logger.exception("获取天气时发生错误")
        return f"[ERROR] 获取 {city} 天气失败: {e}"


def get_attraction(city: str, weather: str) -> str:
    """根据城市和天气推荐旅游景点与活动。

    通过 Tavily Search API 联网搜索最适合当前天气的景点。

    Args:
        city: 城市名称
        weather: 当前天气状况描述，如 '下大雨', '晴天 30度'

    Returns:
        景点推荐结果
    """
    if not city or not city.strip():
        return "[ERROR] 城市名称不能为空。"

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return (
            "[ERROR] Tavily API Key 未设置。\n"
            "请设置环境变量 TAVILY_API_KEY 后重试。\n"
            "获取方式: https://tavily.com"
        )

    try:
        tavily = TavilyClient(api_key=api_key)
        query = f"'{city}'在'{weather}'天气下的旅游景点推荐以及理由"
        response = tavily.search(
            query=query,
            search_depth="basic",
            include_answer=True,
        )

        # 优先使用 AI 生成的综合回答
        if response.get("answer"):
            return (
                f"--- {city} ({weather}) 景点推荐 ---\n\n"
                f"{response['answer']}"
            )

        # 否则整理搜索结果
        results = response.get("results", [])
        if not results:
            return f"未找到关于 {city} ({weather}) 的旅游景点推荐。"

        formatted = [f"--- {city} ({weather}) 景点推荐 ---\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "无标题")
            url = result.get("url", "")
            snippet = result.get("content") or result.get("snippet", "无摘要")
            formatted.append(f"{i}. {title}")
            if url:
                formatted.append(f"   链接: {url}")
            formatted.append(f"   摘要: {snippet}\n")

        return "\n".join(formatted)

    except Exception as e:
        logger.exception("搜索景点时发生错误")
        return f"[ERROR] Tavily API 搜索失败: {e}"
