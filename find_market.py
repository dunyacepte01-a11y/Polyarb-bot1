
import requests
resp = requests.get('https://gamma-api.polymarket.com/markets?active=true&limit=100&closed=false')
data = resp.json()
for m in data:
    q = m.get('question','')
    if 'btc' in q.lower() or 'bitcoin' in q.lower() or 'up or down' in q.lower() or '5 minute' in q.lower():
        print(q)
        print('id:', m.get('id',''))
        print('conditionId:', m.get('conditionId',''))
        print()
