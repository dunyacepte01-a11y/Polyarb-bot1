
import requests, time
resp = requests.get('https://gamma-api.polymarket.com/events?tag_slug=5m&active=true&limit=20&closed=false')
data = resp.json()
for e in data:
    s = e.get('seriesSlug','')
    t = e.get('title','')
    if 'btc' in s.lower() or 'btc' in t.lower():
        print('title:', t)
        print('slug:', e.get('slug',''))
        print('seriesSlug:', s)
        print('active:', e.get('active'))
        print()
