
import requests, json, time
from datetime import datetime

resp = requests.get('https://gamma-api.polymarket.com/events?tag_slug=5m&limit=50&order=startDate&ascending=false')
data = resp.json()
now = time.time()
for e in data:
    if 'btc-up-or-down' not in e.get('seriesSlug',''):
        continue
    try:
        end_ts = datetime.fromisoformat(e['endDate'].replace('Z','+00:00')).timestamp()
        start_ts = datetime.fromisoformat(e['startDate'].replace('Z','+00:00')).timestamp()
    except:
        continue
    if start_ts <= now <= end_ts:
        m = e['markets'][0]
        tokens = json.loads(m.get('clobTokenIds','[]'))
        print('Active market:', e.get('title'))
        print('tokens:', tokens[:2])
        if tokens:
            tid = tokens[0]
            r = requests.get(f'https://clob.polymarket.com/price?token_id={tid}&side=BUY')
            print('price BUY up:', r.text)
            r2 = requests.get(f'https://clob.polymarket.com/price?token_id={tid}&side=SELL')
            print('price SELL up:', r2.text)
        break
