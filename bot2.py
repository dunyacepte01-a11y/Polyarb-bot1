
import asyncio, websockets, json, os, time, random
from dotenv import load_dotenv
from py_clob_client.client import ClobClient

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
FUNDER = os.getenv("FUNDER_ADDRESS")
START_BALANCE = float(os.getenv("START_BALANCE", "300"))
THRESHOLD = 0.03
KELLY_FRACTION = 0.25
KILL_SWITCH = 0.40

balance = START_BALANCE
start_balance = START_BALANCE
wins = 0
losses = 0
trades = 0
btc_price = 0
prev_price = 0
poly_odds = 0.5
last_trade_time = 0

client = ClobClient(host="https://clob.polymarket.com", chain_id=137, key=PRIVATE_KEY, signature_type=0, funder=FUNDER)

def get_poly_odds():
    try:
        resp = client.get_markets()
        for m in resp.get("data", []):
            q = m.get("question","").lower()
            if "bitcoin" in q and "higher" in q:
                for t in m.get("tokens",[]):
                    if t.get("outcome","").lower() == "yes":
                        return float(t.get("price", 0.5))
    except:
        pass
    return 0.5

def kelly_size(edge, odds):
    b = (1/odds) - 1
    if b <= 0: return 0
    f = max(0, min((edge*b - (1-edge))/b * KELLY_FRACTION, 0.25))
    return balance * f

def trade(direction, tp, pp, edge):
    global balance, wins, losses, trades, last_trade_time
    now = time.time()
    if now - last_trade_time < 10: return
    last_trade_time = now
    if (start_balance - balance)/start_balance >= KILL_SWITCH:
        print("KILL SWITCH!")
        return
    pos = kelly_size(tp, pp)
    if pos < 1: return
    b = (1/pp) - 1
    win = random.random() < tp
    pnl = pos*b if win else -pos
    balance += pnl
    trades += 1
    if win: wins += 1
    else: losses += 1
    wr = wins/trades*100
    print(f"\n{'WIN' if win else 'LOSS'} | {direction} | Edge:{edge*100:.1f}% | ${pos:.2f} | PnL:{pnl:+.2f} | Bakiye:${balance:.2f} | WR:{wr:.1f}%")

async def run():
    global btc_price, prev_price, poly_odds
    print("Baslaniyor...")
    print(f"Bakiye: ${balance} | Esik: {THRESHOLD*100}%")
    try:
        creds = client.create_or_derive_api_creds()
        print(f"API OK: {creds.api_key[:8]}...")
    except Exception as e:
        print(f"API hata: {e}")
    async with websockets.connect("wss://stream.binance.com:9443/ws/btcusdt@trade") as ws:
        print("Binance bagli!")
        tick = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(msg)
                prev_price = btc_price
                btc_price = float(d["p"])
                tick += 1
                if tick % 10 == 0 and prev_price > 0:
                    poly_odds = get_poly_odds()
                    move = (btc_price - prev_price)/prev_price
                    tp_down = max(0.05, min(0.95, 0.5 + min(abs(move)*80,0.45)*(-1 if move>0 else 1)))
                    dir = "DOWN" if tp_down > 0.5 else "UP"
                    tp = tp_down if dir=="DOWN" else 1-tp_down
                    pp = poly_odds if dir=="DOWN" else 1-poly_odds
                    edge = tp - pp
                    print(f"BTC:${btc_price:,.0f} Poly:{poly_odds:.2f} Edge:{edge*100:.1f}%", end="\r")
                    if edge > THRESHOLD:
                        trade(dir, tp, pp, edge)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Hata:{e}")
                break

asyncio.run(run())
