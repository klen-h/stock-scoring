import requests, json, time, threading
from datetime import datetime, timedelta

_session = requests.Session()
_session.headers.update({"User-Agent": "Mozilla/5.0"})

# ===== A股代码表（静态生成，覆盖沪深主板+创业板+科创板+北交所）=====

def _build_stock_pool():
    """生成全A股可能代码列表"""
    codes = []
    # 深市主板 000001-005999
    for i in range(1, 6000):
        codes.append(("sz", f"{i:06d}"))
    # 创业板 300001-301999
    for i in range(300001, 302000):
        codes.append(("sz", f"{i:06d}"))
    # 沪市主板 600000-605999
    for i in range(600000, 606000):
        codes.append(("sh", f"{i:06d}"))
    # 科创板 688001-688999
    for i in range(688001, 689000):
        codes.append(("sh", f"{i:06d}"))
    return codes

_ALL_CODES = _build_stock_pool()
_CODE_TO_PREFIX = {}
for _prefix, _code in _ALL_CODES:
    _CODE_TO_PREFIX[_code] = _prefix

# ===== 缓存 =====
_cache = {"stocks": {}, "last_update": 0, "lock": threading.Lock()}
BATCH_SIZE = 80  # 腾讯单次最大约100


def _fetch_tencent(codes_str: str, timeout: int = 10) -> dict:
    """从腾讯获取行情，返回 {qt_code: parsed_dict} """
    url = f"https://qt.gtimg.cn/q={codes_str}"
    r = _session.get(url, timeout=timeout)
    result = {}
    for line in r.text.strip().split(";"):
        line = line.strip()
        if not line or '~' not in line:
            continue
        try:
            qt_code = line.split("=")[0].replace("v_", "")
            data = line.split('"')[1].split('~')
            if len(data) < 59:
                continue
            price = float(data[3]) if data[3] else 0
            prev_close = float(data[4]) if data[4] else 0
            result[qt_code] = {
                "code": data[2],
                "name": data[1],
                "price": price,
                "prev_close": prev_close,
                "open": float(data[5]) if data[5] else 0,
                "high": float(data[41]) if data[41] else 0,
                "low": float(data[42]) if data[42] else 0,
                "change_amt": float(data[31]) if data[31] else 0,
                "change_pct": float(data[32]) if data[32] else 0,
                "volume": float(data[6]) if data[6] else 0,
                "amount_wan": float(data[37]) if data[37] else 0,
                "amount": float(data[37]) * 10000 if data[37] else 0,
                "turnover_rate": float(data[38]) if data[38] else 0,
                "pe": float(data[39]) if data[39] else 0,
                "pb": float(data[40]) if data[40] else 0,
                "amplitude": float(data[43]) if data[43] else 0,
                "market_cap": float(data[57]) if data[57] else 0,
                "float_cap": float(data[58]) if data[58] else 0,
            }
        except (IndexError, ValueError, TypeError):
            continue
    return result


def refresh_all_stocks(force: bool = False):
    """刷新全量A股行情缓存（分批请求腾讯）"""
    with _cache["lock"]:
        if not force and time.time() - _cache["last_update"] < 60:
            return _cache["stocks"]
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始刷新全量行情...")
        stocks = {}
        total = len(_ALL_CODES)
        for i in range(0, total, BATCH_SIZE):
            batch = _ALL_CODES[i:i + BATCH_SIZE]
            codes_str = ",".join(f"{p}{c}" for p, c in batch)
            try:
                data = _fetch_tencent(codes_str, timeout=15)
                for qt_code, info in data.items():
                    if info["price"] > 0:  # 有效数据
                        stocks[info["code"]] = info
            except Exception as e:
                print(f"  批次 {i // BATCH_SIZE} 失败: {e}")
            if i % (BATCH_SIZE * 10) == 0 and i > 0:
                print(f"  进度: {i}/{total}, 已获取 {len(stocks)} 只")
        _cache["stocks"] = stocks
        _cache["last_update"] = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 刷新完成: {len(stocks)} 只股票")
        return stocks


def get_stock(code: str) -> dict:
    """获取单只股票实时行情"""
    prefix = _CODE_TO_PREFIX.get(code, "sz" if code.startswith("0") or code.startswith("3") else "sh")
    data = _fetch_tencent(f"{prefix}{code}")
    for v in data.values():
        return v
    return {}


def get_stocks_batch(codes: list) -> list:
    """批量获取股票行情"""
    codes_str = []
    for c in codes:
        prefix = _CODE_TO_PREFIX.get(c, "sz" if c.startswith("0") or c.startswith("3") else "sh")
        codes_str.append(f"{prefix}{c}")
    data = _fetch_tencent(",".join(codes_str))
    return list(data.values())


def get_index(code: str) -> dict:
    """获取指数行情"""
    prefix = "sh" if code.startswith("0") else "sz"
    data = _fetch_tencent(f"{prefix}{code}")
    for v in data.values():
        return v
    return {}


def get_kline(symbol: str, period: str = "day", start: str = "", end: str = "", count: int = 300) -> list:
    """获取K线数据
    symbol: 纯数字代码如 000001, 000300
    period: day/week/month
    返回: [{date, open, close, high, low, volume}, ...]
    """
    if not start:
        start = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y-%m-%d")
    if not end:
        end = datetime.now().strftime("%Y-%m-%d")

    # 判断市场前缀
    INDEX_MAP = {"000001": "sh", "399001": "sz", "399006": "sz", "000300": "sh", "000905": "sh", "000688": "sh"}
    if symbol in INDEX_MAP:
        prefix = INDEX_MAP[symbol]
        is_index = True
        kline_key = period
    else:
        prefix = _CODE_TO_PREFIX.get(symbol, "sh" if symbol.startswith("6") else "sz")
        is_index = False
        kline_key = f"qfq{period}"

    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": f"{prefix}{symbol},{period},{start},{end},{count},qfq"}
    try:
        r = _session.get(url, params=params, timeout=15)
        d = r.json()
        raw = d.get("data", {}).get(f"{prefix}{symbol}", {}).get(kline_key, [])
        result = []
        for item in raw:
            result.append({
                "date": item[0],
                "open": round(float(item[1]), 3),
                "close": round(float(item[2]), 3),
                "high": round(float(item[3]), 3),
                "low": round(float(item[4]), 3),
                "volume": float(item[5]),
            })
        return result
    except Exception as e:
        print(f"K线获取失败 {symbol}: {e}")
        return []


def search_stocks(keyword: str) -> list:
    """搜索股票（代码或名称），从缓存中查找"""
    stocks = _cache["stocks"]
    keyword = keyword.strip().upper()
    results = []
    for code, info in stocks.items():
        if keyword in code or keyword in info.get("name", "").upper():
            results.append({"code": code, "name": info["name"]})
            if len(results) >= 20:
                break
    # 如果缓存为空，尝试直接从腾讯获取
    if not results:
        prefix = "sz" if keyword.isdigit() and (keyword.startswith("0") or keyword.startswith("3")) else "sh"
        if keyword.isdigit():
            data = _fetch_tencent(f"{prefix}{keyword}")
            for v in data.values():
                if v["price"] > 0:
                    results.append({"code": v["code"], "name": v["name"]})
    return results


MIN_MARKET_CAP_YI = 50  # 最小市值（亿元），低于此值视为小市值


def is_gem_stock(code: str) -> bool:
    """判断是否为创业板（300xxx, 301xxx）"""
    return code.startswith("300") or code.startswith("301")


def is_star_market_stock(code: str) -> bool:
    """判断是否为科创板（688xxx）"""
    return code.startswith("688")


def is_st_stock(name: str) -> bool:
    """判断是否为ST股（包括ST、*ST、SST等）"""
    return "ST" in name.upper()


def is_small_cap_stock(market_cap_wan: float, min_yi: float = MIN_MARKET_CAP_YI) -> bool:
    """判断是否为小市值股票。market_cap_wan 单位为万元，min_yi 单位为亿元。"""
    if not market_cap_wan or market_cap_wan <= 0:
        return True
    cap_yi = market_cap_wan / 10000
    return cap_yi < min_yi


def is_loss_stock(pe: float) -> bool:
    """判断是否为亏损股票（PE <= 0）"""
    return pe is None or pe <= 0


def filter_quality_stocks(stocks: list[dict]) -> list[dict]:
    """
    过滤掉创业板、科创板、ST、小市值、亏损个股，保留优质标的。
    
    过滤条件:
      - 排除创业板（300/301开头）
      - 排除科创板（688开头）
      - 排除ST股（名称含ST）
      - 排除小市值（< 50亿）
      - 排除亏损股（PE <= 0）
    """
    result = []
    for s in stocks:
        code = s.get("code", "")
        name = s.get("name", "")
        cap = s.get("market_cap", 0)
        pe = s.get("pe", 0)

        if is_gem_stock(code):
            continue
        if is_star_market_stock(code):
            continue
        if is_st_stock(name):
            continue
        if is_small_cap_stock(cap):
            continue
        if is_loss_stock(pe):
            continue

        result.append(s)
    return result
