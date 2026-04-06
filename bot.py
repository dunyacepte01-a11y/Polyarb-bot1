import asyncio, websockets, json, os, time, random, aiohttp
from datetime import datetime
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("FUNDER_ADDRESS")
START_BALANCE = float(os.getenv("START_BALANCE","300"))
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")
THRESHOLD = 0.03
KELLY_FRACTION = 0.15
KILL_SWITCH = 0.40
PAPER_TRADE = os.getenv("PAPER_TRADE","true").lower() == "true"
PORT = int(os.getenv("PORT", 8080))

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

async def tg(session, msg):
    try:
        await session.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id":TG_CHAT,"text":msg,"parse_mode":"HTML"}
        )
    except: pass

async def handle_command(session, msg):
    global bot_active
    msg = msg.strip().lower()
    if msg in ["/durum","/status"]:
        wr = wins/trades*100 if trades > 0 else 0
        net = balance - start_balance
        mode = "PAPER" if PAPER_TRADE else "GERÇEK"
        market = current_market["title"] if current_market else "Yok"
        await tg(session, f"📊 <b>BOT DURUMU</b>\nMode: {mode}\nBakiye: ${round(balance,2)}\nNet: ${round(net,2)}\nİşlem: {trades}\nWR: %{round(wr,1)}\nMarket: {market}\nAktif: {'✅' if bot_active else '❌'}")
    elif msg in ["/durdur","/stop"]:
        bot_active = False
        await tg(session, "🛑 Bot durduruldu!")
    elif msg in ["/baslat","/start"]:
        bot_active = True
        await tg(session, "✅ Bot başlatıldı!")
    elif msg in ["/bakiye"]:
        await tg(session, f"💰 Bakiye: ${round(balance,2)}\n📈 Net: ${round(balance-start_balance,2)}")
    elif msg in ["/yardim","/help"]:
        await tg(session, "📋 <b>KOMUTLAR</b>\n/durum - Bot durumu\n/baslat - Başlat\n/durdur - Durdur\n/bakiye - Bakiye\n/yardim - Yardım")
    else:
        await tg(session, "❓ Bilinmeyen komut. /yardim yazın.")

async def telegram_polling(session):
    global tg_offset
    while True:
        try:
            async with session.get(
                f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates",
                params={"offset":tg_offset,"timeout":10},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                for update in data.get("result",[]):
                    tg_offset = update["update_id"] + 1
                    msg = update.get("message",{}).get("text","")
                    chat = str(update.get("message",{}).get("chat",{}).get("id",""))
                    if chat == TG_CHAT and msg:
                        await handle_command(session, msg)
        except: pass
        await asyncio.sleep(1)

async def fetch_market(session):
    global current_market, market_last_update
    try:
        async with session.get(
            "https://gamma-api.polymarket.com/events?tag_slug=5m&limit=100&closed=false",
            timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            data = await resp.json()
            now = time.time()
            for e in data:
                if "btc-up-or-down" not in e.get("seriesSlug",""):
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

async def get_clob_prices(session):
    if not current_market: return 0.5, 0.5
    try:
        async with session.get(f"https://clob.polymarket.com/price?token_id={current_market['up_token']}&side=BUY",timeout=aiohttp.ClientTimeout(total=2)) as r1:
            async with session.get(f"https://clob.polymarket.com/price?token_id={current_market['dn_token']}&side=BUY",timeout=aiohttp.ClientTimeout(total=2)) as r2:
                up = float((await r1.json()).get("price",0.5))
                dn = float((await r2.json()).get("price",0.5))
                return up, dn
    except: return 0.5, 0.5

def calc_true_prob():
    if len(price_history) < 3: return 0.5
    prices = price_history[-10:]
    move = (prices[-1]-prices[-3])/prices[-3]*0.7+(prices[-1]-prices[0])/prices[0]*0.3
    momentum = min(abs(move)*15, 0.08)
    return max(0.05, min(0.95, 0.5+(momentum if move > 0 else -momentum)))

def kelly_size(tp, mp):
    if mp <= 0 or mp >= 1: return 0
    b = (1/mp)-1
    f = max(0, min((tp*b-(1-tp))/b*KELLY_FRACTION, 0.20))
    return balance * f

async def execute_trade(session, direction, tp, mp, edge):
    global balance, wins, losses, trades, last_trade_time
    now = time.time()
    if now - last_trade_time < 12: return
    if not bot_active: return
    last_trade_time = now
    dd = (start_balance-balance)/start_balance
    if dd >= KILL_SWITCH:
        await tg(session, f"🚨 KILL SWITCH! Drawdown: %{round(dd*100,1)}")
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
    await tg(session, f"{icon} <b>{direction}</b> | Edge:%{round(edge*100,1)}\nPos:${round(pos,2)} PnL:${round(pnl,2)}\nBakiye:${round(balance,2)} WR:%{round(wr,1)}\nNet:${round(balance-start_balance,2)} ({trades} işlem)")

async def market_updater(session):
    while True:
        if time.time() - market_last_update > 30:
            await fetch_market(session)
        await asyncio.sleep(5)

async def trading_loop(session):
    global btc_price, price_history
    while True:
        try:
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
                            up_p, dn_p = await get_clob_prices(session)
                            true_up = calc_true_prob()
                            true_dn = 1-true_up
                            if true_up > true_dn:
                                dir2, tp, mp = "UP", true_up, up_p
                            else:
                                dir2, tp, mp = "DOWN", true_dn, dn_p
                            edge = tp-mp
                            print(f"BTC:${round(btc_price,0)} Up:{round(up_p,2)} Dn:{round(dn_p,2)} Edge:{round(edge*100,1)}%", end="\r")
                            if edge > THRESHOLD and mp > 0.05:
                                await execute_trade(session, dir2, tp, mp, edge)
                    except asyncio.TimeoutError: continue
                    except Exception as e:
                        print("WS Hata:"+str(e))
                        break
        except Exception as e:
            print("Bağlantı hatası:"+str(e))
            await asyncio.sleep(5)

async def health_server():
    from aiohttp import web
    async def handle(request):
        return web.Response(text="PolyArb Bot Running")
    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health server port {PORT}'da başladı!")

async def main():
    mode = "PAPER" if PAPER_TRADE else "GERÇEK"
    print("POLYARB BOT V10 - TAM ENTEGRE")
    try:
        creds = client.create_or_derive_api_creds()
        print("API OK: "+creds.api_key[:8])
    except Exception as e:
        print("API hata: "+str(e))
    await health_server()
    async with aiohttp.ClientSession() as session:
        await fetch_market(session)
        if current_market:
            print("Market: "+current_market["title"])
        await tg(session, f"🚀 <b>PolyArb Bot V10!</b>\nMode: {mode}\nBakiye: ${balance}\n\n/yardim - Komutlar")
        await asyncio.gather(
            market_updater(session),
            trading_loop(session),
            telegram_polling(session)
        )

asyncio.run(main())
