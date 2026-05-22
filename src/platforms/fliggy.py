"""飞猪旅行推广 - 阿里妈妈 alibaba.fliggy.promote.activity.link"""

import json
import logging

from config.config import REBATE_CONFIG, TRAVEL_CONFIG
from src.platforms.alimama_base import AliMamaBase
from src.platforms.base import api_error, config_missing, deep_get, success_result

logger = logging.getLogger(__name__)

FLIGGY_HINT = (
    '请在飞猪推广者后台创建 media_id、position_id，'
    '并向运营获取 activity_id，申请 alibaba.fliggy.promote.activity.link 权限'
)


class FliggyClient(AliMamaBase):
    def __init__(self):
        super().__init__('fliggy', fallback_taobao=True)
        cfg = REBATE_CONFIG.get('fliggy', {}) or {}
        legacy = TRAVEL_CONFIG or {}
        self.activity_id = cfg.get('activity_id') or legacy.get('fliggy_activity_id', '')
        self.position_id = cfg.get('position_id') or legacy.get('fliggy_position_id', '')
        self.media_id = cfg.get('media_id') or legacy.get('fliggy_media_id', '')
        self.qr_code = bool(cfg.get('qr_code', False))

    def _configured(self):
        return super()._configured(self.activity_id, self.position_id, self.media_id)

    async def convert(self, url: str, wxid: str = None) -> dict:
        if url and ('fliggy.com' in url or 'feizhu.com' in url or 'alitrip.com' in url):
            return await self.get_activity_link(wxid=wxid, material_url=url)
        if not self._configured():
            return config_missing('fliggy', ['activity_id', 'position_id', 'media_id'])
        return await self.get_activity_link(wxid=wxid)

    async def get_activity_link(self, wxid: str = None, material_url: str = None) -> dict:
        if not self._configured():
            return config_missing('fliggy', ['activity_id', 'position_id', 'media_id'])

        req_obj = {
            'activity_id': str(self.activity_id),
            'position_id': int(self.position_id),
            'media_id': int(self.media_id),
            'qr_code': self.qr_code,
        }
        result = await self.call(
            'alibaba.fliggy.promote.activity.link',
            {'promotion_activity_link_request': json.dumps(req_obj, ensure_ascii=False)},
        )
        err = self.parse_error(result)
        if err:
            return api_error('fliggy', f'{err}。{FLIGGY_HINT}', result)

        resp = result.get('alibaba_fliggy_promote_activity_link_response') or {}
        if resp.get('result_code') and resp.get('result_code') != 'SUCCESS':
            msg = resp.get('result_message') or resp.get('result_code')
            return api_error('fliggy', f'{msg}。{FLIGGY_HINT}', result)

        model = resp.get('model') or {}
        link_data_raw = model.get('link_data') or ''
        rebate_url = self._pick_link(link_data_raw, wxid=wxid)
        if not rebate_url and material_url:
            rebate_url = material_url
        if not rebate_url:
            return api_error('fliggy', f'未获取到飞猪推广链接。{FLIGGY_HINT}', result)

        return success_result(
            'fliggy',
            rebate_url=rebate_url,
            original_url=material_url or f'fliggy:activity:{self.activity_id}',
            title='飞猪旅行',
            commission=0,
            convert_method='fliggy_promote_activity',
            activity_id=str(self.activity_id),
        )

    @staticmethod
    def _pick_link(link_data_raw: str, wxid: str = None) -> str:
        if not link_data_raw:
            return ''
        try:
            data = json.loads(link_data_raw)
            if isinstance(data, str):
                data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return str(link_data_raw) if link_data_raw.startswith('http') else ''

        deliver = deep_get(data, 'deliverInfo') or data.get('deliverInfo') or data
        for channel in ('wechat', 'web', 'taobao', 'alipay'):
            block = deliver.get(channel) or {}
            for key in (
                'wxRouterShortLink', 'wxShortLink', 'shortLink', 'longLink',
            ):
                val = block.get(key)
                if val and isinstance(val, str) and not val.startswith('#'):
                    if wxid and '__SHT_OUT_USER_ID__' in val:
                        val = val.replace('__SHT_OUT_USER_ID__', str(wxid)[:64])
                    return val
        return ''
