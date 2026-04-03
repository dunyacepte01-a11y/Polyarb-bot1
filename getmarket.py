
import requests
resp = requests.get('https://gamma-api.polymarket.com/events?slug=btc-updown-5m-1775168400')
data = resp.json()
print(data)
