import os
import requests
import json
import re
from datetime import datetime, timedelta
from fastmcp import FastMCP

# AMap API 配置
AMAP_API_KEY = os.getenv("AMAP_API_KEY", "c0abe1f7b95925c860cefe6cdacbe174")
mcp = FastMCP("amap")

class TravelPlanner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://restapi.amap.com/v3"
    
    def get_city_code(self, city_name: str) -> tuple:
        """通过AMap地理编码API获取城市名称和城市代码"""
        url = f"{self.base_url}/geocode/geo"
        params = {
            "key": self.api_key,
            "address": city_name,
            "output": "JSON"
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            if data.get("status") == "1" and data.get("geocodes"):
                geocode = data["geocodes"][0]
                city = geocode.get("city", city_name)
                city_code = geocode.get("adcode", "")
                return city, city_code
            return None, None
        except Exception:
            return None, None
    
    def get_weather(self, city, days=1):
        """获取城市天气预报"""
        url = f"{self.base_url}/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "all" if days > 1 else "base",
            "output": "JSON"
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            if data.get("status") == "1":
                if days > 1:
                    return data.get("forecasts", [])[0].get("casts", [])[:days]
                else:
                    return data.get("lives", [])[0]
            return None
        except Exception:
            return None
    
    def search_places(self, city, keywords, types=None, pagesize=5):
        """搜索景点或美食"""
        url = f"{self.base_url}/place/text"
        params = {
            "key": self.api_key,
            "city": city,
            "keywords": keywords,
            "types": types,
            "offset": pagesize,
            "page": 1,
            "extensions": "all",
            "output": "JSON"
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            if data.get("status") == "1":
                return data.get("pois", [])
            return []
        except Exception:
            return []
    

    def get_route(self, origin, destination, city, mode="transit"):
     if mode == "transit":
         url = f"{self.base_url}/direction/transit/integrated"
     elif mode == "driving":
        url = f"{self.base_url}/direction/driving"
     else:
        url = f"{self.base_url}/direction/walking"
     params = {
        "key": self.api_key,
        "origin": origin,
        "destination": destination,
        "city": city,
        "output": "JSON"
     }
     try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data.get("status") == "1":
             return data.get("route", {}).get("paths" if mode != "transit" else "transits", [])
        return []
     except Exception:
        return []


    def generate_itinerary(self, query):
        """解析用户输入并生成旅游攻略"""
        # 解析输入: 城市和天数
        city, days = self._parse_query(query)
        if not city:
            return "❌ 无法识别城市，请提供有效的城市名称。"

        # 获取数据
        weather = self.get_weather(city[1], days)
        attractions = self.search_places(city[1], "", types="风景名胜", pagesize=10)[:5]
        foods = self.search_places(city[1], "美食", types="餐饮服务", pagesize=5)
        route = []
        if attractions and foods:
            origin = attractions[0].get("location")
            dest = foods[0].get("location")
        print(f"Origin: {origin}, Destination: {dest}")  # 调试
        if origin and dest and re.match(r"^\d+\.\d+,\d+\.\d+$", origin) and re.match(r"^\d+\.\d+,\d+\.\d+$", dest):
        #    routes = self.get_route(origin, dest, city[1])
            routes = self.get_route(origin, dest, city[1], mode="driving")
            if not routes:
              routes = self.get_route(origin, dest, city[1], mode="walking")
        else:
           error_msg = "⚠️ 起点或终点坐标无效，无法生成路线。"


        # 拼接文本攻略
        return self._build_text(city[0], days, weather, attractions, foods, route)

    def _parse_query(self, query: str):
        city_pattern = re.search(r"([一-龥]+)(?:[一二三四五六七八九十\d]+)?(?:天|日)?(?:游)?", query)
        days_pattern = re.search(r"([一二三四五六七八九十\d]+)(?:天|日)", query)
        city_name = city_pattern.group(1) if city_pattern else None
        city = self.get_city_code(city_name) if city_name else (None, None)
        days = 1
        if days_pattern:
            val = days_pattern.group(1)
            mapping = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
            days = mapping.get(val, int(val))
        return city, min(days,7)

    def _build_text(self, city, days, weather, attractions, foods, route):
        it = []
        it.append(f"📍 {city}{days}日游攻略")
        it.append(f"生成时间：{datetime.now():%Y-%m-%d %H:%M}")
        # 天气
        it.append("🌤️ 天气信息")
        if weather:
            if days == 1:
                it.append(f"今天天气: {weather.get('weather','未知')}，温度: {weather.get('temperature','')}℃，风向: {weather.get('winddirection','')}，风力: {weather.get('windpower','')}级")
            else:
                for i, d in enumerate(weather):
                    dt = (datetime.now()+timedelta(days=i)).strftime("%m/%d")
                    it.append(f"{dt}：{d.get('dayweather','')} → {d.get('nightweather','')}，{d.get('daytemp','')}℃/{d.get('nighttemp','')}℃，{d.get('daywind','')}/{d.get('nightwind','')}")
        # 景点
        it.append("🏞️ 景点推荐")
        for idx, a in enumerate(attractions,1):
            it.append(f"{idx}. {a.get('name')} - {a.get('address')} (评分: {a.get('biz_ext',{}).get('rating','无')})")
        # 美食
        it.append("🍽️ 美食推荐")
        for idx, f in enumerate(foods,1):
            it.append(f"{idx}. {f.get('name')} - {f.get('address')}，{f.get('type','')}，电话: {f.get('tel','无')}")
        # 路线
        if route:
            it.append("🛤️ 路线建议")
            for i, s in enumerate(route,1):
                it.append(f"{i}. {s.get('instruction')} ({s.get('distance')}米)")
        return "\n".join(it)
    

# HTML 可视化
@mcp.tool(description="将旅游攻略渲染为美化的 HTML 页面")
def visualize_travel_itinerary(query: str) -> str:
    text = TravelPlanner(AMAP_API_KEY).generate_itinerary(query)
    lines = text.splitlines()
    
    # HTML template with A4 size, print-friendly design, and professional style
    html = [
        "<!DOCTYPE html>",
        "<html lang=\"zh-CN\">",
        "<head>",
        "  <meta charset=\"UTF-8\">",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        f"  <title>{lines[0]}</title>",
        "  <link href=\"https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap\" rel=\"stylesheet\">",
        "  <link href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css\" rel=\"stylesheet\">",
        "  <style>",
        "    @page {",
        "      size: A4;",
        "      margin: 10mm;",
        "    }",
        "    body {",
        "      margin: 0;",
        "      font-family: 'Open Sans', sans-serif;",
        "      font-size: 12pt;",
        "      line-height: 1.5;",
        "      color: #2d3436;",
        "      background: #ffffff;",
        "      width: 210mm;",
        "      height: 297mm;",
        "      box-sizing: border-box;",
        "      padding: 10mm;",
        "      display: flex;",
        "      flex-direction: column;",
        "    }",
        "    .container {",
        "      max-width: 100%;",
        "      margin: 0;",
        "      background: #ffffff;",
        "      border: 1px solid #dfe6e9;",
        "      border-radius: 8px;",
        "      padding: 15mm;",
        "      flex: 1;",
        "      display: grid;",
        "      grid-template-columns: 1fr;",
        "      gap: 15px;",
        "    }",
        "    h1 {",
        "      font-size: 24pt;",
        "      font-weight: 700;",
        "      color: #2c3e50;",
        "      text-align: center;",
        "      margin: 0 0 10px 0;",
        "    }",
        "    .meta {",
        "      text-align: center;",
        "      color: #636e72;",
        "      font-size: 10pt;",
        "      margin-bottom: 20px;",
        "    }",
        "    .section {",
        "      margin-bottom: 20px;",
        "    }",
        "    .section h2 {",
        "      font-size: 16pt;",
        "      font-weight: 600;",
        "      color: #fff;",
        "      background: #0984e3;",
        "      padding: 8px 15px;",
        "      border-radius: 5px;",
        "      display: inline-block;",
        "      margin: 0;",
        "    }",
        "    .item {",
        "      padding: 10px;",
        "      border-left: 4px solid #74b9ff;",
        "      background: #f8f9fa;",
        "      border-radius: 0 5px 5px 0;",
        "      margin: 5px 0;",
        "      font-size: 10pt;",
        "    }",
        "    .timeline {",
        "      position: relative;",
        "      margin-left: 20px;",
        "      padding-left: 20px;",
        "      border-left: 2px dashed #b2bec3;",
        "    }",
        "    .timeline-item {",
        "      position: relative;",
        "      margin: 15px 0;",
        "    }",
        "    .timeline-item::before {",
        "      content: '\\f3c5';",
        "      font-family: 'Font Awesome 6 Free';",
        "      font-weight: 900;",
        "      position: absolute;",
        "      left: -28px;",
        "      top: 5px;",
        "      color: #e17055;",
        "      font-size: 14pt;",
        "    }",
        "    .print-button {",
        "      position: fixed;",
        "      top: 20px;",
        "      right: 20px;",
        "      padding: 10px 20px;",
        "      background: #e17055;",
        "      color: #fff;",
        "      border: none;",
        "      border-radius: 5px;",
        "      font-size: 12pt;",
        "      cursor: pointer;",
        "    }",
        "    .print-button:hover {",
        "      background: #d63031;",
        "    }",
        "    .city-icon {",
        "      text-align: center;",
        "      font-size: 30pt;",
        "      color: #b2bec3;",
        "      margin-bottom: 10px;",
        "    }",
        "    @media print {",
        "      body {",
        "        margin: 0;",
        "        padding: 0;",
        "        box-shadow: none;",
        "      }",
        "      .print-button {",
        "        display: none;",
        "      }",
        "      .container {",
        "        border: none;",
        "        box-shadow: none;",
        "      }",
        "      .item, .timeline-item {",
        "        background: #fff;",
        "        border-left-color: #2d3436;",
        "      }",
        "      .timeline {",
        "        border-left-color: #636e72;",
        "      }",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        "  <button class=\"print-button\" onclick=\"window.print()\">打印行程 <i class=\"fas fa-print\"></i></button>",
        "  <div class=\"container\">",
        f"    <div class=\"city-icon\"><i class=\"fas fa-city\"></i></div>",
        f"    <h1>{lines[0]}</h1>",
        f"    <div class=\"meta\">{lines[1]}</div>",
    ]

    # Process sections with icons and timeline for itinerary
    section_map = {'🌤️': ('weather', 'fa-cloud-sun'), '🏞️': ('attractions', 'fa-landmark'), 
                   '🍽️': ('foods', 'fa-utensils'), '🛤️': ('routes', 'fa-route')}
    current = None
    itinerary_section = False
    for line in lines[2:]:
        if line.startswith(tuple(section_map.keys())):
            if current == 'itinerary':
                html.append("      </div>")  # Close timeline div
                itinerary_section = False
            sec, icon = section_map[line[:2]]
            html.append(f"    <div class=\"section\" id=\"{sec}\">")
            html.append(f"      <h2><i class=\"fas {icon}\"></i> {line[2:].strip()}</h2>")
            current = sec
            if sec == 'attractions':  # Treat attractions as part of itinerary timeline
                html.append("      <div class=\"timeline\">")
                itinerary_section = True
        else:
            content = line.strip()
            if content:
                if itinerary_section:
                    html.append(f"      <div class=\"timeline-item\">{content}</div>")
                else:
                    html.append(f"      <div class=\"item\">{content}</div>")
    
    if itinerary_section:
        html.append("      </div>")  # Close final timeline div
    html.append("  </div>")
    html.append("</body>")
    html.append("</html>")
    html_content= "\n".join(html)

    # 构建桌面路径
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Travel_Plan_{timestamp}.html"
    filepath = os.path.join(desktop, filename)
    
    try:
        # 确保桌面目录存在
        os.makedirs(desktop, exist_ok=True)
        
        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # 返回结果包含文件路径
        return f"✅ 攻略已生成并保存到桌面：\n{filepath}\n\n{html_content}"
    except Exception as e:
        return f"❌ 文件保存失败：{str(e)}\n\n{html_content}"

if __name__ == "__main__":
    mcp.run()