"""微信小店 / 推客带货 - 联盟带货机构 API"""

import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse, parse_qs

from config.config import REBATE_CONFIG
from src.platforms.base import (
    api_error,
    config_missing,
    deep_get,
    http_request,
    is_placeholder,
    parse_json_response,
    success_result,
)

logger = logging.getLogger(__name__)

WEIXIN_STORE_HINT = (
    '需注册「联盟带货机构」账号，配置 app_id/app_secret/sharer_appid，'
    '并申请 channels/ec/promoter/get_product_promotion_link_info 权限'
)


class WeixinStoreClient:
    TOKEN_URL = 'https://api.weixin.qq.com/cgi-bin/token'
    PROMO_LINK_URL = (
        'https://api.weixin.qq.com/channels/ec/promoter/get_product_promotion_link_info'
    )

    def __init__(self):
        cfg = REBATE_CONFIG.get('weixin_store', {}) or {}
        self.app_id = cfg.get('app_id', '')
        self.app_secret = cfg.get('app_secret', '')
        self.access_token = cfg.get('access_token', '')
        self.sharer_appid = cfg.get('sharer_appid', '')
        self.sharer_openid = cfg.get('sharer_openid', '')
        self.head_supplier_appid = cfg.get('head_supplier_appid', '')
        self._token_expires_at = 0

    def _configured(self):
        if is_placeholder(self.app_id) or is_placeholder(self.app_secret):
            return False
        if is_placeholder(self.sharer_appid) and is_placeholder(self.sharer_openid):
            return False
        return True

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing(
                'weixin_store',
                ['app_id', 'app_secret', 'sharer_appid 或 sharer_openid'],
            )

        product_id, shop_appid, short_link = self._parse_product_url(url)
        token = await self._ensure_access_token()
        if not token:
            return api_error('weixin_store', '获取 access_token 失败，请检查 app_id/app_secret')

        body = {}
        if self.sharer_appid:
            body['sharer_appid'] = self.sharer_appid
        elif self.sharer_openid:
            body['sharer_openid'] = self.sharer_openid
        if self.head_supplier_appid:
            body['head_supplier_appid'] = self.head_supplier_appid

        if short_link:
            body['product_short_link'] = short_link
        elif product_id:
            body['product_id'] = int(product_id)
            if shop_appid:
                body['shop_appid'] = shop_appid
            elif self.head_supplier_appid:
                body['shop_appid'] = self.head_supplier_appid
        else:
            return api_error(
                'weixin_store',
                '无法识别微信小店商品链接，请发送 store.weixin.qq.com 商品短链或带 product_id 的链接',
            )

        api_url = f'{self.PROMO_LINK_URL}?access_token={token}'
        resp = await http_request('POST', api_url, json=body)
        result = parse_json_response(resp)

        errcode = int(result.get('errcode', -1) or -1)
        if errcode != 0:
            errmsg = result.get('errmsg') or str(result)
            return api_error('weixin_store', f'{errmsg}。{WEIXIN_STORE_HINT}', result)

        click_url = result.get('http_short_link') or result.get('short_link') or ''
        if not click_url:
            return api_error('weixin_store', f'未返回推广链接。{WEIXIN_STORE_HINT}', result)

        pid = str(result.get('product_id') or product_id or '')
        return success_result(
            'weixin_store',
            rebate_url=click_url,
            original_url=url,
            title='微信小店商品',
            item_id=pid,
            shop_appid=result.get('shop_appid') or shop_appid or '',
            convert_method='promoter_link',
        )

    async def _ensure_access_token(self) -> Optional[str]:
        if self.access_token and not is_placeholder(self.access_token):
            if time.time() < self._token_expires_at:
                return self.access_token

        params = {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret,
        }
        resp = await http_request('GET', self.TOKEN_URL, params=params)
        data = parse_json_response(resp)
        token = data.get('access_token')
        if not token:
            logger.warning('微信小店 token 获取失败: %s', data)
            return None
        self.access_token = token
        expires_in = int(data.get('expires_in') or 7200)
        self._token_expires_at = time.time() + max(expires_in - 120, 60)
        return token

    @staticmethod
    def _parse_product_url(url: str):
        text = (url or '').strip()
        product_id = ''
        shop_appid = ''
        short_link = ''

        if 'store.weixin.qq.com' in text or 'channels.weixin.qq.com' in text:
            short_link = text.split()[0] if text else text

        parsed = urlparse(text)
        qs = parse_qs(parsed.query)
        product_id = (qs.get('product_id') or qs.get('productId') or [''])[0]
        shop_appid = (qs.get('shop_appid') or qs.get('shopAppid') or [''])[0]

        m = re.search(r'product[_-]?id[=:](\d+)', text, re.I)
        if m:
            product_id = m.group(1)

        return product_id, shop_appid, short_link
