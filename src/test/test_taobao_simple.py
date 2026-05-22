"""
淘宝转链测试（好单库 v3 REST + sign 签名）
直接运行: python test_taobao_simple.py
"""
import asyncio
import os
import sys
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.config import COMMISSION_CONFIG, REBATE_CONFIG
from src.platforms.taobao import (
    HDK_DEFAULT_API_URL,
    HDK_DEFAULT_METHOD,
    TaobaoClient,
)
from src.rebate_api import RebateAPI, extract_url_from_text

TEST_WXID = 'test_user_001'

TEST_CASES = [
    {
        'name': '大窑嘉宾（短链+淘口令）',
        'raw_input': (
            '【淘宝】假一赔四 https://e.tb.cn/h.R21JpXAPnZb31KN?tk=dlL35ufVHsg HU926 '
            '「【吴京代言】大窑嘉宾橙诺汽水果味饮料碳酸饮料520mL*8瓶气泡水」'
            '点击链接直接打开 或者 淘宝搜索直接打开'
        ),
        'expected_item_id': None,
    },
    {
        'name': 'Apple iPhone 17（短链+淘口令）',
        'raw_input': (
            '【淘宝】https://e.tb.cn/h.R21O62BrYrwdxTZ?tk=VRWJ5ufbFqo HU926 '
            '「【政府补贴】Apple/苹果 iPhone 17」'
            '点击链接直接打开 或者 淘宝搜索直接打开'
        ),
        'expected_item_id': None,
    },
]


def _print_curl(taoword: str):
    import json as _json

    cfg = REBATE_CONFIG.get('taobao', {})
    app_id = cfg.get('app_id', '')
    app_secret = cfg.get('app_secret', '')
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    sign_params = {
        'app_id': str(app_id),
        'date': date_str,
        'method': HDK_DEFAULT_METHOD,
        'taoword': taoword,
    }
    sign = TaobaoClient._haodanku_sign(sign_params, app_secret)
    body = {**sign_params, 'sign': sign}
    body_json = _json.dumps(body, ensure_ascii=False)
    print('--- 等价 curl（好单库 v3：JSON body + sign）---')
    print(f"curl -X POST '{HDK_DEFAULT_API_URL}' \\")
    print("  -H 'Content-Type: application/json' \\")
    print(f"  -d '{body_json}'")
    print('---')
    print()


def _resolve_link(raw_input: str) -> str:
    urls = extract_url_from_text(raw_input)
    if urls:
        return urls[0]
    return raw_input.strip()


def _print_result(result: dict, expected_item_id: str = None):
    if result.get('success'):
        print('[成功] 转链成功')
        print(f"  转链方式: {result.get('convert_method', 'unknown')}")
        item_id = str(result.get('item_id', '') or '')
        print(f"  商品 ID: {item_id or 'N/A'}")
        if expected_item_id and item_id != expected_item_id:
            print(f"  ⚠️ 预期商品 ID: {expected_item_id}（请核对解析是否正确）")
        print(f"  商品标题: {result.get('title', 'N/A')}")
        print(f"  原价: {result.get('original_price', 0)}")
        if result.get('final_price'):
            print(f"  券后价: {result.get('final_price', 0)}")
        commission = float(result.get('commission', 0) or 0)
        rebate_rate = COMMISSION_CONFIG.get('taobao_rate', 0.7)
        user_rebate = float(result.get('user_rebate', 0) or 0)
        print(f"  佣金: ¥{commission:.2f}（券后价 × tkrates）")
        print(f"  返利金额: ¥{user_rebate:.2f}（佣金 × {rebate_rate:.0%}）")
        print(f"  推广链接: {result.get('click_url') or result.get('rebate_url', 'N/A')}")
        print(f"  淘口令: {result.get('tpwd', 'N/A')}")
    else:
        print(f"[失败] {result.get('message', '未知错误')}")
        if result.get('raw'):
            print(f"  原始响应: {result.get('raw')}")


async def _run_case(api: RebateAPI, case: dict, index: int, total: int):
    raw_input = case['raw_input']
    expected_item_id = case.get('expected_item_id')
    convert_input = raw_input.strip()
    _print_curl(convert_input)
    result = await api.convert_link(convert_input, 'taobao', wxid=TEST_WXID)
    _print_result(result, expected_item_id)


async def test_taobao_convert():
    api = RebateAPI()
    total = len(TEST_CASES)

    print('=' * 80)
    print('淘宝转链测试（好单库 v3 REST + sign）')
    print('=' * 80)
    print(f'共 {total} 个用例\n')

    for i, case in enumerate(TEST_CASES, 1):
        await _run_case(api, case, i, total)

    print('=' * 80)
    print('全部用例执行完毕')
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(test_taobao_convert())
