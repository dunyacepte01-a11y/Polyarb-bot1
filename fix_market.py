import requests, json, time
from datetime import datetime

now = time.time()
# Tüm aktif BTC marketlerini dene
urls = [
    "https://gamma-api.polymarket.com/events?tag_slug=5m&limit=100&closed=false",
    "https://gamma-api.polymarket.com/events?limit=100&closed=false&tag_slug=crypto",
]

for url in urls:
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        for e in data:
            slug = e.get('seriesSlug','') + e.get('slug','')
            if 'btc-up-or-down' in slug or 'btc-updown' in slug:
                try:
                    end_ts = datetime.fromisoformat(e['endDate'].replace('Z','+00:00')).timestamp()
                    start_ts = datetime.fromisoformat(e['startDate'].replace('Z','+00:00')).timestamp()
                    kaldi = end_ts - now
                    gecti = now - start_ts
                    print(f"Title: {e.get('title','')}")
                    print(f"Başladı: {round(gecti)}s önce, Bitiyor: {round(kaldi)}s sonra")
                    print(f"Aktif: {start_ts <= now <= end_ts}")
                    print()
                except: pass
    except Exception as ex:
        print("Hata:", ex)
