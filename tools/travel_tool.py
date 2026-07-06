import requests
import os

from tavily import TavilyClient

def get_weather(city: str):
    try:
        url = f"https://wttr.in/{city}?format=j1"

        proxies = None
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if http_proxy or https_proxy:
            proxies = {
                "http": http_proxy or "",
                "https": https_proxy or "",
            }

        response = requests.get(url, timeout=10, proxies=proxies)
        response.raise_for_status()
        data = response.json()

        current_condition = data.get("current_condition", [{}])[0]
        weather_desc = current_condition.get("weatherDesc", [{}])[0].get("value", "未知")
        temp = current_condition.get("temp_C", "未知")
        humidity = current_condition.get("humidity", "未知")
        wind_speed = current_condition.get("windspeedKmph", "未知")

        return f"{city} 天气：{weather_desc}，温度：{temp}°C，湿度：{humidity}%，风速：{wind_speed} km/h"
    except Exception as e:
        return f"请求失败：{str(e)}"

def get_attraction(city: str, weather: str) -> str:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "Tavily API key is not set. Please set the TAVILY_API_KEY environment variable."

    tavily = TavilyClient(api_key=api_key)
    query = f"'{city}'在'{weather}'天气下的旅游景点推荐以及理由"

    try:
        response = tavily.search(query=query, search_depth="basic", include_answer=True)
        if response.get("answer"):
            return f"--- 针对 {city}({weather}) 的景点推荐 ---\n{response['answer']}"

        formatted_results = []
        for result in response.get("results", []):
            title = result.get("title", "无标题")
            url = result.get("url", "无链接")
            snippet = result.get("snippet", "无摘要")
            formatted_results.append(f"标题: {title}\n链接: {url}\n摘要: {snippet}\n")

        if not formatted_results:
            return f"未找到关于 {city}({weather}) 的旅游景点推荐。"

        return f"--- 针对 {city}({weather}) 的景点推荐 ---\n" + "\n".join(formatted_results)
    except Exception as e:
        return f"请求 Tavily API 失败：{str(e)}"