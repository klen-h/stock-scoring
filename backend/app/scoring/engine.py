"""
A股多因子评分引擎

基于技术指标 + 资金面 + 基本面三个维度计算综合评分。
每项满分100，加权汇总后生成综合评分及买卖信号。

评分体系:
  技术面 (40%): MA趋势 / MACD动量 / RSI强弱 / KDJ超买超卖 / 布林带位置
  资金面 (25%): 量价配合 / 涨跌幅动量 / 换手率活跃度 / 成交额强度
  基本面 (35%): PE估值 / PB估值 / 市值规模 / 振幅

信号判定:
  综合分 >= 80  → 强烈买入
  综合分 >= 65  → 买入
  综合分 45-65  → 观望
  综合分 <= 35  → 卖出
  综合分 <= 20  → 强烈卖出
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DimensionScore:
    """单一维度的评分结果"""
    name: str
    score: float           # 0~100
    weight: float          # 权重 0~1
    weighted_score: float  # 加权分
    details: dict = field(default_factory=dict)  # 各子项明细


@dataclass
class ScoreResult:
    """综合评分结果"""
    code: str = ""
    name: str = ""
    total_score: float = 0.0
    signal: str = "观望"
    signal_level: int = 0       # -2 ~ +2
    dimensions: list = field(default_factory=list)
    summary: str = ""
    factors_up: list = field(default_factory=list)
    factors_down: list = field(default_factory=list)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _score_in_range(val: float, good_lo: float, good_hi: float,
                    bad_lo: float = None, bad_hi: float = None) -> float:
    """将值映射到 0~100 分。在 good_lo~good_hi 区间得满分，越远离越低。"""
    if good_lo <= val <= good_hi:
        return 100.0
    if val < good_lo:
        span = good_lo - (bad_lo if bad_lo is not None else good_lo - 50)
        if span <= 0:
            return 50.0
        return _clamp(round((val - (bad_lo if bad_lo is not None else good_lo - span)) / span * 100, 1))
    else:
        span = (bad_hi if bad_hi is not None else good_hi + 50) - good_hi
        if span <= 0:
            return 50.0
        return _clamp(round(((bad_hi if bad_hi is not None else good_hi + span) - val) / span * 100, 1))


class ScoreEngine:
    """多因子评分引擎"""

    # ── 权重配置 ──
    W_TECHNICAL = 0.40
    W_CAPITAL   = 0.25
    W_FUNDAMENTAL = 0.35

    def __init__(self):
        pass

    # ================================================================
    #  对外接口
    # ================================================================

    def score_stock(self, code: str, name: str = "",
                    technical_data: list | None = None,
                    stock_info: dict | None = None,
                    fundamental: dict | None = None) -> ScoreResult:
        """
        计算单只股票的综合评分。

        参数:
            code:            股票代码
            name:            股票名称
            technical_data:  /api/stock/technical/{code} 返回的数组（需至少 60 条）
            stock_info:      /api/stock/realtime/{code} 返回的 dict
            fundamental:     /api/stock/fundamental/{code} 返回的 dict
        """
        technical_data = technical_data or []
        stock_info = stock_info or {}
        fundamental = fundamental or {}

        dim_tech = self._score_technical(technical_data)
        dim_cap  = self._score_capital(technical_data, stock_info)
        dim_fund = self._score_fundamental(stock_info, fundamental)

        dimensions = [dim_tech, dim_cap, dim_fund]
        total = sum(d.weighted_score for d in dimensions)
        total = round(total, 1)

        signal, signal_level = self._derive_signal(total, dimensions)
        factors_up, factors_down = self._extract_factors(dimensions)
        summary = self._build_summary(name or code, total, signal, factors_up, factors_down)

        return ScoreResult(
            code=code, name=name,
            total_score=total,
            signal=signal,
            signal_level=signal_level,
            dimensions=[{
                "name": d.name, "score": d.score,
                "weight": d.weight, "weighted_score": d.weighted_score,
                "details": d.details,
            } for d in dimensions],
            summary=summary,
            factors_up=factors_up,
            factors_down=factors_down,
        )

    def score_batch(self, stocks: list[dict], technical_cache: dict | None = None) -> list[ScoreResult]:
        """
        批量评分。stocks 来自全量缓存列表，每个 dict 包含 tencent.py 的字段。
        返回按 total_score 降序排列的 ScoreResult 列表。
        """
        technical_cache = technical_cache or {}
        results = []
        for s in stocks:
            code = s.get("code", "")
            name = s.get("name", "")
            tech = technical_cache.get(code, [])
            # 批量模式只能用 stock_info，不逐个拉 technical
            if not tech:
                # 用有限信息做简化评分
                result = self._score_from_realtime(code, name, s)
            else:
                result = self.score_stock(code, name, tech, s)
            results.append(result)
        results.sort(key=lambda r: r.total_score, reverse=True)
        return results

    # ================================================================
    #  技术面评分 (40%)
    # ================================================================

    def _score_technical(self, tech_data: list) -> DimensionScore:
        """技术面：MA趋势 / MACD / RSI / KDJ / BOLL"""
        details = {}
        sub_scores = []

        if len(tech_data) < 30:
            return DimensionScore("技术面", 50.0, self.W_TECHNICAL,
                                  round(50.0 * self.W_TECHNICAL, 1),
                                  {"说明": "数据不足，中性评分"})

        latest = tech_data[-1]
        prev   = tech_data[-2] if len(tech_data) >= 2 else latest
        price  = latest.get("close", 0)

        # ── 1. MA 均线趋势 (25 分) ──
        ma_score = self._score_ma(latest, tech_data)
        details["MA趋势"] = {"分值": ma_score, "满分": 25}
        sub_scores.append((ma_score, 25))

        # ── 2. MACD 动量 (25 分) ──
        macd_score = self._score_macd(latest, prev, tech_data)
        details["MACD动量"] = {"分值": macd_score, "满分": 25}
        sub_scores.append((macd_score, 25))

        # ── 3. RSI 强弱 (20 分) ──
        rsi_score = self._score_rsi(latest)
        details["RSI强弱"] = {"分值": rsi_score, "满分": 20}
        sub_scores.append((rsi_score, 20))

        # ── 4. KDJ (15 分) ──
        kdj_score = self._score_kdj(latest, prev)
        details["KDJ指标"] = {"分值": kdj_score, "满分": 15}
        sub_scores.append((kdj_score, 15))

        # ── 5. BOLL 布林带 (15 分) ──
        boll_score = self._score_boll(latest)
        details["布林带"] = {"分值": boll_score, "满分": 15}
        sub_scores.append((boll_score, 15))

        raw = sum(s * w / 100 for s, w in sub_scores)
        score = _clamp(round(raw, 1))
        return DimensionScore("技术面", score, self.W_TECHNICAL,
                              round(score * self.W_TECHNICAL, 1), details)

    def _score_ma(self, latest: dict, tech_data: list) -> float:
        """MA 趋势：价格在均线上方且均线多头排列得分高"""
        price = latest.get("close", 0)
        ma5  = latest.get("ma5")
        ma10 = latest.get("ma10")
        ma20 = latest.get("ma20")
        ma60 = latest.get("ma60")

        if not all([ma5, ma10, ma20]):
            return 50.0

        score = 50.0
        # 价格在 MA5 上方
        if ma5 and price > ma5:
            score += 5
        # 价格在 MA20 上方
        if ma20 and price > ma20:
            score += 5
        # 多头排列 MA5 > MA10 > MA20
        if ma5 and ma10 and ma20 and ma5 > ma10 > ma20:
            score += 8
        elif ma5 and ma10 and ma5 > ma10:
            score += 4
        # MA60 支撑
        if ma60 and price > ma60:
            score += 4
        elif ma60 and price > ma60 * 0.97:  # 接近 MA60
            score += 2
        # MA5 上穿 MA10（金叉）
        if len(tech_data) >= 2:
            prev = tech_data[-2]
            p_ma5, p_ma10 = prev.get("ma5"), prev.get("ma10")
            if p_ma5 and p_ma10 and ma5 and ma10:
                if p_ma5 <= p_ma10 and ma5 > ma10:
                    score += 3  # 金叉加分

        return _clamp(score, 0, 25)

    def _score_macd(self, latest: dict, prev: dict, tech_data: list) -> float:
        """MACD：DIF/DEA 多空 + 金叉死叉 + 柱状体趋势"""
        dif  = latest.get("dif")
        dea  = latest.get("dea")
        macd = latest.get("macd")

        if dif is None or dea is None:
            return 50.0

        score = 50.0

        # DIF 在零轴上方
        if dif > 0:
            score += 5
        else:
            score -= 5

        # MACD 柱状体为正
        if macd is not None and macd > 0:
            score += 4
            # 柱状体放大
            prev_macd = prev.get("macd")
            if prev_macd is not None and macd > prev_macd:
                score += 3
        elif macd is not None:
            score -= 4

        # DIF > DEA（多头）
        if dif > dea:
            score += 4
        else:
            score -= 4

        # 金叉/死叉判定
        p_dif, p_dea = prev.get("dif"), prev.get("dea")
        if p_dif is not None and p_dea is not None:
            if p_dif <= p_dea and dif > dea:
                score += 5   # 金叉
            elif p_dif >= p_dea and dif < dea:
                score -= 5   # 死叉

        # 连续 N 日 MACD 为正（趋势确认）
        if len(tech_data) >= 5:
            positive_days = 0
            for i in range(-5, 0):
                m = tech_data[i].get("macd")
                if m is not None and m > 0:
                    positive_days += 1
            if positive_days >= 5:
                score += 4
            elif positive_days >= 3:
                score += 2

        return _clamp(score, 0, 25)

    def _score_rsi(self, latest: dict) -> float:
        """RSI：超买扣分、超卖加分、中间区域中性"""
        rsi = latest.get("rsi")
        if rsi is None:
            return 50.0

        if rsi >= 80:
            return 10.0   # 严重超买
        elif rsi >= 70:
            return 30.0   # 超买
        elif rsi >= 60:
            return 85.0   # 强势但未超买
        elif rsi >= 40:
            return 65.0   # 中性偏强
        elif rsi >= 30:
            return 75.0   # 接近超卖，可能有反弹
        elif rsi >= 20:
            return 90.0   # 超卖，反弹概率大
        else:
            return 60.0   # 极度超卖，但风险也大

    def _score_kdj(self, latest: dict, prev: dict) -> float:
        """KDJ：金叉/死叉 + 超买超卖 + J值极端"""
        k = latest.get("k")
        d = latest.get("d")
        j = latest.get("j")

        if k is None or d is None:
            return 50.0

        score = 50.0

        # K > D（多头）
        if k > d:
            score += 3
        else:
            score -= 3

        # 金叉/死叉
        p_k, p_d = prev.get("k"), prev.get("d")
        if p_k is not None and p_d is not None:
            if p_k <= p_d and k > d:
                score += 5   # 金叉
            elif p_k >= p_d and k < d:
                score -= 5   # 死叉

        # J 值极端判断
        if j is not None:
            if j > 100:
                score -= 4   # 超买区域
            elif j < 0:
                score += 4   # 超卖区域

        # K/D 位置
        if k < 20 and d < 20:
            score += 3  # 低位
        elif k > 80 and d > 80:
            score -= 3  # 高位

        return _clamp(score, 0, 15)

    def _score_boll(self, latest: dict) -> float:
        """布林带：价格在中轨上方、带宽收窄、接近下轨加分"""
        price = latest.get("close", 0)
        upper = latest.get("boll_upper")
        mid   = latest.get("boll_mid")
        lower = latest.get("boll_lower")

        if not all([upper, mid, lower]) or price <= 0:
            return 50.0

        score = 50.0
        bandwidth = upper - lower

        if bandwidth <= 0:
            return 50.0

        # 价格在布林带中的相对位置 (0=下轨, 1=上轨)
        position = (price - lower) / bandwidth

        if position > 0.8:
            score -= 3   # 接近上轨，压力
        elif position > 0.6:
            score += 2   # 偏强
        elif position > 0.4:
            score += 4   # 中间偏上，健康
        elif position > 0.2:
            score += 3   # 中间偏下
        elif position > 0:
            score += 5   # 接近下轨，支撑
        else:
            score += 3   # 跌破下轨，可能反弹但也危险

        # 价格在中轨上方
        if price > mid:
            score += 2

        # 带宽收窄（变盘前兆）
        if len(bw_history := [d.get("boll_upper", 0) - d.get("boll_lower", 0)
                              for d in [latest] if d.get("boll_upper")]) == 0:
            pass  # 无法判断

        return _clamp(score, 0, 15)

    # ================================================================
    #  资金面/量价评分 (25%)
    # ================================================================

    def _score_capital(self, tech_data: list, stock_info: dict) -> DimensionScore:
        """资金面：量价配合 / 涨跌幅动量 / 换手率 / 成交额"""
        details = {}
        sub_scores = []

        # ── 1. 量价配合 (30 分) ──
        vol_price_score = self._score_volume_price(tech_data, stock_info)
        details["量价配合"] = {"分值": vol_price_score, "满分": 30}
        sub_scores.append((vol_price_score, 30))

        # ── 2. 涨跌幅动量 (25 分) ──
        momentum_score = self._score_momentum(tech_data, stock_info)
        details["涨跌动量"] = {"分值": momentum_score, "满分": 25}
        sub_scores.append((momentum_score, 25))

        # ── 3. 换手率活跃度 (20 分) ──
        turnover_score = self._score_turnover(stock_info)
        details["换手率"] = {"分值": turnover_score, "满分": 20}
        sub_scores.append((turnover_score, 20))

        # ── 4. 成交额强度 (25 分) ──
        amount_score = self._score_amount(tech_data, stock_info)
        details["成交额"] = {"分值": amount_score, "满分": 25}
        sub_scores.append((amount_score, 25))

        raw = sum(s * w / 100 for s, w in sub_scores)
        score = _clamp(round(raw, 1))
        return DimensionScore("资金面", score, self.W_CAPITAL,
                              round(score * self.W_CAPITAL, 1), details)

    def _score_volume_price(self, tech_data: list, stock_info: dict) -> float:
        """量价配合：放量上涨 / 缩量下跌为佳"""
        if len(tech_data) < 10:
            return 50.0

        score = 50.0
        recent = tech_data[-5:]

        # 最近 5 日量价趋势
        up_vol = 0   # 上涨日成交量
        down_vol = 0 # 下跌日成交量
        up_days = 0
        down_days = 0

        for i, d in enumerate(recent):
            if i == 0:
                continue
            chg = d["close"] - recent[i - 1]["close"]
            vol = d["volume"]
            if chg > 0:
                up_vol += vol
                up_days += 1
            elif chg < 0:
                down_vol += vol
                down_days += 1

        # 放量上涨
        if up_days > 0 and down_days > 0 and down_vol > 0:
            ratio = up_vol / down_vol
            if ratio > 2.0:
                score += 15
            elif ratio > 1.5:
                score += 10
            elif ratio > 1.0:
                score += 5
            else:
                score -= 5
        elif up_days > 0 and down_days == 0:
            score += 10  # 全部上涨
        elif down_days > 0 and up_days == 0:
            score -= 10  # 全部下跌

        # 今日放量
        if len(tech_data) >= 2:
            vol_today = tech_data[-1]["volume"]
            vol_avg5 = sum(d["volume"] for d in tech_data[-6:-1]) / 5
            if vol_avg5 > 0:
                vol_ratio = vol_today / vol_avg5
                if vol_ratio > 2.0:
                    score += 8
                elif vol_ratio > 1.5:
                    score += 5
                elif vol_ratio < 0.5:
                    score -= 3

        return _clamp(score, 0, 30)

    def _score_momentum(self, tech_data: list, stock_info: dict) -> float:
        """涨跌幅动量：近期涨幅趋势"""
        score = 50.0

        # 从实时数据取今日涨跌幅
        change_pct = stock_info.get("change_pct", 0)
        if change_pct > 0:
            score += min(change_pct * 2, 10)  # 涨幅越高分越多（上限+10）
        elif change_pct < 0:
            score += max(change_pct * 2, -10)

        # 5日涨跌幅
        if len(tech_data) >= 6:
            chg_5d = (tech_data[-1]["close"] - tech_data[-6]["close"]) / tech_data[-6]["close"] * 100
            if chg_5d > 5:
                score += 8
            elif chg_5d > 2:
                score += 5
            elif chg_5d > 0:
                score += 2
            elif chg_5d < -5:
                score -= 8
            elif chg_5d < -2:
                score -= 5

        # 20日涨跌幅
        if len(tech_data) >= 21:
            chg_20d = (tech_data[-1]["close"] - tech_data[-21]["close"]) / tech_data[-21]["close"] * 100
            if chg_20d > 10:
                score += 7
            elif chg_20d > 5:
                score += 4
            elif chg_20d < -10:
                score -= 7
            elif chg_20d < -5:
                score -= 4

        return _clamp(score, 0, 25)

    def _score_turnover(self, stock_info: dict) -> float:
        """换手率：适中为佳，过低不活跃，过高可能出货"""
        turnover = stock_info.get("turnover_rate", 0)
        if not turnover:
            return 50.0

        # 理想换手率 1%~8%
        if 1.0 <= turnover <= 3.0:
            return 90.0   # 温和换手
        elif 3.0 < turnover <= 5.0:
            return 80.0   # 活跃
        elif 5.0 < turnover <= 8.0:
            return 65.0   # 较活跃
        elif 8.0 < turnover <= 15.0:
            return 45.0   # 偏高
        elif turnover > 15.0:
            return 25.0   # 异常换手，可能出货
        elif 0.3 <= turnover < 1.0:
            return 60.0   # 偏低但可接受
        else:
            return 30.0   # 极低

    def _score_amount(self, tech_data: list, stock_info: dict) -> float:
        """成交额：持续放量说明资金关注"""
        if len(tech_data) < 10:
            return 50.0

        score = 50.0
        amounts = [d["close"] * d["volume"] for d in tech_data[-10:]]
        avg_amount = sum(amounts) / len(amounts)
        today_amount = amounts[-1]

        if avg_amount > 0:
            ratio = today_amount / avg_amount
            if ratio > 2.0:
                score += 12
            elif ratio > 1.5:
                score += 8
            elif ratio > 1.0:
                score += 3
            elif ratio < 0.5:
                score -= 8

        # 金额趋势：近 5 日 vs 前 5 日
        if len(amounts) >= 10:
            recent_avg = sum(amounts[-5:]) / 5
            prev_avg = sum(amounts[-10:-5]) / 5
            if prev_avg > 0:
                trend_ratio = recent_avg / prev_avg
                if trend_ratio > 1.3:
                    score += 8
                elif trend_ratio > 1.1:
                    score += 4
                elif trend_ratio < 0.7:
                    score -= 8
                elif trend_ratio < 0.9:
                    score -= 3

        return _clamp(score, 0, 25)

    # ================================================================
    #  基本面评分 (35%)
    # ================================================================

    def _score_fundamental(self, stock_info: dict, fundamental: dict) -> DimensionScore:
        """基本面：PE / PB / 市值规模 / 振幅"""
        details = {}
        sub_scores = []

        # ── 1. PE 估值 (30 分) ──
        pe_score = self._score_pe(stock_info, fundamental)
        details["PE估值"] = {"分值": pe_score, "满分": 30}
        sub_scores.append((pe_score, 30))

        # ── 2. PB 估值 (20 分) ──
        pb_score = self._score_pb(stock_info, fundamental)
        details["PB估值"] = {"分值": pb_score, "满分": 20}
        sub_scores.append((pb_score, 20))

        # ── 3. 市值规模 (25 分) ──
        cap_score = self._score_market_cap(stock_info)
        details["市值规模"] = {"分值": cap_score, "满分": 25}
        sub_scores.append((cap_score, 25))

        # ── 4. 振幅/波动 (25 分) ──
        vol_score = self._score_volatility(stock_info)
        details["振幅"] = {"分值": vol_score, "满分": 25}
        sub_scores.append((vol_score, 25))

        raw = sum(s * w / 100 for s, w in sub_scores)
        score = _clamp(round(raw, 1))
        return DimensionScore("基本面", score, self.W_FUNDAMENTAL,
                              round(score * self.W_FUNDAMENTAL, 1), details)

    def _score_pe(self, stock_info: dict, fundamental: dict) -> float:
        """PE 估值：合理偏低为佳"""
        pe = stock_info.get("pe", 0) or 0
        if pe <= 0:
            return 40.0  # 亏损或无数据

        # PE 分段评分
        if pe < 10:
            return 95.0   # 极度低估
        elif pe < 15:
            return 85.0   # 低估
        elif pe < 25:
            return 75.0   # 合理
        elif pe < 40:
            return 55.0   # 偏高
        elif pe < 60:
            return 40.0   # 高估
        elif pe < 100:
            return 25.0   # 严重高估
        else:
            return 15.0   # 泡沫

    def _score_pb(self, stock_info: dict, fundamental: dict) -> float:
        """PB 估值：破净或低 PB 为佳"""
        pb = stock_info.get("pb", 0) or 0
        if pb <= 0:
            return 40.0

        if pb < 1.0:
            return 95.0   # 破净
        elif pb < 1.5:
            return 80.0
        elif pb < 2.5:
            return 65.0
        elif pb < 4.0:
            return 50.0
        elif pb < 7.0:
            return 35.0
        else:
            return 20.0

    def _score_market_cap(self, stock_info: dict) -> float:
        """市值规模：中小盘弹性更大，但超小盘风险也大"""
        cap = stock_info.get("market_cap", 0) or 0
        # market_cap 单位是万元，转为亿
        cap_yi = cap / 10000

        if cap_yi <= 0:
            return 50.0

        if cap_yi < 20:
            return 75.0   # 小盘，弹性大
        elif cap_yi < 50:
            return 85.0   # 中小盘，最佳区间
        elif cap_yi < 200:
            return 70.0   # 中盘
        elif cap_yi < 1000:
            return 55.0   # 大盘
        else:
            return 40.0   # 超大盘，弹性不足

    def _score_volatility(self, stock_info: dict) -> float:
        """振幅：适中为佳，过低无机会，过高风险大"""
        amp = stock_info.get("amplitude", 0) or 0

        if amp <= 0:
            return 50.0

        if amp < 1.0:
            return 40.0   # 极低波动，缺乏机会
        elif amp < 2.0:
            return 65.0   # 低波动
        elif amp < 4.0:
            return 85.0   # 适中波动，最佳
        elif amp < 6.0:
            return 70.0   # 偏高波动
        elif amp < 9.0:
            return 50.0   # 高波动
        else:
            return 30.0   # 极高波动，风险大

    # ================================================================
    #  简化评分（仅用实时数据，批量模式）
    # ================================================================

    def _score_from_realtime(self, code: str, name: str, info: dict) -> ScoreResult:
        """仅用实时行情做简化评分（无技术指标时使用）"""
        details = {}
        sub_scores = []

        # 涨跌幅
        chg = info.get("change_pct", 0)
        if chg > 3:
            momentum_s = 70
        elif chg > 0:
            momentum_s = 60
        elif chg > -3:
            momentum_s = 40
        else:
            momentum_s = 25
        details["涨跌动量"] = {"分值": momentum_s, "满分": 50}
        sub_scores.append((momentum_s, 50))

        # 换手率
        turnover_s = self._score_turnover(info)
        details["换手率"] = {"分值": turnover_s, "满分": 25}
        sub_scores.append((turnover_s, 25))

        # PE
        pe_s = self._score_pe(info, {})
        details["PE估值"] = {"分值": pe_s, "满分": 25}
        sub_scores.append((pe_s, 25))

        raw = sum(s * w / 100 for s, w in sub_scores)
        score = _clamp(round(raw, 1))

        dim = DimensionScore("简化评分", score, 1.0, score, details)
        signal, signal_level = self._derive_signal(score, [dim])
        return ScoreResult(
            code=code, name=name, total_score=score,
            signal=signal, signal_level=signal_level,
            dimensions=[{
                "name": dim.name, "score": dim.score,
                "weight": dim.weight, "weighted_score": dim.weighted_score,
                "details": dim.details,
            }],
            summary=f"{name or code} 简化评分 {score}，信号：{signal}"
        )

    # ================================================================
    #  信号 & 报告生成
    # ================================================================

    def _derive_signal(self, total: float, dimensions: list[DimensionScore]) -> tuple[str, int]:
        """根据综合分和各维度生成信号"""
        # 检查是否有极端维度
        any_extreme_low = any(d.score < 20 for d in dimensions)
        any_extreme_high = any(d.score > 85 for d in dimensions)

        if total >= 80 and not any_extreme_low:
            return "强烈买入", 2
        elif total >= 65:
            return "买入", 1
        elif total >= 45:
            return "观望", 0
        elif total <= 20:
            return "强烈卖出", -2
        elif total <= 35:
            return "卖出", -1
        else:
            return "观望", 0

    def _extract_factors(self, dimensions: list[DimensionScore]) -> tuple[list[str], list[str]]:
        """提取主要加分和扣分因素"""
        ups = []
        downs = []

        label_map = {
            "MA趋势": "均线多头排列",
            "MACD动量": "MACD金叉",
            "RSI强弱": "RSI处于强势区间",
            "KDJ指标": "KDJ低位金叉",
            "布林带": "价格获得布林带支撑",
            "量价配合": "量价齐升",
            "涨跌动量": "短期趋势向好",
            "换手率": "换手率健康",
            "成交额": "资金持续流入",
            "PE估值": "估值合理偏低",
            "PB估值": "PB处于低位",
            "市值规模": "市值适中弹性好",
            "振幅": "波动率适中",
        }

        down_map = {
            "MA趋势": "均线空头排列",
            "MACD动量": "MACD死叉",
            "RSI强弱": "RSI进入超买区",
            "KDJ指标": "KDJ高位死叉",
            "布林带": "价格触及布林上轨压力",
            "量价配合": "量价背离",
            "涨跌动量": "短期趋势走弱",
            "换手率": "换手率异常偏高",
            "成交额": "资金持续流出",
            "PE估值": "估值偏高",
            "PB估值": "PB偏高",
            "市值规模": "市值过大弹性不足",
            "振幅": "波动率过高风险大",
        }

        for dim in dimensions:
            for factor_name, detail in dim.details.items():
                if isinstance(detail, dict):
                    s = detail.get("分值", 50)
                    max_s = detail.get("满分", 100)
                    pct = s / max_s if max_s > 0 else 0.5
                    if pct >= 0.75:
                        ups.append(label_map.get(factor_name, factor_name))
                    elif pct <= 0.35:
                        downs.append(down_map.get(factor_name, factor_name))

        return ups[:5], downs[:5]  # 最多取 5 个

    def _build_summary(self, name: str, total: float, signal: str,
                       ups: list[str], downs: list[str]) -> str:
        """生成评分摘要文字"""
        parts = [f"{name} 综合评分 {total}，信号：{signal}。"]
        if ups:
            parts.append(f"加分因素：{'、'.join(ups)}。")
        if downs:
            parts.append(f"风险提示：{'、'.join(downs)}。")
        return " ".join(parts)
