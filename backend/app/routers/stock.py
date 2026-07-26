from fastapi import APIRouter, Query
from datetime import datetime
import numpy as np
from app.tencent import get_stock, get_kline, search_stocks, _CODE_TO_PREFIX

router = APIRouter()


@router.get("/kline/{symbol}")
async def stock_kline(symbol: str, period: str = "day"):
    """个股K线"""
    return get_kline(symbol, period=period)


@router.get("/realtime/{symbol}")
async def stock_realtime(symbol: str):
    """个股实时行情"""
    return get_stock(symbol)


@router.get("/search")
async def stock_search(keyword: str = Query(default="")):
    """股票搜索"""
    if not keyword:
        return []
    return search_stocks(keyword)


@router.get("/technical/{symbol}")
async def stock_technical(symbol: str, period: str = "day"):
    """技术指标：MA/MACD/KDJ/RSI/BOLL"""
    klines = get_kline(symbol, period=period, count=500)
    if len(klines) < 30:
        return []

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    dates = [k["date"] for k in klines]
    n = len(closes)

    def ma(data, window):
        result = [None] * (window - 1)
        for i in range(window - 1, len(data)):
            result.append(round(sum(data[i - window + 1:i + 1]) / window, 3))
        return result

    # MA
    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)

    # EMA
    def ema(data, span):
        result = [data[0]]
        k = 2 / (span + 1)
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result

    # MACD
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [round(ema12[i] - ema26[i], 4) for i in range(n)]
    dea_raw = ema(dif, 9)
    dea = [round(v, 4) for v in dea_raw]
    macd_hist = [round((dif[i] - dea[i]) * 2, 4) for i in range(n)]

    # RSI(14)
    delta = [closes[i] - closes[i - 1] for i in range(1, n)]
    rsi_vals = [None] * n
    for i in range(14, n):
        gains = [d for d in delta[i - 13:i + 1] if d > 0]
        losses = [-d for d in delta[i - 13:i + 1] if d < 0]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rsi_vals[i] = round(100 - 100 / (1 + avg_gain / avg_loss), 2) if avg_loss > 0 else 100.0

    # KDJ(9,3,3)
    k_list, d_list = [None] * n, [None] * n
    k_list[18], d_list[18] = 50.0, 50.0
    for i in range(19, n):
        low9 = min(lows[i - 8:i + 1])
        high9 = max(highs[i - 8:i + 1])
        rsv = (closes[i] - low9) / (high9 - low9) * 100 if high9 != low9 else 50
        k_list[i] = round(2 / 3 * (k_list[i - 1] or 50) + 1 / 3 * rsv, 2)
        d_list[i] = round(2 / 3 * (d_list[i - 1] or 50) + 1 / 3 * k_list[i], 2)
    j_list = [round(3 * (k_list[i] or 50) - 2 * (d_list[i] or 50), 2) for i in range(n)]

    # BOLL(20,2)
    boll_mid_raw = ma(closes, 20)
    boll_mid = [v if v is not None else closes[i] for i, v in enumerate(boll_mid_raw)]
    boll_upper, boll_lower = [], []
    for i in range(n):
        if i >= 19:
            std = (sum((closes[j] - boll_mid[i]) ** 2 for j in range(i - 19, i + 1)) / 20) ** 0.5
            boll_upper.append(round(boll_mid[i] + 2 * std, 3))
            boll_lower.append(round(boll_mid[i] - 2 * std, 3))
        else:
            boll_upper.append(None)
            boll_lower.append(None)

    result = []
    for i in range(n):
        result.append({
            "date": dates[i],
            "close": closes[i],
            "open": klines[i]["open"],
            "high": highs[i],
            "low": lows[i],
            "volume": volumes[i],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i], "ma60": ma60[i],
            "dif": dif[i], "dea": dea[i], "macd": macd_hist[i],
            "rsi": rsi_vals[i],
            "k": k_list[i], "d": d_list[i], "j": j_list[i],
            "boll_upper": boll_upper[i], "boll_mid": boll_mid[i], "boll_lower": boll_lower[i],
        })
    return result


@router.get("/fundamental/{symbol}")
async def stock_fundamental(symbol: str):
    """基本面（从实时数据取PE/PB/市值等可用指标）"""
    info = get_stock(symbol)
    if not info:
        return {"valuation": {}, "financial": {}}
    return {
        "valuation": {
            "市盈率(动态)": info.get("pe", 0),
            "市净率": info.get("pb", 0),
            "总市值(亿)": round(info.get("market_cap", 0) / 10, 2) if info.get("market_cap") else 0,
            "流通市值(亿)": round(info.get("float_cap", 0) / 10, 2) if info.get("float_cap") else 0,
        },
        "financial": {
            "换手率": info.get("turnover_rate", 0),
        },
    }
