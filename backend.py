import asyncio, json, random, time, os
import yfinance as yf
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ponytail: alpaca handles real API trading trivially without manual auth headers
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
except ImportError:
    TradingClient = None

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(tick_generator())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def root():
    return {"status": "running"}

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ponytail: mock keys for now, use env vars on real server.
API_KEY = os.getenv("ALPACA_KEY", "mock")
API_SECRET = os.getenv("ALPACA_SECRET", "mock")
trading_client = TradingClient(API_KEY, API_SECRET, paper=True) if TradingClient and API_KEY != "mock" else None

class StockTick(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=5)
    price: float = Field(..., gt=0)
    timestamp: float
    volume: int = Field(..., ge=0)

clients = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    try:
        while True: await websocket.receive_text()
    except:
        clients.remove(websocket)

async def tick_generator():
    price = 150.0
    while True:
        # ponytail: keeping the high-perf generator, polling yfinance 100x a second gets you IP banned.
        batch = []
        for _ in range(100):
            price += random.uniform(-0.5, 0.5)
            batch.append(StockTick(symbol="NVDA", price=price, timestamp=time.time(), volume=random.randint(10, 100)).model_dump())
        if clients:
            msg = json.dumps(batch)
            for client in list(clients):
                try: await client.send_text(msg)
                except: clients.remove(client)
        await asyncio.sleep(0.1)

@app.post("/trade/{symbol}")
def auto_trade(symbol: str, qty: int = 1):
    if not trading_client: return {"status": "mocked", "msg": "Set ALPACA_KEY env var to trade."}
    # ponytail: Market order is 1 line. Custom limit strategies are yagni until this runs.
    order = MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
    return trading_client.submit_order(order)

@app.get("/screener")
def screener():
    # ponytail: standard lib / basic yfinance call. No complex web scraping needed.
    return {k: v.info.get('regularMarketPrice') for k, v in yf.Tickers("AAPL MSFT NVDA").tickers.items()}

@app.get("/news/{symbol}")
def analyze_news(symbol: str):
    # ponytail: naive keyword counting instead of a heavy LLM. Add NLP ONLY when this fails.
    news = yf.Ticker(symbol).news
    good, bad = ["surge", "beat", "up", "growth"], ["miss", "down", "drop", "loss"]
    for n in news:
        title = n['title'].lower()
        score = sum(1 for w in good if w in title) - sum(1 for w in bad if w in title)
        n['sentiment'] = "BULL" if score > 0 else "BEAR" if score < 0 else "NEUTRAL"
    return news

# ponytail: lifespan handles startup now

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
