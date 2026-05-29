import asyncio
import json
from datetime import datetime, timedelta

from config.settings_store import init_runtime_settings
from config.rebate_helpers import get_haodanku_config
from config.config import ORDER_SYNC_CONFIG
from src.platforms.alliance_orders import AllianceOrderFetcher, _HaodankuOrderApi
from src.platforms.base import is_placeholder, http_request, parse_json_response
from src.database import DatabaseManager
from src.services.order_sync_service import OrderSyncService
from src.services.wallet_service import WalletService

init_runtime_settings()

hdk = get_haodanku_config()
print("tb_name:", hdk.get("tb_name") or "(empty)")


async def probe(start, end, label):
    client = _HaodankuOrderApi(hdk)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sign_params = {
        "method": "tbk.order",
        "v": "3.7.12",
        "app_id": client.app_id,
        "date": date_str,
        "tb_name": client.tb_name,
        "start_time": int(start.timestamp()),
        "end_time": int(end.timestamp()),
        "page_no": 1,
        "page_size": 10,
        "query_type": 1,
        "order_scene": 1,
    }
    sign = client._sign(sign_params, client.app_secret)
    resp = await http_request(
        "POST",
        client.API_URL,
        json={**sign_params, "sign": sign},
        headers={"Content-Type": "application/json"},
    )
    data = parse_json_response(resp)
    code = data.get("code") if isinstance(data, dict) else None
    msg = (data.get("msg") or data.get("message") or "") if isinstance(data, dict) else ""
    rows = []
    if isinstance(data, dict) and int(data.get("code") or 0) == 200:
        body = data.get("data") or {}
        ro = body.get("results") or {}
        rows = ro.get("publisher_order_dto") or []
        if isinstance(rows, dict):
            rows = [rows]
    print(f"\n--- {label} ---")
    print("窗口:", start.strftime("%Y-%m-%d %H:%M"), "->", end.strftime("%H:%M"))
    print("API code:", code, "| msg:", msg)
    print("本页订单数:", len(rows) if isinstance(rows, list) else 0)
    if rows:
        r0 = rows[0]
        print(
            "样例: trade_id=",
            r0.get("trade_id"),
            "tk_status=",
            r0.get("tk_status"),
            "title=",
            (r0.get("item_title") or "")[:40],
        )
    return code, len(rows) if isinstance(rows, list) else 0


async def main():
    if (
        is_placeholder(hdk.get("app_id"))
        or is_placeholder(hdk.get("app_secret"))
        or is_placeholder(hdk.get("tb_name"))
    ):
        print("配置不完整")
        return
    end = datetime.now()
    lb = int(ORDER_SYNC_CONFIG.get("lookback_minutes", 120))
    start_lb = end - timedelta(minutes=lb)
    await probe(start_lb, end, f"lookback {lb} 分钟")

    total = 0
    window_end = end
    for _ in range(8):
        window_start = window_end - timedelta(hours=3)
        rows = await _HaodankuOrderApi(hdk).query_orders(window_start, window_end)
        total += len(rows)
        if rows:
            print(f"分片 {window_start:%m-%d %H:%M}-{window_end:%H:%M}: {len(rows)} 条")
        window_end = window_start
        if window_start <= end - timedelta(hours=24):
            break
    print(f"最近24h(3h分片) 合计: {total} 条")

    fetcher = AllianceOrderFetcher()
    parsed = await fetcher.fetch_taobao_orders(start_lb, end)
    print(f"解析后有效淘宝单: {len(parsed)}")

    db = DatabaseManager()
    result = await OrderSyncService(db, wallet_service=WalletService(db)).sync_once()
    print("\nsync_once:", json.dumps(result, ensure_ascii=False))


asyncio.run(main())

