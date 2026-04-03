
import requests
resp = requests.get('https://gamma-api.polymarket.com/markets?slug=btc-5-minute-up-or-down')
print(resp.text[:2000])
resp2 = requests.get('https://gamma-api.polymarket.com/events?active=true&limit=50')
data = resp2.json()
for m in data:
    t = m.get('title','')
    if 'btc' in t.lower() or 'bitcoin' in t.lower() or 'minute' in t.lower():
        print(t)
        print(m.get('slug',''))
