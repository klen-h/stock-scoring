from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import market, stock, capital, sector, scoring

app = FastAPI(title="A股数据评分系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api/market", tags=["市场行情"])
app.include_router(stock.router, prefix="/api/stock", tags=["个股数据"])
app.include_router(capital.router, prefix="/api/capital", tags=["资金流向"])
app.include_router(sector.router, prefix="/api/sector", tags=["板块数据"])
app.include_router(scoring.router, prefix="/api/score", tags=["评分数据"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "stock-scoring-backend"}
