"""淘宝转链：好单库 v3 REST analyze.taoword（method + sign 签名）"""

import hashlib
import json
import logging
import re
from datetime import datetime

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

# 官方文档：https://v3.api.haodanku.com/rest
HDK_DEFAULT_API_URL = 'https://v3.api.haodanku.com/rest'
HDK_DEFAULT_METHOD = 'analyze.taoword'

TOP_CONVERT_HINT = (
    '请到淘宝开放平台申请转链权限，或改用好单库：在 config.py 配置 taobao.app_id / app_secret'
)


class TaobaoClient:
    API_URL = 'https://gw.api.taobao.com/router/rest'

    def __init__(self):
        cfg = REBATE_CONFIG['taobao']
        self.app_id = str(cfg.get('app_id') or '')
        self.app_secret = str(cfg.get('app_secret') or '')
        self.api_url = HDK_DEFAULT_API_URL
        self.hdk_method = HDK_DEFAULT_METHOD
        # 以下仅 TOP 转链 / 饿了么·闲鱼·订单同步使用，好单库转链不需要
        self.adzone_id = cfg.get('adzone_id', '')
        self.pid = cfg.get('pid', '')
        self.convert_mode = (cfg.get('convert_mode') or 'item').lower()
        self._last_error = ''
        self.site_id = self._parse_site_id_from_pid()
        # 饿了么/闲鱼/订单同步等仍走 TOP 时使用
        self.app_key = cfg.get('top_app_key') or cfg.get('app_key') or ''
        self.top_app_secret = cfg.get('top_app_secret') or ''

    def _parse_site_id_from_pid(self) -> str:
        parts = (self.pid or '').split('_')
        if len(parts) >= 4:
            return parts[2]
        return ''

    def _haodanku_configured(self) -> bool:
        return not any(is_placeholder(v) for v in (self.app_id, self.app_secret))

    def _top_configured(self) -> bool:
        return not any(
            is_placeholder(v) for v in (self.app_key, self.top_app_secret, self.adzone_id, self.pid)
        )

    async def convert(self, url: str, wxid: str = None) -> dict:
        """商品转链固定走好单库 v3 analyze.taoword（不在 config 中配置 provider）。"""
        return await self._convert_via_haodanku(url, wxid=wxid)

    async def _convert_via_haodanku(self, text: str, wxid: str = None) -> dict:
        if not self._haodanku_configured():
            return config_missing('taobao', ['app_id', 'app_secret'])

        taoword = (text or '').strip()
        if not taoword:
            return api_error('taobao', '请发送淘宝商品链接或淘口令')

        date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sign_params = {
            'app_id': self.app_id,
            'date': date_str,
            'method': self.hdk_method,
            'taoword': taoword,
        }
        sign = self._haodanku_sign(sign_params, self.app_secret)
        payload = {**sign_params, 'sign': sign}

        resp = await http_request(
            'POST',
            self.api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
        )
        result = parse_json_response(resp)

        if not self._haodanku_success(result):
            msg = self._haodanku_error_msg(result) or '好单库转链失败'
            logger.warning('好单库 %s 失败: %s', self.hdk_method, result)
            return api_error('taobao', msg, result)

        data = result.get('data') or {}
        if isinstance(data, list):
            data = data[0] if data else {}

        click_url = self._pick_promo_url(data)
        if not click_url:
            return api_error('taobao', '好单库未返回推广链接', result)

        title = str(data.get('itemtitle') or data.get('title') or data.get('item_name') or '')
        item_id = str(
            data.get('itemid') or data.get('item_id') or data.get('num_iid') or data.get('numIid') or ''
        )
        if not item_id:
            m = re.search(r'[?&]id=(\d+)', click_url)
            if m:
                item_id = m.group(1)
        price = self._to_float(
            data.get('itemprice') or data.get('price') or data.get('zk_final_price') or data.get('final_price')
        )
        final_price = self._to_float(
            data.get('itemendprice') or data.get('final_price') or data.get('zk_final_price')
        )
        if not final_price and price:
            final_price = price
        coupon_amount = self._to_float(
            data.get('couponmoney') or data.get('coupon_amount')
            or data.get('coupon_money') or data.get('coupon_price')
        )

        commission, commission_err = self._parse_haodanku_commission(data)
        if commission_err:
            return api_error('taobao', commission_err, result)

        tpwd = str(
            data.get('taoword') or data.get('tpwd') or data.get('new_tpwd')
            or data.get('coupon_tpwd') or data.get('short_tpwd') or ''
        )

        return success_result(
            'taobao',
            rebate_url=click_url,
            original_url=text,
            title=title,
            original_price=price,
            final_price=final_price,
            coupon_amount=coupon_amount,
            commission=commission,
            item_id=item_id,
            click_url=click_url,
            tpwd=tpwd,
            convert_method='haodanku_analyze.taoword',
        )

    @staticmethod
    def _haodanku_sign(params: dict, app_secret: str) -> str:
        """
        好单库签名：参数按 key 升序拼接 key+value，末尾追加 app_secret，MD5 大写。
        文档示例：app_id+date+method+taoword 拼接后 + secret -> MD5 大写。
        """
        items = sorted((k, str(v)) for k, v in params.items() if v is not None and k != 'sign')
        raw = ''.join(f'{k}{v}' for k, v in items) + str(app_secret)
        return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()

    @staticmethod
    def _haodanku_success(result: dict) -> bool:
        if not isinstance(result, dict):
            return False
        msg = str(result.get('msg') or result.get('message') or '').upper()
        data = result.get('data')
        code = result.get('code')

        if isinstance(data, dict) and TaobaoClient._pick_promo_url(data):
            if code in (200, '200', 1, '1', 0, '0', None):
                return True
        if code in (200, '200'):
            return msg in ('SUCCESS', 'OK', '成功')
        if code in (1, '1'):
            return True
        return False

    @staticmethod
    def _haodanku_error_msg(result: dict) -> str:
        if not isinstance(result, dict):
            return str(result)
        return str(result.get('msg') or result.get('message') or '好单库 API 错误')

    @staticmethod
    def _pick_promo_url(data: dict) -> str:
        if not isinstance(data, dict):
            return ''
        for key in (
            'click_url', 'coupon_click_url', 'coupon_share_url', 'item_url',
            'long_url', 'short_url', 'tklink', 'url', 'cps_long_url', 'cps_short_url',
            'promotion_url', 'item_link', 'link',
        ):
            val = data.get(key)
            if val and str(val).startswith('http'):
                return str(val)
        return ''

    @staticmethod
    def _to_float(value) -> float:
        try:
            if value is None or value == '':
                return 0.0
            return float(str(value).replace('¥', '').replace(',', '').strip())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _parse_haodanku_commission(data: dict) -> tuple:
        """
        好单库 analyze.taoword：佣金 = 券后价(itemendprice) × 佣金比例(tkrates%)。
        无 tkrates 视为未加入淘宝联盟，返回 (None, 提示文案)。
        """
        tkrates_raw = data.get('tkrates')
        if tkrates_raw is None or str(tkrates_raw).strip() == '':
            return None, '该商品未加入淘宝联盟计划，没有优惠'

        rate = TaobaoClient._to_float(tkrates_raw)
        if rate <= 0:
            return None, '该商品未加入淘宝联盟计划，没有优惠'
        if rate > 1:
            rate = rate / 100

        pay_price = TaobaoClient._to_float(
            data.get('itemendprice') or data.get('itemprice') or data.get('price')
        )
        if pay_price <= 0:
            for key in ('commission', 'pub_share_pre_fee', 'predict_money', 'tkmoney'):
                val = TaobaoClient._to_float(data.get(key))
                if val > 0:
                    return round(val, 2), None
            return None, '该商品未加入淘宝联盟计划，没有优惠'

        return round(pay_price * rate, 2), None

    @staticmethod
    def _estimate_commission(data: dict, price: float) -> float:
        if 'tkrates' in data or data.get('itemendprice') is not None:
            commission, _ = TaobaoClient._parse_haodanku_commission(data)
            return commission or 0.0
        for key in ('commission', 'pub_share_pre_fee', 'predict_money', 'tkmoney'):
            val = TaobaoClient._to_float(data.get(key))
            if val > 0:
                return round(val, 2)
        rate = TaobaoClient._to_float(
            data.get('commission_rate') or data.get('tkrate') or data.get('tk_rate')
        )
        if rate > 1:
            rate = rate / 100
        if price and rate:
            return round(price * rate, 2)
        return 0.0

    async def _convert_via_top(self, url: str, wxid: str = None) -> dict:
        if not self._top_configured():
            return config_missing('taobao', ['top_app_key', 'top_app_secret', 'adzone_id', 'pid'])

        if self.convert_mode in ('general', 'auto'):
            general = await self._general_link_convert(url, wxid=wxid)
            if general.get('click_url'):
                info = {}
                if general.get('item_id'):
                    info = await self._get_item_info(general['item_id'])
                return success_result(
                    'taobao',
                    rebate_url=general['click_url'],
                    original_url=url,
                    title=info.get('title', general.get('title', '')),
                    original_price=info.get('price', 0),
                    coupon_amount=info.get('coupon_amount', 0),
                    commission=info.get('commission', 0) or general.get('commission', 0),
                    item_id=general.get('item_id', ''),
                    click_url=general['click_url'],
                    tpwd=general.get('tpwd', ''),
                    convert_method='general_link',
                )
            if self.convert_mode == 'general':
                msg = self._last_error or '万能转链失败'
                return api_error('taobao', msg + '。' + TOP_CONVERT_HINT)

        return await self._convert_by_item_path(url, wxid=wxid)

    async def _convert_by_item_path(self, url: str, wxid: str = None) -> dict:
        item_id = self._regex_item_id(url)
        extract_method = 'regex' if item_id else ''
        if not item_id:
            item_id = await self._extract_item_id(url)
            if item_id:
                extract_method = 'click_extract'

        if not item_id:
            msg = self._last_error or '无法解析商品 ID，请发送标准商品链接或淘口令'
            return api_error('taobao', msg + '。' + TOP_CONVERT_HINT)

        promo = await self._generate_promo(item_id, wxid=wxid)
        click_url = promo.get('click_url', '')
        if not click_url:
            err = self._parse_api_error(promo.get('raw')) or '商品转链未返回推广链接'
            return api_error('taobao', err + '。' + TOP_CONVERT_HINT, promo.get('raw'))

        info = await self._get_item_info(item_id)
        return success_result(
            'taobao',
            rebate_url=click_url,
            original_url=url,
            title=info.get('title', ''),
            original_price=info.get('price', 0),
            coupon_amount=info.get('coupon_amount', 0),
            commission=info.get('commission', 0),
            item_id=item_id,
            click_url=click_url,
            tpwd=promo.get('tpwd', ''),
            convert_method=f'item_convert({extract_method or "id"})',
        )

    def _regex_item_id(self, text: str) -> str:
        patterns = [
            r'[?&]id=(\d+)',
            r'item\.htm[^?]*\?[^#]*id=(\d+)',
            r'itemId[=:](\d+)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ''

    async def _general_link_convert(self, url: str, wxid: str = None) -> dict:
        material_list = json.dumps([{'material_url': url}], ensure_ascii=False)
        extra = {'adzone_id': self.adzone_id, 'material_list': material_list}
        if self.site_id:
            extra['site_id'] = self.site_id
        if wxid:
            extra['external_id'] = str(wxid)[:64]

        result = await self._call('taobao.tbk.dg.general.link.convert', extra)
        if 'error_response' in result:
            err = result['error_response']
            self._last_error = err.get('sub_msg') or err.get('msg', '')
            return {}

        resp = result.get('tbk_dg_general_link_convert_response') or {}
        data = resp.get('data') or resp
        link_dto = data.get('link_info_dto') or data.get('material_url_list') or data
        if isinstance(link_dto, list) and link_dto:
            link_dto = link_dto[0]

        click_url = (
            deep_get(link_dto, 'link_info_dto', 'cps_long_url')
            or link_dto.get('cps_long_url')
            or link_dto.get('cps_short_url')
            or link_dto.get('click_url')
            or ''
        )
        return {
            'click_url': click_url,
            'tpwd': link_dto.get('cps_full_tpwd') or link_dto.get('tpwd') or '',
            'item_id': str(link_dto.get('item_id') or link_dto.get('num_iid') or ''),
            'title': link_dto.get('title', ''),
            'commission': float(link_dto.get('commission') or 0),
        }

    async def _call(self, method: str, extra: dict) -> dict:
        params = {
            'method': method,
            'app_key': self.app_key,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'format': 'json',
            'v': '2.0',
            'sign_method': 'md5',
            **extra,
        }
        params['sign'] = md5_sign(params, self.top_app_secret)
        resp = await http_request('GET', self.API_URL, params=params)
        return parse_json_response(resp)

    def _parse_api_error(self, result) -> str:
        if isinstance(result, dict) and 'error_response' in result:
            err = result['error_response']
            return err.get('sub_msg') or err.get('msg', '')
        return ''

    async def _extract_item_id(self, url: str) -> str:
        result = await self._call('taobao.tbk.item.click.extract', {'url': url})
        if 'error_response' in result:
            err = result['error_response']
            self._last_error = err.get('sub_msg') or err.get('msg', '淘宝 API 错误')
            return ''
        item_id = deep_get(result, 'tbk_item_click_extract_response', 'click_info_dto', 'item_id')
        return str(item_id) if item_id else ''

    async def _generate_promo(self, item_id: str, wxid: str = None) -> dict:
        extra = {'num_iid': item_id, 'pid': self.pid, 'adzone_id': self.adzone_id}
        if wxid:
            extra['external_id'] = str(wxid)[:64]

        result = await self._call('taobao.tbk.item.convert', extra)
        if 'error_response' in result:
            err = result['error_response']
            self._last_error = err.get('sub_msg') or err.get('msg', '')
            return {'click_url': '', 'tpwd': '', 'raw': result}

        coupon_list = deep_get(
            result, 'tbk_item_convert_response', 'results', 'tbk_coupon', default=[]
        )
        if coupon_list:
            item = coupon_list[0] if isinstance(coupon_list, list) else coupon_list
            return {
                'click_url': item.get('click_url', '') or item.get('coupon_click_url', ''),
                'tpwd': item.get('tpwd', '') or item.get('coupon_tpwd', ''),
            }
        return {'click_url': '', 'tpwd': '', 'raw': result}

    async def _get_item_info(self, item_id: str) -> dict:
        result = await self._call('taobao.tbk.item.info.upgrade.get', {
            'item_id': item_id,
            'num_iids': item_id,
        })
        if 'error_response' in result:
            result = await self._call('taobao.tbk.item.info.get', {'num_iids': item_id})
        if 'error_response' in result:
            return {}

        items = deep_get(
            result, 'tbk_item_info_upgrade_get_response', 'results', 'tbk_item_detail', default=[]
        )
        if not items:
            items = deep_get(
                result, 'tbk_item_info_get_response', 'results', 'n_tbk_item', default=[]
            )
        if not items:
            return {}
        item = items[0] if isinstance(items, list) else items
        price = float(item.get('zk_final_price') or item.get('reserve_price') or 0)
        commission_rate = float(item.get('commission_rate') or 0) / 100
        return {
            'title': item.get('title', ''),
            'price': price,
            'commission': round(price * commission_rate, 2) if price and commission_rate else 0,
            'coupon_amount': 0,
        }
