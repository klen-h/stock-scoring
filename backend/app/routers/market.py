from fastapi import APIRouter, Query, BackgroundTasks
from datetime import datetime
from app.tencent import (
    get_index, refresh_all_stocks, get_kline,
    _cache, BATCH_SIZE, _ALL_CODES, filter_quality_stocks,
)

router = APIRouter()

MAIN_INDICES = [
    ("sh", "000001", "上证指数"),
    ("sz", "399001", "深证成指"),
    ("sz", "399006", "创业板指"),
    ("sh", "000300", "沪深300"),
    ("sh", "000905", "中证500"),
    ("sh", "000688", "科创50"),
]


@router.get("/overview")
async def market_overview(background_tasks: BackgroundTasks):
    """市场概览：大盘指数 + 涨跌统计"""
    result = {"indices": [], "stats": {}}

    # 主要指数
    try:
        from app.tencent import _fetch_tencent
        codes_str = ",".join(f"{p}{c}" for p, c, _ in MAIN_INDICES)
        data = _fetch_tencent(codes_str)
        for prefix, code, name in MAIN_INDICES:
            qt_code = f"{prefix}{code}"
            info = data.get(qt_code)
            if info and info["price"] > 0:
                result["indices"].append({
                    "name": name,
                    "code": code,
                    "price": info["price"],
                    "change_pct": info["change_pct"],
                    "change_amt": info["change_amt"],
                    "volume": info["volume"],
                    "amount": info["amount"],
                })
    except Exception as e:
        print(f"指数数据失败: {e}")

    # 市场统计（从缓存获取）
    stocks = _cache.get("stocks", {})
    if stocks:
        total = len(stocks)
        up = sum(1 for s in stocks.values() if s["change_pct"] > 0)
        down = sum(1 for s in stocks.values() if s["change_pct"] < 0)
        flat = total - up - down
        limit_up = sum(1 for s in stocks.values() if s["change_pct"] >= 9.9)
        limit_down = sum(1 for s in stocks.values() if s["change_pct"] <= -9.9)
        changes = [s["change_pct"] for s in stocks.values()]
        result["stats"] = {
            "total": total,
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "limit_up": limit_up,
            "limit_down": limit_down,
            "avg_change_pct": round(sum(changes) / len(changes), 2) if changes else 0,
            "median_change_pct": round(sorted(changes)[len(changes) // 2], 2) if changes else 0,
            "total_amount": round(sum(s["amount"] for s in stocks.values()), 2),
        }

    # 后台刷新缓存
    if not stocks or datetime.now().timestamp() - _cache.get("last_update", 0) > 120:
        background_tasks.add_task(refresh_all_stocks)

    return result


@router.get("/realtime")
async def market_realtime(
    page: int = 1, size: int = 50,
    sort_by: str = "change_pct", order: str = "desc"
):
    """全A股实时行情分页（已过滤创业板/科创板/ST/小市值/亏损）"""
    stocks = _cache.get("stocks", {})
    if not stocks:
        return {"data": [], "total": 0, "page": page, "size": size, "cache_status": "loading"}

    stock_list = list(stocks.values())
    # 过滤创业板/科创板/ST/小市值/亏损
    stock_list = filter_quality_stocks(stock_list)

    # 排序
    sort_map = {
        "change_pct": "change_pct", "涨跌幅": "change_pct",
        "amount": "amount", "成交额": "amount",
        "turnover_rate": "turnover_rate", "换手率": "turnover_rate",
        "amplitude": "amplitude", "振幅": "amplitude",
        "price": "price", "最新价": "price",
        "volume": "volume", "成交量": "volume",
    }
    sort_key = sort_map.get(sort_by, "change_pct")
    reverse = order != "asc"
    stock_list.sort(key=lambda x: x.get(sort_key) or 0, reverse=reverse)

    total = len(stock_list)
    start = (page - 1) * size
    page_data = stock_list[start:start + size]

    return {
        "data": page_data,
        "total": total,
        "page": page,
        "size": size,
        "cache_status": "ready",
    }


@router.get("/index-kline/{symbol}")
async def index_kline(symbol: str, period: str = "day"):
    """大盘指数K线"""
    return get_kline(symbol, period=period, count=180)


@router.get("/refresh-status")
async def refresh_status():
    """缓存刷新状态"""
    stocks = _cache.get("stocks", {})
    last = _cache.get("last_update", 0)
    return {
        "stock_count": len(stocks),
        "last_update": datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M:%S") if last else "未刷新",
        "total_codes": len(_ALL_CODES),
    }


@router.get("/trigger-refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """手动触发刷新"""
    background_tasks.add_task(refresh_all_stocks, force=True)
    return {"status": "refreshing"}
