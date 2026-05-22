"""淘票票 / 大麦电影 - 淘宝开放平台 film API + 活动转链"""

import logging

from config.config import REBATE_CONFIG
from src.platforms.alimama_base import AliMamaBase
from src.platforms.base import api_error, config_missing, deep_get, success_result

logger = logging.getLogger(__name__)

TTP_HINT = (
    '请在阿里妈妈申请 taobao.film.open.* 与 taobao.tbk.activity.info.get 权限，'
    '并配置淘票票活动 activity_material_id'
)


class TaopiaopiaoClient(AliMamaBase):
    def __init__(self):
        super().__init__('taopiaopiao', fallback_taobao=True)
        cfg = REBATE_CONFIG.get('taopiaopiao', {}) or {}
        self.activity_material_id = cfg.get('activity_material_id') or cfg.get('activity_id') or ''
        self.default_city = cfg.get('default_city', '北京')
        self.city_code = cfg.get('city_code', 0)

    def _configured(self):
        return super()._configured()

    async def convert(self, url: str, wxid: str = None) -> dict:
        if not self._configured():
            return config_missing('taopiaopiao', ['adzone_id（可复用 taobao）'])
        if url and any(k in url.lower() for k in ('taopiaopiao', 'damai.cn', 'piao.cn')):
            if self.activity_material_id:
                return await self.get_activity_link(wxid=wxid, material_url=url)
            return success_result(
                'taopiaopiao',
                rebate_url=url,
                original_url=url,
                title='淘票票/大麦',
                commission=0,
                convert_method='passthrough',
            )
        if self.activity_material_id:
            return await self.get_activity_link(wxid=wxid)
        return config_missing('taopiaopiao', ['activity_material_id'])

    async def get_activity_link(self, wxid: str = None, material_url: str = None) -> dict:
        if not self._configured() or not self.activity_material_id:
            return config_missing('taopiaopiao', ['activity_material_id', 'adzone_id'])

        extra = {
            'adzone_id': self.adzone_id,
            'activity_material_id': str(self.activity_material_id),
            'platform': '2',
        }
        if self.site_id:
            extra['site_id'] = self.site_id
        if wxid:
            extra['unid'] = str(wxid)[:64]
        if material_url:
            extra['material_url'] = material_url

        result = await self.call('taobao.tbk.activity.info.get', extra)
        err = self.parse_error(result)
        if err:
            return api_error('taopiaopiao', f'{err}。{TTP_HINT}', result)

        resp = result.get('tbk_activity_info_get_response') or {}
        data = resp.get('data') or resp
        if isinstance(data, list) and data:
            data = data[0]

        click_url = self.first_click_url(data)
        tpwd = data.get('click_tpwd') or data.get('tpwd') or ''
        if not click_url and tpwd:
            click_url = tpwd
        if not click_url:
            return api_error('taopiaopiao', f'未获取到淘票票推广链接。{TTP_HINT}', result)

        return success_result(
            'taopiaopiao',
            rebate_url=click_url,
            original_url=material_url or f'taopiaopiao:activity:{self.activity_material_id}',
            title=data.get('title') or data.get('page_name') or '淘票票电影票',
            commission=float(data.get('commission') or 0),
            tpwd=tpwd,
            convert_method='tbk_activity',
        )

    async def search_movies(self, keyword: str = '', city: str = None, page_size: int = 10) -> dict:
        """查询热映/即将上映影片 taobao.film.open.show.nowandsoon.yidong.get.vii"""
        if not self._configured():
            return {'success': False, 'message': config_missing('taopiaopiao', ['app_key']).get('message')}

        extra = {
            'platform': str(self.city_code or 0),
            'page_index': '0',
            'page_size': str(min(page_size, 30)),
        }
        result = await self.call('taobao.film.open.show.nowandsoon.yidong.get.vii', extra)
        err = self.parse_error(result)
        if err:
            return {'success': False, 'message': f'{err}。{TTP_HINT}', 'raw': result}

        resp = result.get('film_open_show_nowandsoon_yidong_get_vii_response') or {}
        if resp.get('return_code') not in (None, '0', 0):
            return {
                'success': False,
                'message': resp.get('return_message') or '淘票票影片查询失败',
                'raw': result,
            }

        shows = deep_get(resp, 'return_value', 'show') or resp.get('return_value') or []
        if isinstance(shows, dict):
            shows = shows.get('show') or [shows]
        if not isinstance(shows, list):
            shows = [shows] if shows else []

        keyword_lower = (keyword or '').lower()
        if keyword_lower:
            shows = [
                s for s in shows
                if keyword_lower in str(s.get('show_name', '')).lower()
                or keyword_lower in str(s.get('leading_role', '')).lower()
            ]

        movies = []
        for item in shows[:page_size]:
            movies.append({
                'id': item.get('show_id'),
                'title': item.get('show_name', ''),
                'score': item.get('score', ''),
                'director': item.get('director', ''),
                'leading_role': item.get('leading_role', ''),
                'status': item.get('status', ''),
                'open_time': item.get('open_time', ''),
                'jump_url': item.get('jump_url', ''),
                'poster': item.get('poster', ''),
            })

        activity = None
        if self.activity_material_id:
            activity = await self.get_activity_link()

        return {
            'success': True,
            'city': city or self.default_city,
            'movies': movies,
            'total': resp.get('count') or len(movies),
            'activity_link': activity.get('rebate_url') if activity and activity.get('success') else '',
            'activity_tpwd': activity.get('tpwd') if activity and activity.get('success') else '',
        }
