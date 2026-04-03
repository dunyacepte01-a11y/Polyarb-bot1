
import requests, json
resp = requests.get('https://gamma-api.polymarket.com/events?tag_slug=5m&limit=50&order=startDate&ascending=false')
data = resp.json()
import time
now = time.time()
from datetime import datetime, timezone
for e in data:
    if 'btc-up-or-down' not in e.get('seriesSlug',''):
        continue
    end = e.get('endDate','')
    start = e.get('startDate','')
    try:
        end_ts = datetime.fromisoformat(end.replace('Z','+00:00')).timestamp()
        start_ts = datetime.fromisoformat(start.replace('Z','+00:00')).timestamp()
    except:
        continue
    if start_ts <= now <= end_ts:
        m = e['markets'][0]
        tokens = json.loads(m.get('clobTokenIds','[]'))
        print('tokens:', tokens)
        if tokens:
            r = requests.get(f'https://clob.polymarket.com/midpoints?token_id={tokens[0]}')
            print('midpoint up:', r.json())
            if len(tokens)>1:
                r2 = requests.get(f'https://clob.polymarket.com/midpoints?token_id={tokens[1]}')
                print('midpoint dn:', r2.json())
        break
