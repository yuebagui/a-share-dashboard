#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any


EASTMONEY_FIELDS = ",".join(
    [
        "f57",  # code
        "f58",  # name
        "f43",  # latest price * 100
        "f44",  # high * 100
        "f45",  # low * 100
        "f46",  # open * 100
        "f47",  # volume, hands
        "f48",  # amount, yuan
        "f60",  # previous close * 100
        "f169",  # change * 100
        "f170",  # change pct * 100
        "f86",  # quote timestamp
    ]
)


@dataclass
class Quote:
    code: str
    market: str
    name: str
    price: float | None
    change: float | None
    change_pct: float | None
    open: float | None
    high: float | None
    low: float | None
    prev_close: float | None
    volume: float | None
    amount: float | None
    time: str
    source: str


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
    return number / scale


def parse_em_time(value: Any) -> str:
    try:
        stamp = int(value)
    except (TypeError, ValueError):
        return ""
    if stamp <= 0:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stamp))


def parse_compact_time(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"\d{14}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"
    return text


def fetch_eastmoney(prefix: str, code: str, market_id: str, timeout: float) -> Quote:
    params = urllib.parse.urlencode(
        {
            "secid": f"{market_id}.{code}",
            "fields": EASTMONEY_FIELDS,
            "_": int(time.time() * 1000),
        }
    )
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
    payload = json.loads(urlopen_text(url, timeout))
    data = payload.get("data")
    if not data:
        raise RuntimeError(payload.get("message") or "empty Eastmoney response")
    price = to_float(data.get("f43"), 100)
    prev_close = to_float(data.get("f60"), 100)
    change = to_float(data.get("f169"), 100)
    change_pct = to_float(data.get("f170"), 100)
    if price is None:
        raise RuntimeError("Eastmoney returned no latest price")
    return Quote(
        code=code,
        market=prefix,
        name=str(data.get("f58") or ""),
        price=price,
        change=change,
        change_pct=change_pct,
        open=to_float(data.get("f46"), 100),
        high=to_float(data.get("f44"), 100),
        low=to_float(data.get("f45"), 100),
        prev_close=prev_close,
        volume=(to_float(data.get("f47")) or 0) * 100,
        amount=to_float(data.get("f48")),
        time=parse_em_time(data.get("f86")),
        source="eastmoney",
    )


def fetch_tencent(prefix: str, code: str, _market_id: str, timeout: float) -> Quote:
    text = urlopen_text(f"http://qt.gtimg.cn/q={prefix}{code}", timeout, {"Referer": "https://gu.qq.com/"})
    if "~" not in text:
        raise RuntimeError(f"unexpected Tencent response: {text[:80]}")
    parts = text.split('"')[1].split("~") if '"' in text else text.split("~")
    if len(parts) < 35 or not parts[3]:
        raise RuntimeError(f"incomplete Tencent response: {text[:120]}")
    price = to_float(parts[3])
    prev_close = to_float(parts[4])
    return Quote(
        code=code,
        market=prefix,
        name=parts[1],
        price=price,
        change=(price - prev_close) if price is not None and prev_close is not None else to_float(parts[31] if len(parts) > 31 else None),
        change_pct=to_float(parts[32] if len(parts) > 32 else None),
        open=to_float(parts[5]),
        high=to_float(parts[33] if len(parts) > 33 else None),
        low=to_float(parts[34] if len(parts) > 34 else None),
        prev_close=prev_close,
        volume=(to_float(parts[6]) or 0) * 100,
        amount=((to_float(parts[37] if len(parts) > 37 else None) or 0) * 10000),
        time=parse_compact_time(parts[30]) if len(parts) > 30 else "",
        source="tencent",
    )


def fetch_sina(prefix: str, code: str, _market_id: str, timeout: float) -> Quote:
    text = urlopen_text(
        f"http://hq.sinajs.cn/list={prefix}{code}",
        timeout,
        {"Referer": "https://finance.sina.com.cn/"},
    )
    if '"' not in text:
        raise RuntimeError(f"unexpected Sina response: {text[:80]}")
    content = text.split('"')[1]
    parts = content.split(",")
    if len(parts) < 32 or not parts[3]:
        raise RuntimeError(f"incomplete Sina response: {text[:120]}")
    price = to_float(parts[3])
    prev_close = to_float(parts[2])
    return Quote(
        code=code,
        market=prefix,
        name=parts[0],
        price=price,
        change=(price - prev_close) if price is not None and prev_close is not None else None,
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


SOURCES = {
    "eastmoney": fetch_eastmoney,
    "tencent": fetch_tencent,
    "sina": fetch_sina,
}


def fetch_quote(raw_code: str, timeout: float, preferred_sources: list[str]) -> tuple[Quote | None, list[dict[str, str]]]:
    prefix, code, market_id = normalize_code(raw_code)
    errors: list[dict[str, str]] = []
    for source in preferred_sources:
        try:
            return SOURCES[source](prefix, code, market_id, timeout), errors
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": source, "error": str(exc)})
    return None, errors


def format_quote(quote: Quote, errors: list[dict[str, str]], verbose: bool) -> str:
    sign_pct = "" if quote.change_pct is None else f"{quote.change_pct:+.2f}%"
    sign_change = "" if quote.change is None else f"{quote.change:+.2f}"
    lines = [
        f"{quote.name or quote.market + quote.code}({quote.market}{quote.code})",
        f"source: {quote.source}",
        f"price: {quote.price:.2f}" if quote.price is not None else "price: --",
        f"change: {sign_change} ({sign_pct})".strip(),
        f"open/high/low/prev: {fmt(quote.open)} / {fmt(quote.high)} / {fmt(quote.low)} / {fmt(quote.prev_close)}",
        f"volume: {fmt(quote.volume, 0)} shares",
        f"amount: {fmt(quote.amount, 0)} yuan",
        f"time: {quote.time or '--'}",
    ]
    if verbose and errors:
        lines.append("fallback errors:")
        lines.extend(f"- {item['source']}: {item['error']}" for item in errors)
    return "\n".join(lines)


def fmt(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{value:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch realtime A-share quote with Eastmoney/Tencent/Sina fallback.")
    parser.add_argument("code", help="A-share code, e.g. 300136, sz300136, sh600519")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--verbose", action="store_true", help="Print failed fallback source errors")
    parser.add_argument("--timeout", type=float, default=8.0, help="Per-source timeout in seconds")
    parser.add_argument(
        "--source",
        choices=["eastmoney", "tencent", "sina"],
        action="append",
        help="Restrict source order; can be repeated. Default: eastmoney, tencent, sina",
    )
    args = parser.parse_args()

    sources = args.source or ["eastmoney", "tencent", "sina"]
    quote, errors = fetch_quote(args.code, args.timeout, sources)
    if args.json:
        print(json.dumps({"quote": asdict(quote) if quote else None, "errors": errors}, ensure_ascii=False, indent=2))
    elif quote:
        print(format_quote(quote, errors, args.verbose))
    else:
        print("All quote sources failed.", file=sys.stderr)
        for item in errors:
            print(f"- {item['source']}: {item['error']}", file=sys.stderr)
    return 0 if quote else 1


if __name__ == "__main__":
    raise SystemExit(main())
