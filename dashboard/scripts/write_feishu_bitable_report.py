#!/usr/bin/env python3
"""
Generate the daily A-share review.

Default behavior:
  Refresh market data and print the report to stdout for Codex delivery.

Optional Feishu mode:
  Pass --feishu to append the same report to a Feishu Bitable table.

Required environment for --feishu:
  FEISHU_APP_ID=cli_...
  FEISHU_APP_SECRET=...
  FEISHU_BITABLE_APP_TOKEN=app...
  FEISHU_BITABLE_TABLE_ID=tbl...

Optional environment:
  FEISHU_BITABLE_FIELD_PREFIX=...
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from send_feishu_report import DAILY_JSON, build_report, format_money, format_signed, run_fetch


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
BITABLE_RECORDS_URL = (
    "https://open.feishu.cn/open-apis/bitable/v1/apps/"
    "{app_token}/tables/{table_id}/records/batch_create"
)
BITABLE_FIELDS_URL = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields"

FIELD_SCHEMA = [
    {"field_name": "日期", "type": 1},
    {"field_name": "阶段", "type": 1},
    {"field_name": "生成时间", "type": 1},
    {"field_name": "情绪", "type": 1},
    {"field_name": "情绪分", "type": 2, "property": {"formatter": "0.0"}},
    {"field_name": "涨停数", "type": 2, "property": {"formatter": "0"}},
    {"field_name": "跌停数", "type": 2, "property": {"formatter": "0"}},
    {"field_name": "炸板率", "type": 2, "property": {"formatter": "0.0"}},
    {"field_name": "最高连板", "type": 2, "property": {"formatter": "0"}},
    {"field_name": "关注板块", "type": 1},
    {"field_name": "强势个股", "type": 1},
    {"field_name": "弱势方向", "type": 1},
    {"field_name": "风险提示", "type": 1},
    {"field_name": "看板链接", "type": 1},
    {"field_name": "复盘全文", "type": 1},
    {"field_name": "看板数据", "type": 1},
]


def main() -> int:
    load_local_env(PROJECT_ROOT / ".env")
    load_local_env(ROOT / ".feishu.env")

    trade_date = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    use_feishu = "--feishu" in sys.argv
    setup_only = "--setup-only" in sys.argv
    if len(sys.argv) > 1 and sys.argv[1] == "--date" and len(sys.argv) > 2:
        trade_date = sys.argv[2]

    if setup_only and not use_feishu:
        raise RuntimeError("--setup-only requires --feishu")

    config: dict[str, str] | None = None
    token = ""
    if use_feishu:
        config = get_config()
        token = get_tenant_access_token(config["app_id"], config["app_secret"])
        if "--skip-field-setup" not in sys.argv and os.environ.get("FEISHU_SKIP_FIELD_SETUP", "").strip() != "1":
            ensure_fields(token, config["app_token"], config["table_id"])
        if setup_only:
            print("Feishu Bitable fields are ready.")
            return 0

    run_fetch(trade_date)
    data = json.loads(DAILY_JSON.read_text(encoding="utf-8"))
    report = build_report(data)

    if not use_feishu:
        print(report)
        return 0

    record = build_record(data, report)
    result = append_bitable_record(token, config["app_token"], config["table_id"], record)

    record_id = result.get("data", {}).get("records", [{}])[0].get("record_id", "--")
    print(f"Feishu Bitable report written: {record_id}")
    return 0


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def get_config() -> dict[str, str]:
    config = {
        "app_id": os.environ.get("FEISHU_APP_ID", "").strip(),
        "app_secret": os.environ.get("FEISHU_APP_SECRET", "").strip(),
        "app_token": os.environ.get("FEISHU_BITABLE_APP_TOKEN", "").strip(),
        "table_id": os.environ.get("FEISHU_BITABLE_TABLE_ID", "").strip(),
    }
    missing = [key for key, value in config.items() if not value]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing Feishu Bitable config: {joined}")
    return config


def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    payload = {"app_id": app_id, "app_secret": app_secret}
    result = post_json(AUTH_URL, payload)
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant_access_token: {result}")
    return str(result["tenant_access_token"])


def append_bitable_record(token: str, app_token: str, table_id: str, fields: dict) -> dict:
    url = BITABLE_RECORDS_URL.format(app_token=app_token, table_id=table_id)
    return post_json(url, {"records": [{"fields": fields}]}, token=token)


def ensure_fields(token: str, app_token: str, table_id: str) -> None:
    existing = list_fields(token, app_token, table_id)
    existing_names = {item.get("field_name") for item in existing}
    for spec in FIELD_SCHEMA:
        name = field(spec["field_name"])
        if name in existing_names:
            continue
        payload = dict(spec)
        payload["field_name"] = name
        create_field(token, app_token, table_id, payload)


def list_fields(token: str, app_token: str, table_id: str) -> list[dict]:
    query = urlencode({"page_size": 100})
    url = f"{BITABLE_FIELDS_URL.format(app_token=app_token, table_id=table_id)}?{query}"
    result = get_json(url, token=token)
    return result.get("data", {}).get("items", [])


def create_field(token: str, app_token: str, table_id: str, payload: dict) -> None:
    url = BITABLE_FIELDS_URL.format(app_token=app_token, table_id=table_id)
    try:
        post_json(url, payload, token=token)
    except RuntimeError:
        if "property" not in payload:
            raise
        fallback = dict(payload)
        fallback.pop("property", None)
        post_json(url, fallback, token=token)


def get_json(url: str, token: str = "") -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(format_http_error(exc, url)) from exc
    if result.get("code") not in (0, None):
        raise RuntimeError(f"Feishu API failed: {result}")
    return result


def post_json(url: str, payload: dict, token: str = "") -> dict:
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(format_http_error(exc, url)) from exc
    if result.get("code") not in (0, None):
        raise RuntimeError(f"Feishu API failed: {result}")
    return result


def format_http_error(exc: HTTPError, url: str) -> str:
    raw = exc.read().decode("utf-8", errors="replace")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        body = raw[:1000]
    safe_url = url.split("?")[0]
    return f"Feishu HTTP {exc.code} for {safe_url}: {body}"


def build_record(data: dict, report: str) -> dict:
    meta = data.get("meta", {})
    emotion = data.get("emotion", {})
    temp = data.get("temperature", {})
    focus = data.get("focusBoards", {}).get("items", [])[:8]
    strong_stocks = data.get("limitUps", [])[:12]
    weak = data.get("againstMarket", {}).get("down", [])[:8]
    risks = data.get("risks", [])[:5]

    return {
        field("日期"): meta.get("tradeDate", ""),
        field("阶段"): meta.get("phase", ""),
        field("生成时间"): meta.get("generatedAt", ""),
        field("情绪"): emotion.get("tag", ""),
        field("情绪分"): float(emotion.get("score", 0) or 0),
        field("涨停数"): int(temp.get("limitUp", 0) or 0),
        field("跌停数"): int(temp.get("limitDown", 0) or 0),
        field("炸板率"): float(temp.get("failRate", 0) or 0),
        field("最高连板"): int(temp.get("maxLadder", 0) or 0),
        field("关注板块"): "\n".join(format_board(item) for item in focus),
        field("强势个股"): "\n".join(format_stock(item) for item in strong_stocks),
        field("弱势方向"): "\n".join(format_board(item) for item in weak),
        field("风险提示"): "\n".join(f"- {item}" for item in risks),
        field("看板链接"): dashboard_url(),
        field("复盘全文"): report,
        field("看板数据"): json.dumps(data, ensure_ascii=False),
    }


def field(name: str) -> str:
    prefix = os.environ.get("FEISHU_BITABLE_FIELD_PREFIX", "").strip()
    return f"{prefix}{name}" if prefix else name


def dashboard_url() -> str:
    return os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8765/").strip()


def format_board(item: dict) -> str:
    return (
        f"{item.get('name', '--')}｜涨跌 {format_signed(item.get('changePct', 0))}%｜"
        f"超额 {format_signed(item.get('excessPct', 0))}%｜资金 {format_money(item.get('netInflow', 0))}"
    )


def format_stock(item: dict) -> str:
    tags = ",".join(item.get("tags", [])[:2])
    return (
        f"{item.get('name', '--')}({item.get('code', '--')})｜"
        f"{item.get('boards', 1)}板｜{tags}｜{item.get('reason', '')}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
