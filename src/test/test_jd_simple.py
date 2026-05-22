"""
京东联盟转链测试（默认 byunionid，可选 common.get）

用法（在项目根目录 robot/ 下）:
  .\\.venv\\Scripts\\python.exe .\\src\\test\\test_jd_simple.py
  .\\.venv\\Scripts\\python.exe .\\src\\test\\test_jd_simple.py "https://item.jd.com/100012043978.html"

配置: config/config.py 中 REBATE_CONFIG['jd']
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from urllib.parse import quote

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.config import COMMISSION_CONFIG, REBATE_CONFIG
from src.platforms.base import is_placeholder, md5_sign
from src.platforms.jd import JDClient, METHOD_BYUNIONID, METHOD_COMMON
from src.rebate_api import RebateAPI, extract_url_from_text

TEST_WXID = 'test_user_001'

TEST_CASES = [
    {
        'name': '商品页链接（示例，请换成你的链接）',
        'raw_input': 'https://item.jd.com/100012043978.html',
    },
    {
        'name': '短链（可选）',
        'raw_input': 'https://u.jd.com/xxxxxxx',
    },
]


def _jd_config_status() -> tuple[bool, list[str]]:
    cfg = REBATE_CONFIG.get('jd', {})
    method = (cfg.get('promotion_method') or 'byunionid').lower()
    missing = []
    for key in ('app_key', 'app_secret'):
        if not cfg.get(key) or is_placeholder(cfg.get(key, '')):
            missing.append(key)
    if method == 'common':
        if not cfg.get('site_id') or is_placeholder(cfg.get('site_id', '')):
            missing.append('site_id')
    elif method == 'byunionid':
        for key in ('union_id', 'position_id'):
            if not cfg.get(key) or is_placeholder(cfg.get(key, '')):
                missing.append(key)
    else:
        has_union = cfg.get('union_id') and not is_placeholder(cfg.get('union_id', ''))
        has_site = cfg.get('site_id') and not is_placeholder(cfg.get('site_id', ''))
        if not has_union and not has_site:
            missing.append('union_id 或 site_id（至少一种）')
    return len(missing) == 0, missing


def _print_config_hint():
    cfg = REBATE_CONFIG.get('jd', {})
    ok, missing = _jd_config_status()
    method = cfg.get('promotion_method') or 'byunionid'
    print('--- 京东联盟配置 ---')
    print(f"  promotion_method: {method}")
    print(f"  app_key:     {'已配置' if cfg.get('app_key') and not is_placeholder(str(cfg.get('app_key'))) else '未配置'}")
    print(f"  union_id:    {cfg.get('union_id') or '(空)'}")
    print(f"  position_id: {cfg.get('position_id') or '(空)'}")
    print(f"  site_id:     {cfg.get('site_id') or '(空，common 回退用)'}")
    if missing:
        print(f"  ⚠️ 缺少或未填写: {', '.join(missing)}")
    print('---\n')
    return ok


def _print_request_hint(material_id: str, wxid: str = None):
    cfg = REBATE_CONFIG.get('jd', {})
    client = JDClient()
    method = (cfg.get('promotion_method') or 'byunionid').lower()
    api_method = METHOD_BYUNIONID if method != 'common' else METHOD_COMMON

    if api_method == METHOD_BYUNIONID:
        req = client._build_byunionid_req(material_id, wxid)
    else:
        req = client._build_common_req(material_id)

    param_json = {'promotionCodeReq': req}
    params = {
        'method': api_method,
        'app_key': cfg.get('app_key', ''),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'format': 'json',
        'v': '1.0',
        'sign_method': 'md5',
        'param_json': json.dumps(param_json, ensure_ascii=False),
    }
    app_secret = cfg.get('app_secret', '')
    if not is_placeholder(app_secret):
        params['sign'] = md5_sign(params, app_secret)

    print('--- 转链 API 要点 ---')
    print(f"  接口: GET {JDClient.API_URL}")
    print(f"  method: {api_method}")
    print(f"  请求体 promotionCodeReq: {json.dumps(req, ensure_ascii=False)}")
    if params.get('sign'):
        q = '&'.join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
        print(f"  调试 URL（截断）:\n  {JDClient.API_URL}?{q[:500]}...")
    print('---\n')


def _print_result(result: dict):
    if result.get('success'):
        print('[成功] 转链成功')
        print(f"  转链 API: {result.get('convert_api', 'N/A')}")
        print(f"  平台: {result.get('platform', 'jd')}")
        print(f"  商品标题: {result.get('title', 'N/A')}")
        print(f"  原价: ¥{float(result.get('original_price', 0) or 0):.2f}")
        commission = float(result.get('commission', 0) or 0)
        rebate_rate = COMMISSION_CONFIG.get('jd_rate', 0.7)
        user_rebate = float(result.get('user_rebate', 0) or 0)
        print(f"  佣金: ¥{commission:.2f}")
        print(f"  返利金额: ¥{user_rebate:.2f}（佣金 × {rebate_rate:.0%}）")
        item_id = result.get('item_id')
        if item_id:
            print(f"  商品 ID: {item_id}")
        if result.get('sub_union_id'):
            print(f"  subUnionId: {result.get('sub_union_id')}")
        print(f"  推广链接: {result.get('click_url') or result.get('rebate_url', 'N/A')}")
        if result.get('weChatShortLink'):
            print(f"  微信短链: {result.get('weChatShortLink')}")
    else:
        print(f"[失败] {result.get('message', '未知错误')}")
        raw = result.get('raw')
        if raw:
            text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            print(f"  原始响应: {text[:800]}{'...' if len(text) > 800 else ''}")


async def _run_case(api: RebateAPI, case: dict, index: int, total: int):
    name = case['name']
    raw_input = case['raw_input'].strip()

    print('=' * 80)
    print(f'用例 {index}/{total}: {name}')
    print('=' * 80)
    print(f'\n原始输入:\n{raw_input}\n')

    urls = extract_url_from_text(raw_input)
    convert_input = urls[0] if urls else raw_input
    if urls:
        print(f'提取链接: {convert_input}\n')

    _print_request_hint(convert_input, wxid=TEST_WXID)
    result = await api.convert_link(convert_input, 'jd', wxid=TEST_WXID)
    print(f'绑定用户 wxid: {TEST_WXID}（subUnionId 跟单，须京东开通权限）\n')
    _print_result(result)
    print()


async def test_jd_convert(extra_url: str = None):
    print('=' * 80)
    print('京东联盟转链测试')
    print('=' * 80)
    print()

    if not _print_config_hint():
        print('请先在 config/config.py 填写 REBATE_CONFIG["jd"] 后再运行。\n')
        return

    cases = list(TEST_CASES)
    if extra_url:
        cases = [{'name': '命令行传入链接', 'raw_input': extra_url}] + cases

    runnable = [
        c for c in cases
        if c['raw_input'] and 'xxxx' not in c['raw_input'].lower()
    ]
    if not runnable:
        print('无有效测试链接。请修改 TEST_CASES 或传入 URL 参数。\n')
        return

    api = RebateAPI()
    total = len(runnable)
    print(f'共 {total} 个用例\n')

    for i, case in enumerate(runnable, 1):
        await _run_case(api, case, i, total)

    print('=' * 80)
    print('全部用例执行完毕')
    print('=' * 80)


if __name__ == '__main__':
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(test_jd_convert(url_arg))
