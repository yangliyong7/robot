"""饿了么联盟 - 淘宝联盟官方活动转链 taobao.tbk.activity.info.get"""

import logging

from config.config import LOCAL_LIFE_CONFIG, REBATE_CONFIG
from src.platforms.alimama_base import AliMamaBase
from src.platforms.base import api_error, config_missing, deep_get, success_result

logger = logging.getLogger(__name__)

ELEME_HINT = (
    '请在阿里妈妈「活动推广」获取饿了么会场 activity_material_id，'
    '并申请 taobao.tbk.activity.info.get 权限'
)


class ElemeClient(AliMamaBase):
    def __init__(self):
        super().__init__('eleme', fallback_taobao=True)
        cfg = REBATE_CONFIG.get('eleme', {}) or {}
        legacy_pid = LOCAL_LIFE_CONFIG.get('eleme_pid', '')
        self.activity_material_id = (
            cfg.get('activity_material_id')
            or cfg.get('activity_id')
            or '10144'
        )
        self.relation_id = cfg.get('relation_id') or legacy_pid or ''
        self.union_id = cfg.get('union_id', '')

    def _configured(self):
        return super()._configured(self.activity_material_id)

    async def convert(self, url: str, wxid: str = None) -> dict:
        """支持传入饿了么活动页 URL，或空 URL 时返回默认红包活动链"""
        if not self._configured():
            return config_missing(
                'eleme',
                ['activity_material_id', 'adzone_id（可复用 taobao）'],
            )
        return await self.get_activity_link(wxid=wxid, material_url=url or None)

    async def get_activity_link(self, wxid: str = None, material_url: str = None) -> dict:
        extra = {
            'adzone_id': self.adzone_id,
            'activity_material_id': str(self.activity_material_id),
            'platform': '2',
        }
        if self.site_id:
            extra['site_id'] = self.site_id
        if self.relation_id:
            extra['relation_id'] = str(self.relation_id)
        if self.union_id:
            extra['union_id'] = str(self.union_id)
        if wxid:
            extra['unid'] = str(wxid)[:64]
        if material_url:
            extra['material_url'] = material_url

        result = await self.call('taobao.tbk.activity.info.get', extra)
        err = self.parse_error(result)
        if err:
            return api_error('eleme', f'{err}。{ELEME_HINT}', result)

        resp = result.get('tbk_activity_info_get_response') or {}
        data = resp.get('data') or resp
        if isinstance(data, list) and data:
            data = data[0]

        click_url = self.first_click_url(data)
        tpwd = data.get('click_tpwd') or data.get('tpwd') or data.get('coupon_tpwd') or ''
        wx_qrcode = data.get('wx_qrcode_url') or data.get('wx_qrcode') or ''

        if not click_url and tpwd:
            click_url = tpwd
        if not click_url:
            return api_error('eleme', f'未获取到饿了么推广链接。{ELEME_HINT}', result)

        title = data.get('title') or data.get('page_name') or '饿了么天天领红包'
        commission = float(data.get('commission') or 0)

        return success_result(
            'eleme',
            rebate_url=click_url,
            original_url=material_url or f'eleme:activity:{self.activity_material_id}',
            title=title,
            commission=commission,
            tpwd=tpwd,
            wx_qrcode=wx_qrcode,
            activity_id=str(self.activity_material_id),
            convert_method='tbk_activity',
        )
