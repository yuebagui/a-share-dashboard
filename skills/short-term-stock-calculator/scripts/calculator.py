#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Quote:
    code: str
    market: str
    name: str
    price: float | None
    change_pct: float | None
    open: float | None
    high: float | None
    low: float | None
    prev_close: float | None
    volume: float | None
    amount: float | None
    time: str
    source: str


@dataclass
class Bar:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float
    amount: float | None = None


def normalize_code(raw: str) -> tuple[str, str, str]:
    text = raw.strip().lower()
    match = re.fullmatch(r"(sh|sz)?\s*(\d{6})", text)
    if not match:
        raise ValueError(f"Unsupported A-share code: {raw!r}")
    prefix, code = match.groups()
    if not prefix:
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
    market_id = "1" if prefix == "sh" else "0"
    return prefix, code, market_id


def decode_body(body: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            pass
    return body.decode("utf-8", errors="replace")


def urlopen_text(url: str, timeout: float, headers: dict[str, str] | None = None) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Referer": "https://quote.eastmoney.com/",
            **(headers or {}),
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        return decode_body(response.read())


def to_float(value: Any, scale: float = 1.0) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number / scale


def fetch_quote(raw_code: str, timeout: float) -> tuple[Quote, list[str]]:
    prefix, code, market_id = normalize_code(raw_code)
    errors: list[str] = []
    for source, fetcher in (
        ("eastmoney", fetch_quote_eastmoney),
        ("tencent", fetch_quote_tencent),
        ("sina", fetch_quote_sina),
    ):
        try:
            return fetcher(prefix, code, market_id, timeout), errors
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")
    raise RuntimeError("; ".join(errors))


def fetch_quote_eastmoney(prefix: str, code: str, market_id: str, timeout: float) -> Quote:
    fields = ",".join(["f57", "f58", "f43", "f44", "f45", "f46", "f47", "f48", "f60", "f170", "f86"])
    params = urllib.parse.urlencode({"secid": f"{market_id}.{code}", "fields": fields, "_": int(time.time() * 1000)})
    payload = json.loads(urlopen_text(f"https://push2.eastmoney.com/api/qt/stock/get?{params}", timeout))
    data = payload.get("data")
    if not data:
        raise RuntimeError(payload.get("message") or "empty response")
    price = to_float(data.get("f43"), 100)
    if price is None:
        raise RuntimeError("no latest price")
    stamp = int(data.get("f86") or 0)
    return Quote(
        code=code,
        market=prefix,
        name=str(data.get("f58") or ""),
        price=price,
        change_pct=to_float(data.get("f170"), 100),
        open=to_float(data.get("f46"), 100),
        high=to_float(data.get("f44"), 100),
        low=to_float(data.get("f45"), 100),
        prev_close=to_float(data.get("f60"), 100),
        volume=(to_float(data.get("f47")) or 0) * 100,
        amount=to_float(data.get("f48")),
        time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp)) if stamp else "",
        source="eastmoney",
    )


def fetch_quote_tencent(prefix: str, code: str, _market_id: str, timeout: float) -> Quote:
    text = urlopen_text(f"http://qt.gtimg.cn/q={prefix}{code}", timeout, {"Referer": "https://gu.qq.com/"})
    parts = text.split('"')[1].split("~") if '"' in text else text.split("~")
    if len(parts) < 35 or not parts[3]:
        raise RuntimeError(f"incomplete response: {text[:100]}")
    price = to_float(parts[3])
    prev_close = to_float(parts[4])
    return Quote(
        code=code,
        market=prefix,
        name=parts[1],
        price=price,
        change_pct=to_float(parts[32] if len(parts) > 32 else None),
        open=to_float(parts[5]),
        high=to_float(parts[33] if len(parts) > 33 else None),
        low=to_float(parts[34] if len(parts) > 34 else None),
        prev_close=prev_close,
        volume=(to_float(parts[6]) or 0) * 100,
        amount=(to_float(parts[37] if len(parts) > 37 else None) or 0) * 10000,
        time=parts[30] if len(parts) > 30 else "",
        source="tencent",
    )


def fetch_quote_sina(prefix: str, code: str, _market_id: str, timeout: float) -> Quote:
    text = urlopen_text(f"http://hq.sinajs.cn/list={prefix}{code}", timeout, {"Referer": "https://finance.sina.com.cn/"})
    parts = text.split('"')[1].split(",") if '"' in text else []
    if len(parts) < 32 or not parts[3]:
        raise RuntimeError(f"incomplete response: {text[:100]}")
    price = to_float(parts[3])
    prev_close = to_float(parts[2])
    return Quote(
        code=code,
        market=prefix,
        name=parts[0],
        price=price,
        change_pct=((price - prev_close) / prev_close * 100) if price is not None and prev_close else None,
        open=to_float(parts[1]),
        high=to_float(parts[4]),
        low=to_float(parts[5]),
        prev_close=prev_close,
        volume=to_float(parts[8]),
        amount=to_float(parts[9]),
        time=f"{parts[30]} {parts[31]}" if len(parts) > 31 else "",
        source="sina",
    )


def fetch_bars(raw_code: str, timeout: float) -> tuple[list[Bar], str]:
    prefix, code, _market_id = normalize_code(raw_code)
    errors: list[str] = []
    for source, fetcher in (("eastmoney", fetch_bars_eastmoney), ("tencent", fetch_bars_tencent)):
        try:
            bars = fetcher(prefix, code, timeout)
            if len(bars) >= 60:
                return bars, source
            errors.append(f"{source}: only {len(bars)} bars")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}: {exc}")
    raise RuntimeError("; ".join(errors))


def fetch_bars_eastmoney(prefix: str, code: str, timeout: float) -> list[Bar]:
    market_id = "1" if prefix == "sh" else "0"
    params = urllib.parse.urlencode(
        {
            "secid": f"{market_id}.{code}",
            "klt": "101",
            "fqt": "1",
            "lmt": "160",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
    )
    payload = json.loads(urlopen_text(f"https://push2his.eastmoney.com/api/qt/stock/kline/get?{params}", timeout))
    klines = (payload.get("data") or {}).get("klines") or []
    bars: list[Bar] = []
    for row in klines:
        parts = str(row).split(",")
        if len(parts) < 6:
            continue
        bars.append(
            Bar(
                date=parts[0],
                open=float(parts[1]),
                close=float(parts[2]),
                high=float(parts[3]),
                low=float(parts[4]),
                volume=float(parts[5]),
                amount=to_float(parts[6]) if len(parts) > 6 else None,
            )
        )
    return bars


def fetch_bars_tencent(prefix: str, code: str, timeout: float) -> list[Bar]:
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,160,qfq"
    payload = json.loads(urlopen_text(url, timeout, {"Referer": "https://gu.qq.com/"}))
    for item in (payload.get("data") or {}).values():
        rows = item.get("qfqday") or item.get("day") or []
        bars = []
        for row in rows:
            if len(row) < 6:
                continue
            bars.append(Bar(row[0], float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
        return bars
    return []


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def atr_values(bars: list[Bar], period: int = 14) -> list[float]:
    trs: list[float] = []
    prev_close: float | None = None
    for bar in bars:
        if prev_close is None:
            tr = bar.high - bar.low
        else:
            tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        trs.append(tr)
        prev_close = bar.close
    out: list[float] = []
    for index in range(len(trs)):
        if index + 1 < period:
            out.append(sum(trs[: index + 1]) / (index + 1))
        else:
            out.append(sum(trs[index + 1 - period : index + 1]) / period)
    return out


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def score_analysis(quote: Quote, bars: list[Bar], mode: str) -> dict[str, Any]:
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    vols = [b.volume for b in bars]
    last = bars[-1]
    price = quote.price or last.close
    ma20 = sma(closes, 20) or last.close
    ma20_prev5 = sum(closes[-25:-5]) / 20 if len(closes) >= 25 else ma20
    ma60 = sma(closes, 60)
    atrs = atr_values(bars)
    atr = atrs[-1]
    atr_pct = atr / price * 100 if price else 0
    high60 = max(highs[-60:])
    low60 = min(lows[-60:])
    position_60 = (price - low60) / (high60 - low60) * 100 if high60 > low60 else 50
    avg20_vol = sma(vols, 20) or last.volume
    vol_ratio = last.volume / avg20_vol if avg20_vol else 1
    today_range = (last.high - last.low) / max(last.close, 0.01) * 100
    change_5 = (price / closes[-6] - 1) * 100 if len(closes) >= 6 and closes[-6] else 0
    recent_gain_safety = change_5 / max(statistics.mean([(b.high - b.low) / b.close * 100 for b in bars[-10:]]), 0.1)
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    dif = [a - b for a, b in zip(ema12[-len(ema26) :], ema26)]
    dea = ema_series(dif, 9)
    macd_now = dif[-1] - dea[-1] if dif and dea else 0
    macd_prev = dif[-2] - dea[-2] if len(dif) >= 2 and len(dea) >= 2 else macd_now
    code_type = classify_code(quote.market, quote.code)
    trend_score = 0
    ratio = price / ma20 if ma20 else 1
    if ratio >= 1.08:
        trend_score += 15
    elif ratio >= 1.05:
        trend_score += 13
    elif ratio >= 1.03:
        trend_score += 11
    elif ratio >= 1.00:
        trend_score += 8
    elif ratio >= 0.97:
        trend_score += 5
    elif ratio >= 0.95:
        trend_score += 2
    slope = (ma20 / ma20_prev5 - 1) * 100 if ma20_prev5 else 0
    if slope >= 1.5:
        trend_score += 10
    elif slope >= 0.8:
        trend_score += 8
    elif slope >= 0.3:
        trend_score += 6
    elif slope >= 0:
        trend_score += 4
    elif slope >= -0.5:
        trend_score += 2

    macd_score = 10 if macd_now > 0 and macd_now > macd_prev else 7 if macd_now > 0 else 5 if macd_now > macd_prev else 0
    if position_60 < 30:
        position_score = 10
    elif position_60 < 50:
        position_score = 8
    elif position_60 < 70:
        position_score = 6
    elif position_60 < 85:
        position_score = 3
    else:
        position_score = 0

    atr_score = 10 if atr_pct < 3 else 8 if atr_pct < 4 else 6 if atr_pct < 5 else 4 if atr_pct < 6 else 2 if atr_pct < 7 else 0
    atr_contract = atrs[-1] < statistics.mean(atrs[-10:]) if len(atrs) >= 10 else False
    volatility_score = atr_score + (5 if atr_contract else 2)

    volume_price_score, volume_label = volume_price(last, bars, vol_ratio, price, ma20)
    pullback_score = pullback_quality(bars, avg20_vol)
    buy_fit_score, buy_fit_label = buy_point_fit(price, last, ma20, high60, low60, position_60, vol_ratio, mode, code_type)
    risk_score, risk_label, stop_ref = risk_assessment(price, ma20, atr, low60, last.low, mode)
    mode_score = mode_fit(mode, code_type, price, ma20, vol_ratio, position_60, last)
    safety_score = 5 if recent_gain_safety < 0.7 else 3 if recent_gain_safety < 1.0 else 1 if recent_gain_safety < 1.3 else 0

    raw_total = (
        trend_score
        + macd_score
        + position_score
        + volatility_score
        + volume_price_score
        + pullback_score
        + buy_fit_score
        + risk_score
        + mode_score
        + safety_score
    )
    total = int(round(clamp(raw_total, 0, 100)))
    vetoes = detect_vetoes(price, last, ma20, vol_ratio, atr_pct, position_60)
    action = decide_action(total, vetoes, risk_label)
    confidence = "中" if not vetoes and total >= 70 else "偏低" if vetoes or total < 70 else "中高"
    position = suggest_position(total, vetoes, risk_label)
    return {
        "quote": asdict(quote),
        "bar_source_date": last.date,
        "technical": {
            "ma20": round(ma20, 3),
            "ma60": round(ma60, 3) if ma60 else None,
            "ma20_slope_5d_pct": round(slope, 2),
            "atr": round(atr, 3),
            "atr_pct": round(atr_pct, 2),
            "high60": round(high60, 3),
            "low60": round(low60, 3),
            "position_60_pct": round(position_60, 1),
            "volume_ratio": round(vol_ratio, 2),
            "macd_hist": round(macd_now, 4),
            "code_type": code_type,
            "stop_reference": stop_ref,
        },
        "score": {
            "total": total,
            "trend": trend_score,
            "macd": macd_score,
            "position": position_score,
            "volatility": volatility_score,
            "volume_price": volume_price_score,
            "pullback": pullback_score,
            "buy_point_fit": buy_fit_score,
            "risk": risk_score,
            "mode_fit": mode_score,
            "gain_safety": safety_score,
        },
        "labels": {
            "volume_price": volume_label,
            "buy_point": buy_fit_label,
            "risk": risk_label,
            "mode": best_mode_label(mode, code_type, price, ma20, vol_ratio, position_60),
        },
        "vetoes": vetoes,
        "action": action,
        "confidence": confidence,
        "suggested_position": position,
        "plan": build_plan(total, vetoes, price, ma20, atr, high60, low60, last, mode),
        "caveat": "自动分数主要来自股价、K线、量价和风险；主线题材、龙头地位、市场情绪需要结合当日复盘确认。",
    }


def classify_code(market: str, code: str) -> str:
    if code.startswith(("300", "301", "688", "689")):
        return "20cm"
    if code.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "10cm"
    if code.startswith(("5", "15", "16", "18")):
        return "etf"
    return market


def volume_price(last: Bar, bars: list[Bar], vol_ratio: float, price: float, ma20: float) -> tuple[int, str]:
    body_pct = (last.close - last.open) / max(last.open, 0.01) * 100
    upper_shadow = (last.high - max(last.open, last.close)) / max(last.close, 0.01) * 100
    close_pos = (last.close - last.low) / max(last.high - last.low, 0.01)
    if body_pct > 2 and vol_ratio >= 1.2 and close_pos > 0.65:
        return 15, "放量上涨，需求占优"
    if price >= ma20 and 0.5 <= vol_ratio <= 1.2 and close_pos > 0.45:
        return 12, "量价健康，承接正常"
    if body_pct < -2 and vol_ratio >= 1.2:
        return 3, "放量下跌，供应进场"
    if upper_shadow > 3 and vol_ratio >= 1.4:
        return 0, "放量长上影，疑似滞涨"
    if vol_ratio < 0.6 and abs(body_pct) < 1.5:
        return 8, "缩量整理，等待方向"
    return 7, "量价中性"


def pullback_quality(bars: list[Bar], avg20_vol: float) -> int:
    recent = bars[-3:]
    if all(b.close <= b.open for b in recent) and sum(b.volume for b in recent) / 3 < avg20_vol * 0.8:
        return 10
    if any(b.close < b.open and b.volume > avg20_vol * 1.2 for b in recent):
        return 0
    return 5


def buy_point_fit(
    price: float,
    last: Bar,
    ma20: float,
    high60: float,
    low60: float,
    position_60: float,
    vol_ratio: float,
    mode: str,
    code_type: str,
) -> tuple[int, str]:
    near_ma20 = abs(price / ma20 - 1) <= 0.035 if ma20 else False
    near_breakout = price >= high60 * 0.97
    recovered = last.close > max(last.open, (last.high + last.low) / 2)
    if mode == "20cm" or (mode == "auto" and code_type == "20cm"):
        if near_ma20 and recovered:
            return 10, "20cm分歧后靠近支撑并修复"
        if recovered and vol_ratio >= 1.1:
            return 8, "20cm反包修复迹象"
    if mode == "trend" or mode == "auto":
        if near_breakout and vol_ratio >= 1.2 and price > ma20:
            return 10, "容量趋势放量突破"
        if near_ma20 and price > ma20:
            return 8, "趋势回踩MA20附近"
    if mode == "leader" and recovered and position_60 < 85:
        return 8, "龙头分歧承接尚可"
    if position_60 >= 85:
        return 2, "位置偏高，追高性价比低"
    return 5, "买点一般，等待更明确触发"


def risk_assessment(price: float, ma20: float, atr: float, low60: float, day_low: float, mode: str) -> tuple[int, str, dict[str, float]]:
    candidates = [price - 2 * atr, day_low * 0.99, low60 * 0.995]
    if mode in ("trend", "auto") and ma20 < price:
        candidates.append(ma20 * 0.985)
    valid_candidates = [item for item in candidates if 0 < item < price]
    technical_stop = max(valid_candidates) if valid_candidates else price * 0.95
    stop_loss_pct = (price - technical_stop) / price * 100 if price else 99
    if stop_loss_pct <= 3:
        return 10, "止损距离舒适", {"technical_stop": round(technical_stop, 3), "stop_loss_pct": round(stop_loss_pct, 2)}
    if stop_loss_pct <= 5:
        return 7, "止损距离可接受", {"technical_stop": round(technical_stop, 3), "stop_loss_pct": round(stop_loss_pct, 2)}
    if stop_loss_pct <= 8:
        return 3, "止损偏远，需降仓或等回落", {"technical_stop": round(technical_stop, 3), "stop_loss_pct": round(stop_loss_pct, 2)}
    return 0, "止损过远，不适合追入", {"technical_stop": round(max(low60, technical_stop), 3), "stop_loss_pct": round(stop_loss_pct, 2)}


def mode_fit(mode: str, code_type: str, price: float, ma20: float, vol_ratio: float, position_60: float, last: Bar) -> int:
    if mode == "20cm":
        return 5 if code_type == "20cm" else 1
    if mode == "leader":
        return 5 if vol_ratio >= 1.0 and position_60 < 85 else 3
    if mode == "trend":
        return 5 if price > ma20 and vol_ratio >= 0.8 else 2
    if code_type == "20cm" and last.close >= last.open:
        return 5
    if price > ma20:
        return 4
    return 2


def detect_vetoes(price: float, last: Bar, ma20: float, vol_ratio: float, atr_pct: float, position_60: float) -> list[str]:
    vetoes: list[str] = []
    upper_shadow_pct = (last.high - max(last.open, last.close)) / max(last.close, 0.01) * 100
    if price < ma20 * 0.97:
        vetoes.append("价格明显跌破MA20，趋势未修复")
    if upper_shadow_pct > 4 and vol_ratio > 1.4 and position_60 > 70:
        vetoes.append("高位放量长上影，疑似滞涨")
    if atr_pct > 8:
        vetoes.append("ATR波动过高，止损难控制")
    if last.close < last.open and vol_ratio > 1.5:
        vetoes.append("放量阴线，供应压力偏大")
    return vetoes


def best_mode_label(mode: str, code_type: str, price: float, ma20: float, vol_ratio: float, position_60: float) -> str:
    if mode != "auto":
        return mode
    if code_type == "20cm" and position_60 < 85:
        return "20cm反包/分歧低吸"
    if price > ma20 and vol_ratio >= 1.1:
        return "容量趋势突破"
    return "龙头分歧低吸或等待确认"


def decide_action(total: int, vetoes: list[str], risk_label: str) -> str:
    if vetoes:
        return "回避/等待修复"
    if total >= 90:
        return "重点观察，触发计划后可参与"
    if total >= 80:
        return "标准候选，按计划买点参与"
    if total >= 70:
        return "小仓试错或继续观察"
    return "暂不参与"


def suggest_position(total: int, vetoes: list[str], risk_label: str) -> str:
    if vetoes or total < 70:
        return "0%-10%"
    if "偏远" in risk_label or "过远" in risk_label:
        return "10%-15%"
    if total >= 90:
        return "25%-50%，需市场强/中且为主线核心"
    if total >= 80:
        return "25%-35%"
    return "10%-25%"


def build_plan(total: int, vetoes: list[str], price: float, ma20: float, atr: float, high60: float, low60: float, last: Bar, mode: str) -> dict[str, str]:
    stop_candidates = [price - 2 * atr, last.low * 0.99, low60 * 0.995]
    if ma20 < price:
        stop_candidates.append(ma20 * 0.985)
    valid_stops = [item for item in stop_candidates if 0 < item < price]
    stop = max(valid_stops) if valid_stops else price * 0.95
    if vetoes or total < 70:
        buy = "不主动买；等待站回MA20、量价转强、重新出现标准买点。"
    elif mode == "20cm":
        buy = "只做低吸修复：急杀后收回分时均线/关键支撑再试，不追高。"
    elif mode == "trend":
        buy = "放量突破平台或缩量回踩突破位/MA20不破再参与。"
    else:
        buy = "优先等分歧低吸或突破确认，避免一致加速时追入。"
    return {
        "buy": buy,
        "stop": f"参考止损 {stop:.2f}；若亏损接近5%或跌破关键位不收回，执行硬止损。",
        "take_profit": "主线仍强且量价健康则持有；放量滞涨、长上影、板块退潮时减仓或离场。",
        "levels": f"MA20 {ma20:.2f}，60日区间 {low60:.2f}-{high60:.2f}，今日低点 {last.low:.2f}。",
    }


def print_text(result: dict[str, Any]) -> None:
    q = result["quote"]
    tech = result["technical"]
    score = result["score"]
    print(f"{q.get('name') or q['market'] + q['code']}({q['market']}{q['code']}) 短线打分")
    print(f"数据: quote={q['source']} {q.get('time') or '--'} / kline_date={result['bar_source_date']}")
    print(f"现价: {fmt(q.get('price'))} 涨跌幅: {fmt(q.get('change_pct'))}%")
    print(f"总分: {score['total']}/100 | 动作: {result['action']} | 置信度: {result['confidence']} | 建议仓位: {result['suggested_position']}")
    print("")
    print("分项评分:")
    for key in ("trend", "macd", "position", "volatility", "volume_price", "pullback", "buy_point_fit", "risk", "mode_fit", "gain_safety"):
        print(f"- {key}: {score[key]}")
    print("")
    print("关键指标:")
    print(f"- MA20: {fmt(tech['ma20'])} / MA20斜率5日: {fmt(tech['ma20_slope_5d_pct'])}% / ATR: {fmt(tech['atr'])} ({fmt(tech['atr_pct'])}%)")
    print(f"- 60日位置: {fmt(tech['position_60_pct'])}% / 量比: {fmt(tech['volume_ratio'])} / 类型: {tech['code_type']}")
    print(f"- 模式: {result['labels']['mode']} / 量价: {result['labels']['volume_price']} / 买点: {result['labels']['buy_point']} / 风险: {result['labels']['risk']}")
    if result["vetoes"]:
        print("")
        print("一票否决/风险:")
        for item in result["vetoes"]:
            print(f"- {item}")
    print("")
    print("操作计划:")
    for key in ("buy", "stop", "take_profit", "levels"):
        print(f"- {result['plan'][key]}")
    print("")
    print(result["caveat"])


def fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Personalized A-share short-term stock calculator.")
    parser.add_argument("code", help="A-share code, e.g. 300750, sz300750, sh600519")
    parser.add_argument("--mode", choices=["auto", "20cm", "leader", "trend"], default="auto", help="Preferred trading model")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--timeout", type=float, default=8.0, help="Per-source timeout in seconds")
    args = parser.parse_args()
    try:
        quote, _quote_errors = fetch_quote(args.code, args.timeout)
        bars, bar_source = fetch_bars(args.code, args.timeout)
        result = score_analysis(quote, bars, args.mode)
        result["kline_source"] = bar_source
    except Exception as exc:  # noqa: BLE001
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    else:
        print_text(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
