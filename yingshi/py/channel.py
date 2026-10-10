# -*- coding: utf-8 -*-
# FreeTV API 影視壳 / TVBox Python Spider (效能優化版)

import sys
import json
import concurrent.futures
import requests

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def __init__(self):
        super().__init__()

        self.name = "FreeTV"
        self.api_urls = [
            "https://api.dfj.info/api/box/v1/lineup",
          
        ]

        self.headers = {
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJpcHR2LXNhYXMtYm94Iiwic3ViIjoiNzczNyIsInRlbmFudF9pZCI6NywiZW5kX3VzZXJfaWQiOjc3MzcsImRldmljZV9pZCI6ODQ2NSwiZGV2aWNlX21hYyI6IjQ0OkZFOkVGOjg0OjZBOkQ1IiwidHlwZSI6ImJveCIsImp0aSI6Ijc4M2Y1YmNjODQyNzQ0ZmViMmY0YjM1YzVkMWM3YjVjIiwiaDVfcG9saWN5X2FwcF9pZCI6bnVsbCwicHNpZCI6Ijc4M2Y1YmNjODQyNzQ0ZmViMmY0YjM1YzVkMWM3YjVjIiwiYXV0aF90aW1lIjoxNzkxNTkzNzE1LjkyNTgyNiwiaWF0IjoxNzkxNTkzNzE1LjkyNTgyNiwiZXhwIjoxNzk0MTg1NzE1fQ.YDaNZFSNMVT51TwbCg9BMB8RaSH_800NzcoB_xcEL9Y",
            "x-tenant-slug": "yushanvideo",
            "accept-language": "zh-CN",
            "x-box-proto": "1.0",
            "user-agent": "okhttp/3.12.13"
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.channels = []
        self.categories = []

    def getName(self):
        return self.name

    def init(self, extend):
        pass

    def load_channels(self):
        if self.channels:
            return self.channels

        processed_channels = []
        categories_order = []

        def fetch_url(url):
            try:
                res = self.session.get(url, timeout=8)
                if res.status_code == 200:
                    return res.json()
            except Exception:
                pass
            return None

        # 使用多執行緒並發請求多頁 API，加快頻道清單載入速度
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            results = executor.map(fetch_url, self.api_urls)

        for data in results:
            if not data:
                continue
            partitions = data.get("data", {}).get("partitions", [])
            
            for partition in partitions:
                categories = partition.get("categories", [])
                for cat in categories:
                    category_name = str(cat.get("name", "其他")).strip()
                    channels = cat.get("channels", [])
                    
                    if category_name not in categories_order:
                        categories_order.append(category_name)
                    
                    for ch in channels:
                        ch_name = str(ch.get("name", "")).strip()
                        stream_url = str(ch.get("stream_url", "")).strip()
                        
                        if not ch_name or not stream_url:
                            continue
                        
                        logo = str(ch.get("logo_resolved_url", "")).strip()
                        if logo and logo.startswith("/"):
                            logo = "https://s.freetv.sh" + logo

                        processed_channels.append({
                            "name": ch_name,
                            "url": stream_url,
                            "logo": logo,
                            "category": category_name
                        })

        self.channels = processed_channels
        self.categories = categories_order
        return self.channels

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(ext in url.lower() for ext in [".m3u8", ".mp4", ".ts", ".flv"])

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        self.load_channels()
        classes = [{"type_name": "全部頻道", "type_id": "all"}]
        for cat in self.categories:
            classes.append({
                "type_name": cat,
                "type_id": cat
            })
        return {"class": classes}

    def homeVideoContent(self):
        channels = self.load_channels()
        videos = []
        for ch in channels:
            videos.append({
                "vod_id": ch["url"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"],
                "vod_remarks": ch["category"],
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": "FreeTV 直播頻道"
            })
        return {"list": videos}

    def categoryContent(self, tid, page, filter, ext):
        channels = self.load_channels()
        videos = []
        for ch in channels:
            if tid != "all" and ch["category"] != tid:
                continue
            videos.append({
                "vod_id": ch["url"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"],
                "vod_remarks": "直播",
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": ch["category"]
            })

        return {
            "list": videos,
            "page": 1,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos)
        }

    def detailContent(self, array):
        if not array:
            return {"list": []}
        
        url = array[0]
        channels = self.load_channels()
        ch_name = "FreeTV直播"
        logo = ""
        category = "直播"

        for ch in channels:
            if ch["url"] == url:
                ch_name = ch["name"]
                logo = ch["logo"]
                category = ch["category"]
                break

        return {
            "list": [
                {
                    "vod_id": url,
                    "vod_name": ch_name,
                    "vod_pic": logo,
                    "vod_remarks": "直播",
                    "vod_year": "",
                    "vod_area": category,
                    "vod_content": "FreeTV直播頻道",
                    "vod_play_from": "FreeTV",
                    "vod_play_url": f"播放${url}"
                }
            ]
        }

    def searchContent(self, key, quick, page="1"):
        if not key:
            return {"list": []}

        key = str(key).lower()
        channels = self.load_channels()
        videos = []

        for ch in channels:
            if key not in ch["name"].lower():
                continue

            videos.append({
                "vod_id": ch["url"],
                "vod_name": ch["name"],
                "vod_pic": ch["logo"],
                "vod_remarks": "直播",
                "vod_content": ch["category"]
            })

        return {"list": videos}

    def searchContentPage(self, keywords, quick, page):
        return self.searchContent(keywords, quick, page)

    def playerContent(self, flag, pid, vipFlags):
        if not pid:
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

        # 同步帶入鑑權標頭，避免播放時因缺乏認證導致卡頓或無法播放
        return {
            "parse": 0,
            "playUrl": "",
            "url": pid,
            "header": {
                "authorization": self.headers.get("authorization", ""),
                "x-tenant-slug": self.headers.get("x-tenant-slug", ""),
                "x-box-proto": "1.0",
                "User-Agent": "okhttp/3.12.13",
                "Referer": "https://s.freetv.sh/"
            }
        }

    def liveContent(self, url):
        channels = self.load_channels()
        lines = ["#EXTM3U"]
        for ch in channels:
            lines.append(
                f'#EXTINF:-1 tvg-logo="{ch["logo"]}" group-title="{ch["category"]}",{ch["name"]}'
            )
            lines.append(ch["url"])
        return "\n".join(lines)

    def localProxy(self, params):
        return {}

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
        return "正在Destroy"


if __name__ == '__main__':
    pass
