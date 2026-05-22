"""闲鱼联盟 - 淘宝开放平台 alibaba.idle.affiliate.*"""

import logging
import re

from config.config import REBATE_CONFIG
from src.platforms.alimama_base import AliMamaBase
from src.platforms.base import api_error, config_missing, success_result

logger = logging.getLogger(__name__)

XIANYU_HINT = (
    '请在阿里妈妈开放平台申请「闲鱼联盟」权限：'
    'alibaba.idle.affiliate.general.link.convert、'
    'alibaba.idle.affiliate.cps.income.details.query'
)


class XianyuClient(AliMamaBase):
    def __init__(self):
        super().__init__('xianyu', fallback_taobao=True)
        cfg = REBATE_CONFIG.get('xianyu', {}) or {}
        self.media_id = cfg.get('media_id', '')
        self.media_name = cfg.get('media_name', 'rebate_bot')

    def _configured(self):
        return super()._configured()

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('xianyu', ['app_key/app_secret/adzone_id（可复用 taobao 配置）'])

        material_type, payload = self._build_material(url)
        extra = {
            'material_type': str(material_type),
            'pid': self.pid,
            **payload,
        }
        if wxid:
            extra['external_id'] = str(wxid)[:64]
        if self.media_id:
            extra['media_id'] = str(self.media_id)
        if self.media_name:
            extra['media_name'] = str(self.media_name)

        result = await self.call('alibaba.idle.affiliate.general.link.convert', extra)
        err = self.parse_error(result)
        if err:
            return api_error('xianyu', f'{err}。{XIANYU_HINT}', result)

        resp = (
            result.get('alibaba_idle_affiliate_general_link_convert_response')
            or result.get('result') or {}
        )
        data = resp.get('data') or resp.get('result') or resp
        if isinstance(data, list) and data:
            data = data[0]

        click_url = (
            self.first_click_url(data)
            or data.get('deeplink', '')
            or data.get('short_tpwd', '')
        )
        tpwd = data.get('short_tpwd') or data.get('tpwd') or ''
        if not click_url and tpwd:
            click_url = tpwd

        if not click_url:
            return api_error('xianyu', f'闲鱼转链未返回推广链接。{XIANYU_HINT}', result)

        title = data.get('title') or '闲鱼商品'
        price = float(data.get('reserve_price') or data.get('price') or 0)
        commission_rate = float(data.get('commission_rate') or 0) / 100 if data.get('commission_rate') else 0
        commission = float(data.get('commission') or 0) or round(price * commission_rate, 2)

        return success_result(
            'xianyu',
            rebate_url=click_url,
            original_url=url,
            title=title,
            original_price=price,
            commission=commission,
            item_id=str(data.get('item_id') or data.get('num_iid') or ''),
            tpwd=tpwd,
            convert_method='idle_affiliate',
        )

    def _build_material(self, url: str):
        text = (url or '').strip()
        item_id = self._extract_item_id(text)
        if item_id:
            return 1, {'item_ids': item_id, 'plain_item_ids': item_id}
        if self._looks_like_xy_pwd(text):
            return 4, {'xy_url': text}
        return 4, {'xy_url': text}

    @staticmethod
    def _looks_like_xy_pwd(text: str) -> bool:
        return bool(re.search(r'闲鱼|复制|口令|￥|¥', text))

    @staticmethod
    def _extract_item_id(text: str) -> str:
        patterns = [
            r'[?&]id=(\d+)',
            r'itemId[=:](\d+)',
            r'item_id[=:](\d+)',
            r'goofish\.com/item\?[^#]*id=(\d+)',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1)
        return ''
