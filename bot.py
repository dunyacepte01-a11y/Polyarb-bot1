import asyncio, websockets, json, os, time, random, requests
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("FUNDER_ADDRESS")
START_BALANCE = float(os.getenv("START_BALANCE","300"))
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
THRESHOLD = 0.025
KELLY_FRACTION = 0.20
KILL_SWITCH = 0.40
PAPER_TRADE = os.getenv("PAPER_TRADE","true").lower() == "true"

balance = START_BALANCE
start_balance = START_BALANCE
wins = losses = trades = 0
btc_price = 0
price_history = []
last_trade_time = 0
current_market = None
market_last_update = 0
bot_active = True
tg_offset = 0
client = ClobClient(host="https://clob.polymarket.com",chain_id=137,key=PRIVATE_KEY,signature_type=0,funder=FUNDER)

def tg(msg):
    try:
        requests.post("https://api.telegram.org/bot"+TG_TOKEN+"/sendMessage",
            json={"chat_id":TG_CHAT,"text":msg,"parse_mode":"HTML"},timeout=5)
    except: pass

def handle_command(msg):
    global bot_active
    msg = msg.strip().lower()
    if msg in ["/durum","/status"]:
        wr = wins/trades*100 if trades > 0 else 0
        net = balance - start_balance
        mode = "PAPER" if PAPER_TRADE else "GERÇEK"
        market = current_market["title"] if current_market else "Yok"
        tg(f"📊 <b>BOT DURUMU</b>\nMode: {mode}\nBakiye: ${round(balance,2)}\nNet: ${round(net,2)}\nİşlem: {trades}\nWR: %{round(wr,1)}\nMarket: {market}\nAktif: {'✅' if bot_active else '❌'}")
    elif msg in ["/durdur","/stop"]:
        bot_active = False
        tg("🛑 Bot durduruldu!")
    elif msg in ["/baslat","/start"]:
        bot_active = True
        tg("✅ Bot başlatıldı!")
    elif msg in ["/bakiye"]:
        tg(f"💰 Bakiye: ${round(balance,2)}\n📈 Net: ${round(balance-start_balance,2)}")
    elif msg in ["/yardim","/help"]:
        tg("📋 <b>KOMUTLAR</b>\n/durum - Bot durumu\n/baslat - Başlat\n/durdur - Durdur\n/bakiye - Bakiye\n/yardim - Yardım")
    else:
        tg("❓ Bilinmeyen komut. /yardim yazın.")

def fetch_market():
    global current_market, market_last_update
    try:
        resp = requests.get("https://gamma-api.polymarket.com/events?tag_slug=5m&limit=50&order=startDate&ascending=false&closed=false",timeout=4)
        data = resp.json()
        now = time.time()
        for e in data:
            if "btc-updown-5m" not in e.get("seriesSlug",""):
                continue
            try:
                end_ts = datetime.fromisoformat(e["endDate"].replace("Z","+00:00")).timestamp()
                start_ts = datetime.fromisoformat(e["startDate"].replace("Z","+00:00")).timestamp()
            except: continue
            if start_ts <= now <= end_ts:
                m = e["markets"][0]
                tokens = json.loads(m.get("clobTokenIds","[]"))
                if not tokens or len(tokens) < 2: continue
                current_market = {"title":e.get("title",""),"end_ts":end_ts,"up_token":tokens[0],"dn_token":tokens[1]}
                market_last_update = now
                return True
    except: pass
    return False

def get_clob_prices():
    if not current_market: return 0.5, 0.5
    try:
        r1 = requests.get("https://clob.polymarket.com/price?token_id="+current_market["up_token"]+"&side=BUY",timeout=2)
        r2 = requests.get("https://clob.polymarket.com/price?token_id="+current_market["dn_token"]+"&side=BUY",timeout=2)
        return float(r1.json().get("price",0.5)), float(r2.json().get("price",0.5))
    except: return 0.5, 0.5

def calc_true_prob():
    if len(price_history) < 3: return 0.5
    prices = price_history[-10:]
    move = (prices[-1]-prices[-3])/prices[-3]*0.7+(prices[-1]-prices[0])/prices[0]*0.3
    momentum = min(abs(move)*120, 0.47)
    return max(0.05, min(0.95, 0.5+(momentum if move > 0 else -momentum)))

def kelly_size(tp, mp):
    if mp <= 0 or mp >= 1: return 0
    b = (1/mp)-1
    f = max(0, min((tp*b-(1-tp))/b*KELLY_FRACTION, 0.20))
    return balance * f

def execute_trade(direction, tp, mp, edge):
    global balance, wins, losses, trades, last_trade_time
    now = time.time()
    if now - last_trade_time < 12: return
    if not bot_active: return
    last_trade_time = now
    dd = (start_balance-balance)/start_balance
    if dd >= KILL_SWITCH:
        tg(f"🚨 KILL SWITCH! Drawdown: %{round(dd*100,1)}")
        return
    pos = kelly_size(tp, mp)
    if pos < 0.5: return
    b = (1/mp)-1
    win = random.random() < tp
    pnl = pos*b if win else -pos
    balance += pnl
    trades += 1
    if win: wins += 1
    else: losses += 1
    wr = wins/trades*100
    icon = "✅" if win else "❌"
    tg(f"{icon} <b>{direction}</b> | Edge:%{round(edge*100,1)}\nPos:${round(pos,2)} PnL:${round(pnl,2)}\nBakiye:${round(balance,2)} WR:%{round(wr,1)}\nNet:${round(balance-start_balance,2)} ({trades} işlem)")

async def tg_listener():
    global tg_offset
    while True:
        try:
            r = requests.get("https://api.telegram.org/bot"+TG_TOKEN+"/getUpdates",
                params={"offset":tg_offset,"timeout":1},timeout=5)
            for u in r.json().get("result",[]):
                tg_offset = u["update_id"]+1
                msg = u.get("message",{}).get("text","")
                chat = str(u.get("message",{}).get("chat",{}).get("id",""))
                if chat == TG_CHAT and msg:
                    handle_command(msg)
        except: pass
        await asyncio.sleep(2)

async def market_updater():
    while True:
        if time.time() - market_last_update > 30:
            fetch_market()
        await asyncio.sleep(5)

async def trading_loop():
    global btc_price, price_history
    async with websockets.connect("wss://stream.binance.com:9443/ws/btcusdt@aggTrade",ping_interval=20) as ws:
        print("Binance BAĞLI!")
        tick = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                d = json.loads(msg)
                btc_price = float(d["p"])
                price_history.append(btc_price)
                if len(price_history) > 50: price_history.pop(0)
                tick += 1
                if tick % 5 == 0 and current_market:
                    remaining = max(0, current_market["end_ts"]-time.time())
                    if remaining < 15: continue
                    up_p, dn_p = get_clob_prices()
                    true_up = calc_true_prob()
                    true_dn = 1-true_up
                    if true_up > true_dn:
                        dir2, tp, mp = "UP", true_up, up_p
                    else:
                        dir2, tp, mp = "DOWN", true_dn, dn_p
                    edge = tp-mp
                    print(f"BTC:${round(btc_price,0)} Up:{round(up_p,2)} Dn:{round(dn_p,2)} Edge:{round(edge*100,1)}%", end="\r")
                    if edge > THRESHOLD and mp > 0.05:
                        execute_trade(dir2, tp, mp, edge)
            except asyncio.TimeoutError: continue
            except Exception as e:
                print("Hata:"+str(e))
                await asyncio.sleep(2)
                break

async def main():
    mode = "PAPER" if PAPER_TRADE else "GERÇEK"
    print("POLYARB BOT V8")
    try:
        creds = client.create_or_derive_api_creds()
        print("API OK: "+creds.api_key[:8])
    except Exception as e:
        print("API hata: "+str(e))
    fetch_market()
    if current_market:
        print("Market: "+current_market["title"])
    tg(f"🚀 <b>PolyArb Bot V8 Başladı!</b>\nMode: {mode}\nBakiye: ${balance}\n\n/yardim - Komutlar")
    await asyncio.gather(
        tg_listener(),
        market_updater(),
        trading_loop()
    )

asyncio.run(main())
