
import requests, json
resp = requests.get('https://gamma-api.polymarket.com/events?slug=btc-updown-5m-1775168400')
data = resp.json()
m = data[0]['markets'][0]
print('question:', m['question'])
print('conditionId:', m['conditionId'])
print('clobTokenIds:', m['clobTokenIds'])
print('outcomePrices:', m['outcomePrices'])
print('outcomes:', m['outcomes'])
