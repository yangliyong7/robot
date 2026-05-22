"""京东联盟真实 API（微信导购优先 byunionid，可选 common.get 回退）"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from config.config import REBATE_CONFIG
from src.platforms.base import (
    api_error,
    config_missing,
    deep_get,
    http_request,
    is_placeholder,
    md5_sign,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)

METHOD_BYUNIONID = 'jd.union.open.promotion.byunionid.get'
METHOD_COMMON = 'jd.union.open.promotion.common.get'


class JDClient:
    API_URL = 'https://api.jd.com/routerjson'

    def __init__(self):
        cfg = REBATE_CONFIG['jd']
        self.app_key = cfg['app_key']
        self.app_secret = cfg['app_secret']
        self.site_id = str(cfg.get('site_id', '') or '')
        self.union_id = str(cfg.get('union_id', '') or '')
        self.position_id = str(cfg.get('position_id', '') or '')
        self.promotion_method = (cfg.get('promotion_method') or 'byunionid').lower()
        self.chain_type = int(cfg.get('chain_type') or 2)

    def _keys_ok(self) -> bool:
        return not any(is_placeholder(v) for v in (self.app_key, self.app_secret))

    def _byunionid_ready(self) -> bool:
        return (
            self._keys_ok()
            and self.union_id
            and not is_placeholder(self.union_id)
            and self.position_id
            and not is_placeholder(self.position_id)
        )

    def _common_ready(self) -> bool:
        return self._keys_ok() and self.site_id and not is_placeholder(self.site_id)

    def _configured(self) -> bool:
        if self.promotion_method == 'common':
            return self._common_ready()
        if self.promotion_method == 'byunionid':
            return self._byunionid_ready()
        return self._byunionid_ready() or self._common_ready()

    @staticmethod
    def _sanitize_sub_union(wxid: str) -> str:
        s = re.sub(r'[^\w\-]', '_', (wxid or '').strip())[:80]
        return s or 'user'

    @staticmethod
    def _extract_sku_id(url: str) -> str:
        if not url:
            return ''
        if url.isdigit():
            return url
        m = re.search(r'item\.jd\.com/(\d+)', url)
        if m:
            return m.group(1)
        m = re.search(r'jingfen\.jd\.com/detail/(\d+)', url)
        if m:
            return m.group(1)
        return ''

    @staticmethod
    def _scene_id_for_url(url: str) -> Optional[int]:
        if 'item.jd.com' in url or '3.cn' in url or (url and url.isdigit()):
            return 2
        if 'jingfen.jd.com' in url:
            return 1
        return None

    def _build_byunionid_req(self, url: str, wxid: Optional[str] = None) -> dict:
        req = {
            'materialId': url,
            'unionId': self.union_id,
            'positionId': self.position_id,
            'chainType': self.chain_type,
        }
        scene = self._scene_id_for_url(url)
        if scene is not None:
            req['sceneId'] = scene
        if wxid:
            req['subUnionId'] = self._sanitize_sub_union(wxid)
        return req

    def _build_common_req(self, url: str) -> dict:
        req = {
            'materialId': url,
            'siteId': self.site_id,
            'positionId': self.position_id or self.site_id,
        }
        scene = self._scene_id_for_url(url)
        if scene is not None:
            req['sceneId'] = scene
        return req

    async def convert(self, url: str, wxid: Optional[str] = None) -> dict:
        if not self._configured():
            need = ['app_key', 'app_secret']
            if self.promotion_method == 'common':
                need.append('site_id')
            else:
                need.extend(['union_id', 'position_id'])
            return config_missing('jd', need)

        methods = self._resolve_methods()
        last_err: Optional[dict] = None

        for method in methods:
            if method == METHOD_BYUNIONID:
                if not self._byunionid_ready():
                    continue
                param_json = {'promotionCodeReq': self._build_byunionid_req(url, wxid)}
            else:
                if not self._common_ready():
                    continue
                param_json = {'promotionCodeReq': self._build_common_req(url)}

            result = await self._call(method, param_json)
            parsed, err = self._parse_promotion_response(method, result, url)
            if parsed:
                parsed['convert_api'] = (
                    'byunionid' if method == METHOD_BYUNIONID else 'common'
                )
                if wxid and method == METHOD_BYUNIONID:
                    parsed['sub_union_id'] = self._sanitize_sub_union(wxid)
                sku = self._extract_sku_id(url)
                if sku:
                    parsed['item_id'] = sku
                return parsed
            last_err = err
            raw = err.get('raw') if err else None
            if isinstance(raw, dict) and str(raw.get('code')) == '403':
                logger.info('京东 %s 无权限，尝试下一转链方式', method)
                continue

        if last_err:
            msg = last_err.get('message', '京东转链失败')
            if '403' in msg or '无访问权限' in msg:
                msg += '（请向 cps-qxsq@jd.com 申请 byunionid 接口权限，详见 docs/README.md）'
            return api_error('jd', msg, last_err.get('raw'))
        return api_error('jd', '京东转链失败：未配置可用的转链方式')

    def _resolve_methods(self) -> Tuple[str, ...]:
        if self.promotion_method == 'byunionid':
            return (METHOD_BYUNIONID,)
        if self.promotion_method == 'common':
            return (METHOD_COMMON,)
        order: Tuple[str, ...] = ()
        if self._byunionid_ready():
            order += (METHOD_BYUNIONID,)
        if self._common_ready():
            order += (METHOD_COMMON,)
        return order or (METHOD_BYUNIONID,)

    def _parse_promotion_response(
        self, method: str, result: dict, url: str
    ) -> Tuple[Optional[dict], Optional[dict]]:
        prefix = method.replace('.', '_')
        resp_key = f'{prefix}_responce'
        data = result.get(resp_key) or result.get(f'{prefix}_response', {})
        code = data.get('code')
        if str(code) != '0' and code != 0:
            return None, {
                'message': data.get('message') or str(result),
                'raw': result,
            }

        inner = data.get('getResult')
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                inner = {}
        if isinstance(inner, dict) and str(inner.get('code')) not in ('0', '200', ''):
            msg = inner.get('message') or '京东转链失败'
            icode = str(inner.get('code'))
            if icode == '400' and method == METHOD_COMMON:
                msg += (
                    '（site_id 须为网站管理里的网站ID，不能填导购媒体id；'
                    '或改用 promotion_method=byunionid）'
                )
            return None, {'message': msg, 'raw': inner}

        click_url = (
            deep_get(inner, 'data', 'clickURL')
            or deep_get(inner, 'data', 'shortURL')
            or deep_get(inner, 'clickURL')
            or deep_get(inner, 'shortURL')
        )
        if not click_url:
            return None, {'message': '未获取到京东推广链接', 'raw': result}

        goods_info = deep_get(inner, 'data') or {}
        title = goods_info.get('skuName') or goods_info.get('goodsName') or '京东商品'
        price = float(goods_info.get('price') or goods_info.get('wlprice') or 0)
        commission = float(
            goods_info.get('commission') or goods_info.get('commision') or 0
        )

        extra: Dict[str, Any] = {}
        for key in ('weChatShortLink', 'jCommand', 'jShortCommand'):
            val = deep_get(inner, 'data', key) or inner.get(key)
            if val:
                extra[key] = val

        return (
            success_result(
                'jd',
                rebate_url=click_url,
                original_url=url,
                title=title,
                original_price=price,
                commission=commission,
                **extra,
            ),
            None,
        )

    async def _call(self, method: str, param_json: dict) -> dict:
        params = {
            'method': method,
            'app_key': self.app_key,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'json',
            'v': '1.0',
            'sign_method': 'md5',
            'param_json': json.dumps(param_json, ensure_ascii=False),
        }
        params['sign'] = md5_sign(params, self.app_secret)
        resp = await http_request('GET', self.API_URL, params=params)
        return parse_json_response(resp)
