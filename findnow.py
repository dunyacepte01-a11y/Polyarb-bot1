
import requests, time
now = int(time.time())
resp = requests.get(f'https://gamma-api.polymarket.com/events?tag_slug=5m&limit=50&order=startDate&ascending=false')
data = resp.json()
for e in data[:10]:
    s = e.get('seriesSlug','')
    if 'btc' in s.lower() or 'btc' in e.get('title','').lower():
        print('title:', e.get('title',''))
        print('slug:', e.get('slug',''))
        print('startDate:', e.get('startDate',''))
        print('endDate:', e.get('endDate',''))
        print()
