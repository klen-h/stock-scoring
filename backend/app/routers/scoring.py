from fastapi import APIRouter, Query, BackgroundTasks
from app.scoring.engine import ScoreEngine
from app.tencent import get_stock, get_kline, _cache, get_stocks_batch

router = APIRouter()
engine = ScoreEngine()


@router.get("/{symbol}")
async def score_single(symbol: str):
    """单只股票综合评分"""
    # 并行获取三类数据
    stock_info = get_stock(symbol)
    if not stock_info:
        return {"error": f"未找到股票 {symbol}"}

    technical_data = get_kline(symbol, period="day", count=500)
    # 复用 stock.py 的技术指标计算
    if len(technical_data) >= 30:
        from app.routers.stock import stock_technical
        # 直接调用内部函数构建技术指标
        technical_data = _calc_technical(technical_data)

    fundamental = {
        "valuation": {
            "市盈率(动态)": stock_info.get("pe", 0),
            "市净率": stock_info.get("pb", 0),
            "总市值(亿)": round(stock_info.get("market_cap", 0) / 10000, 2),
            "流通市值(亿)": round(stock_info.get("float_cap", 0) / 10000, 2),
        },
        "financial": {
            "换手率": stock_info.get("turnover_rate", 0),
        },
    }

    result = engine.score_stock(
        code=symbol,
        name=stock_info.get("name", ""),
        technical_data=technical_data,
        stock_info=stock_info,
        fundamental=fundamental,
    )

    return {
        "code": result.code,
        "name": result.name,
        "total_score": result.total_score,
        "signal": result.signal,
        "signal_level": result.signal_level,
        "dimensions": result.dimensions,
        "factors_up": result.factors_up,
        "factors_down": result.factors_down,
        "summary": result.summary,
    }


@router.get("/batch/top")
async def score_top(
    limit: int = Query(default=50, ge=10, le=200),
    background_tasks: BackgroundTasks = None,
):
    """对全量缓存的股票批量评分，返回 Top N"""
    stocks = _cache.get("stocks", {})
    if not stocks:
        # 触发后台刷新
        if background_tasks:
            from app.tencent import refresh_all_stocks
            background_tasks.add_task(refresh_all_stocks)
        return {"data": [], "total": 0, "cache_status": "loading"}

    stock_list = list(stocks.values())
    # 过滤掉停牌/异常
    valid = [s for s in stock_list if s.get("price", 0) > 0 and s.get("change_pct") is not None]

    results = engine.score_batch(valid)
    top = results[:limit]

    return {
        "data": [{
            "code": r.code,
            "name": r.name,
            "total_score": r.total_score,
            "signal": r.signal,
            "signal_level": r.signal_level,
        } for r in top],
        "total": len(results),
        "cache_status": "ready",
    }


@router.get("/batch/bottom")
async def score_bottom(
    limit: int = Query(default=50, ge=10, le=200),
):
    """返回评分最低的 N 只（适合做空/回避）"""
    stocks = _cache.get("stocks", {})
    if not stocks:
        return {"data": [], "total": 0, "cache_status": "loading"}

    stock_list = [s for s in stocks.values() if s.get("price", 0) > 0]
    results = engine.score_batch(stock_list)
    bottom = results[-limit:]
    bottom.reverse()  # 最低分排最前

    return {
        "data": [{
            "code": r.code,
            "name": r.name,
            "total_score": r.total_score,
            "signal": r.signal,
            "signal_level": r.signal_level,
        } for r in bottom],
        "total": len(results),
        "cache_status": "ready",
    }


@router.get("/batch/signal")
async def score_by_signal(
    signal: str = Query(default="买入", description="信号类型：强烈买入/买入/观望/卖出/强烈卖出"),
    limit: int = Query(default=50, ge=10, le=200),
):
    """按信号类型筛选"""
    stocks = _cache.get("stocks", {})
    if not stocks:
        return {"data": [], "total": 0, "signal": signal}

    stock_list = [s for s in stocks.values() if s.get("price", 0) > 0]
    results = engine.score_batch(stock_list)
    filtered = [r for r in results if r.signal == signal][:limit]

    return {
        "data": [{
            "code": r.code,
            "name": r.name,
            "total_score": r.total_score,
            "signal": r.signal,
            "signal_level": r.signal_level,
        } for r in filtered],
        "total": len([r for r in results if r.signal == signal]),
        "signal": signal,
    }


# ================================================================
#  内部技术指标计算（复用 stock.py 的逻辑）
# ================================================================

def _calc_technical(klines: list) -> list:
    """从K线计算技术指标（与 stock.py 的 /technical/ 端点逻辑一致）"""
    if len(klines) < 30:
        return klines

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k["volume"] for k in klines]
    n = len(closes)

    def ma(data, window):
        result = [None] * (window - 1)
        for i in range(window - 1, len(data)):
            result.append(round(sum(data[i - window + 1:i + 1]) / window, 3))
        return result

    def ema(data, span):
        result = [data[0]]
        k = 2 / (span + 1)
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result

    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [round(ema12[i] - ema26[i], 4) for i in range(n)]
    dea_raw = ema(dif, 9)
    dea = [round(v, 4) for v in dea_raw]
    macd_hist = [round((dif[i] - dea[i]) * 2, 4) for i in range(n)]

    delta = [closes[i] - closes[i - 1] for i in range(1, n)]
    rsi_vals = [None] * n
    for i in range(14, n):
        gains = [d for d in delta[i - 13:i + 1] if d > 0]
        losses = [-d for d in delta[i - 13:i + 1] if d < 0]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rsi_vals[i] = round(100 - 100 / (1 + avg_gain / avg_loss), 2) if avg_loss > 0 else 100.0

    k_list, d_list = [None] * n, [None] * n
    k_list[18], d_list[18] = 50.0, 50.0
    for i in range(19, n):
        low9 = min(lows[i - 8:i + 1])
        high9 = max(highs[i - 8:i + 1])
        rsv = (closes[i] - low9) / (high9 - low9) * 100 if high9 != low9 else 50
        k_list[i] = round(2 / 3 * (k_list[i - 1] or 50) + 1 / 3 * rsv, 2)
        d_list[i] = round(2 / 3 * (d_list[i - 1] or 50) + 1 / 3 * k_list[i], 2)
    j_list = [round(3 * (k_list[i] or 50) - 2 * (d_list[i] or 50), 2) for i in range(n)]

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
            "date": klines[i]["date"],
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
