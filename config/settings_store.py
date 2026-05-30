"""
运行时配置：唯一持久化来源为 SQLite app_config 表，启动与后台均直接读库。
"""

from __future__ import annotations

import copy
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

import config.config as cfg
from config.config import CONFIG_ATTRS, CONFIG_ATTRS_WITH_DB
from config.config_repository import count_config_rows, delete_config_key, load_all_config, save_config_key
from config.schema_builder import SECRET_KEY_PATTERN, build_settings_schema

logger = logging.getLogger(__name__)

SETTINGS_VERSION = 3
MASK_PLACEHOLDER = '__UNCHANGED__'
LEGACY_SETTINGS_PATH = os.path.join('data', 'app_settings.json')
REWARD_MAP_KEYS = frozenset({'continuous_rewards', 'total_rewards'})


class SettingsStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or cfg.DATABASE_CONFIG['db_path']
        self._data: dict[str, Any] = {}

    @property
    def storage_label(self) -> str:
        return f'SQLite 表 app_config（{self.db_path}）'

    def get_config_data(self) -> dict[str, Any]:
        if not self._data:
            self.reload_from_db()
        return copy.deepcopy(self._data)

    @staticmethod
    def _deep_merge(base: dict, patch: dict) -> dict:
        out = copy.deepcopy(base)
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = SettingsStore._deep_merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
        return out

    @staticmethod
    def _normalize_reward_map(raw: Any) -> dict[str, float]:
        if not isinstance(raw, dict):
            return {}
        out: dict[str, float] = {}
        for days, reward in raw.items():
            try:
                out[str(int(days))] = round(float(reward), 2)
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def _merge_section_values(cls, base: dict, patch: dict) -> dict:
        """合并配置分组：里程碑 JSON 整字段替换，避免与旧键 deep_merge 产生重复。"""
        out = copy.deepcopy(base)
        for key, value in patch.items():
            if key in REWARD_MAP_KEYS:
                out[key] = copy.deepcopy(value)
            elif isinstance(value, dict) and isinstance(out.get(key), dict):
                out[key] = cls._deep_merge(out[key], value)
            else:
                out[key] = copy.deepcopy(value)
        return out

    @staticmethod
    def _sync_dict(target: dict, merged: dict):
        target.clear()
        target.update(copy.deepcopy(merged))

    @staticmethod
    def _sync_list(target: list, merged: list):
        target.clear()
        target.extend(copy.deepcopy(merged))

    @staticmethod
    def _empty_for_attr(attr: str) -> Any:
        if attr == 'SENSITIVE_WORDS':
            return []
        return {}

    def _load_legacy_json_overrides(self) -> dict[str, Any]:
        if not os.path.isfile(LEGACY_SETTINGS_PATH):
            return {}
        try:
            with open(LEGACY_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            overrides = data.get('overrides', {}) if isinstance(data, dict) else {}
            return overrides if isinstance(overrides, dict) else {}
        except Exception as e:
            logger.warning('读取旧版 app_settings.json 失败: %s', e)
            return {}

    def _backup_legacy_json(self):
        if not os.path.isfile(LEGACY_SETTINGS_PATH):
            return
        backup = LEGACY_SETTINGS_PATH + '.migrated'
        try:
            os.replace(LEGACY_SETTINGS_PATH, backup)
            logger.info('已备份旧配置 %s -> %s', LEGACY_SETTINGS_PATH, backup)
        except OSError as e:
            logger.warning('备份旧配置文件失败: %s', e)

    def _migrate_legacy_json_into_db(self):
        legacy_overrides = self._load_legacy_json_overrides()
        if not legacy_overrides:
            return
        logger.info('检测到旧版 app_settings.json，正在合并进数据库…')
        for attr, patch in legacy_overrides.items():
            if patch is None:
                continue
            current = self._data.get(attr, self._empty_for_attr(attr))
            if attr == 'SENSITIVE_WORDS' and isinstance(patch, list):
                merged = copy.deepcopy(patch)
            elif isinstance(current, dict) and isinstance(patch, dict):
                merged = self._deep_merge(current, patch)
            else:
                merged = copy.deepcopy(patch)
            self._data[attr] = merged
            save_config_key(self.db_path, attr, merged)
        self._backup_legacy_json()

    def ensure_seeded(self):
        if count_config_rows(self.db_path) > 0:
            return
        legacy_overrides = self._load_legacy_json_overrides()
        if legacy_overrides:
            logger.info('app_config 为空，从 app_settings.json 迁移…')
            for attr, patch in legacy_overrides.items():
                if patch is not None:
                    save_config_key(self.db_path, attr, patch)
            self._backup_legacy_json()
            return
        logger.warning('app_config 为空且无旧配置文件，请先在管理后台填写配置')

    def reload_from_db(self):
        self.ensure_seeded()
        self._data = load_all_config(self.db_path)
        self._migrate_legacy_json_into_db()
        self._migrate_openclaw_config_key()
        self._migrate_haodanku_from_legacy_taobao()
        self._migrate_checkin_total_rewards()
        self._migrate_checkin_reward_maps()

    def _migrate_haodanku_from_legacy_taobao(self):
        """将旧版写在 REBATE_CONFIG.taobao 下的好单库密钥迁移到 haodanku 分组。"""
        rebate = self._data.get('REBATE_CONFIG')
        if not isinstance(rebate, dict):
            return
        legacy_tb = rebate.get('taobao') if isinstance(rebate.get('taobao'), dict) else {}
        hdk = rebate.get('haodanku') if isinstance(rebate.get('haodanku'), dict) else {}
        patch: dict[str, Any] = {}
        for key in ('app_id', 'app_secret'):
            if not str(hdk.get(key) or '').strip() and str(legacy_tb.get(key) or '').strip():
                patch[key] = legacy_tb[key]
        if not patch:
            return
        merged_hdk = copy.deepcopy(hdk)
        merged_hdk.update(patch)
        rebate['haodanku'] = merged_hdk
        self._data['REBATE_CONFIG'] = rebate
        save_config_key(self.db_path, 'REBATE_CONFIG', rebate)
        logger.info('已将好单库密钥从 taobao 迁移到 REBATE_CONFIG.haodanku')

    def _migrate_checkin_total_rewards(self):
        cfg = self._data.get('CHECKIN_CONFIG')
        if not isinstance(cfg, dict):
            return
        if cfg.get('total_rewards'):
            return
        merged = copy.deepcopy(cfg)
        merged['total_rewards'] = {'10': 1.0, '30': 3.0, '100': 10.0}
        self._data['CHECKIN_CONFIG'] = merged
        save_config_key(self.db_path, 'CHECKIN_CONFIG', merged)
        logger.info('已为 CHECKIN_CONFIG 写入默认累计签到里程碑 total_rewards')

    def _migrate_checkin_reward_maps(self):
        cfg = self._data.get('CHECKIN_CONFIG')
        if not isinstance(cfg, dict):
            return
        merged = copy.deepcopy(cfg)
        for key in REWARD_MAP_KEYS:
            if key not in merged:
                continue
            merged[key] = self._normalize_reward_map(merged.get(key))

        raw_text = self._read_config_json_text('CHECKIN_CONFIG')
        clean_text = json.dumps(merged, ensure_ascii=False, sort_keys=True)
        self._data['CHECKIN_CONFIG'] = merged
        if raw_text is not None and raw_text == clean_text:
            return
        save_config_key(self.db_path, 'CHECKIN_CONFIG', merged)
        logger.info('已规范化 CHECKIN_CONFIG 签到里程碑（去除重复键）')

    @staticmethod
    def _read_config_json_text(config_key: str, db_path: str | None = None) -> str | None:
        path = db_path or cfg.DATABASE_CONFIG['db_path']
        conn = sqlite3.connect(path)
        try:
            row = conn.execute(
                'SELECT value_json FROM app_config WHERE config_key = ?',
                (config_key,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def _migrate_openclaw_config_key(self):
        legacy = self._data.get('OPENCLAW_API_CONFIG')
        if not isinstance(legacy, dict):
            return
        if 'API_SERVER_CONFIG' not in self._data:
            self._data['API_SERVER_CONFIG'] = copy.deepcopy(legacy)
            save_config_key(self.db_path, 'API_SERVER_CONFIG', self._data['API_SERVER_CONFIG'])
            logger.info('已将 OPENCLAW_API_CONFIG 迁移为 API_SERVER_CONFIG')
        self._data.pop('OPENCLAW_API_CONFIG', None)
        delete_config_key(self.db_path, 'OPENCLAW_API_CONFIG')

    def apply_all(self):
        self.reload_from_db()
        for attr in CONFIG_ATTRS_WITH_DB:
            if attr not in self._data:
                continue
            value = copy.deepcopy(self._data[attr])
            if not hasattr(cfg, attr):
                setattr(cfg, attr, copy.deepcopy(value))
                continue
            target = getattr(cfg, attr)
            if isinstance(target, list):
                self._sync_list(target, value if isinstance(value, list) else [])
            elif isinstance(target, dict):
                self._sync_dict(target, value if isinstance(value, dict) else {})
            else:
                setattr(cfg, attr, value)
        logger.info('配置已从数据库加载（%d 项）', len(self._data))

    def _schema(self) -> list[dict]:
        return build_settings_schema(self._data)

    def _section_by_id(self, section_id: str) -> dict:
        for section in self._schema():
            if section['id'] == section_id:
                return section
        raise KeyError(f'unknown section: {section_id}')

    def _get_attr_data(self, attr: str) -> Any:
        if attr in self._data:
            return copy.deepcopy(self._data[attr])
        return self._empty_for_attr(attr)

    def _get_section_merged(self, section: dict) -> dict | list:
        attr = section['config_attr']
        nested = section.get('nested_key')
        data = self._get_attr_data(attr)

        if attr == 'SENSITIVE_WORDS':
            return {'words': data if isinstance(data, list) else []}

        if nested:
            if isinstance(data, dict):
                merged = copy.deepcopy(data.get(nested, {}))
            else:
                merged = {}
            if nested == 'haodanku' and isinstance(data, dict):
                legacy_tb = data.get('taobao') if isinstance(data.get('taobao'), dict) else {}
                for key in ('app_id', 'app_secret'):
                    if not str(merged.get(key) or '').strip() and legacy_tb.get(key):
                        merged[key] = legacy_tb[key]
            return merged
        return data if isinstance(data, dict) else {}

    def _save_attr(self, attr: str, value: Any):
        self._data[attr] = copy.deepcopy(value)
        save_config_key(self.db_path, attr, value)
        if not hasattr(cfg, attr):
            setattr(cfg, attr, copy.deepcopy(value))
            return
        target = getattr(cfg, attr)
        if isinstance(target, list):
            self._sync_list(target, value if isinstance(value, list) else [])
        elif isinstance(target, dict):
            self._sync_dict(target, value if isinstance(value, dict) else {})
        else:
            setattr(cfg, attr, copy.deepcopy(value))

    @staticmethod
    def _is_secret_field(field: dict) -> bool:
        if field.get('type') == 'secret':
            return True
        return bool(SECRET_KEY_PATTERN.search(field.get('key', '')))

    def _mask_value(self, field: dict, value: Any) -> Any:
        if not self._is_secret_field(field):
            if field.get('type') == 'string_list' and isinstance(value, list):
                return ', '.join(str(x) for x in value)
            if field.get('type') == 'json':
                return json.dumps(value, ensure_ascii=False) if value is not None else '{}'
            return value
        if value:
            return MASK_PLACEHOLDER
        return ''

    def get_section_values(self, section_id: str, *, reveal_secrets: bool = False) -> dict[str, Any]:
        section = self._section_by_id(section_id)
        merged = self._get_section_merged(section)
        out = {}
        for field in section['fields']:
            key = field['key']
            if not isinstance(merged, dict):
                out[key] = self._mask_value(field, None)
                continue
            raw = merged.get(key)
            if reveal_secrets and self._is_secret_field(field):
                out[key] = raw if raw is not None else ''
            else:
                out[key] = self._mask_value(field, raw)
        return out

    def get_all_values(self, *, reveal_secrets: bool = False) -> dict[str, dict[str, Any]]:
        return {
            s['id']: self.get_section_values(s['id'], reveal_secrets=reveal_secrets)
            for s in self._schema()
        }

    def get_meta(self) -> dict[str, Any]:
        return {
            'version': SETTINGS_VERSION,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'storage': self.storage_label,
            'section_count': len(self._schema()),
        }

    def _validate_field(self, field: dict, value: Any) -> Any:
        ftype = field.get('type')
        key = field['key']

        if ftype == 'bool':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('1', 'true', 'yes', 'on')
            return bool(value)

        if ftype == 'select':
            value_type = field.get('value_type')
            if value_type == 'int' or key == 'chain_type':
                v = int(value)
                if 'min' in field and v < field['min']:
                    raise ValueError(f'{key} 不能小于 {field["min"]}')
                if 'max' in field and v > field['max']:
                    raise ValueError(f'{key} 不能大于 {field["max"]}')
                return v
            text = str(value or '').strip()
            options = field.get('options') or []
            allowed = {str(o.get('value', '')) for o in options if isinstance(o, dict)}
            if allowed and text not in allowed:
                raise ValueError(f'{key} 取值无效，请从下拉列表选择')
            return text

        if ftype == 'int':
            v = int(value)
            if 'min' in field and v < field['min']:
                raise ValueError(f'{key} 不能小于 {field["min"]}')
            if 'max' in field and v > field['max']:
                raise ValueError(f'{key} 不能大于 {field["max"]}')
            return v

        if ftype == 'float':
            v = float(value)
            if 'min' in field and v < field['min']:
                raise ValueError(f'{key} 不能小于 {field["min"]}')
            if 'max' in field and v > field['max']:
                raise ValueError(f'{key} 不能大于 {field["max"]}')
            if key.endswith('_rate'):
                return round(v, 4)
            if key in ('min_withdraw', 'base_reward') or key.endswith('_reward'):
                return round(v, 2)
            return v

        if ftype == 'string_list':
            if isinstance(value, list):
                return [str(x).strip() for x in value if str(x).strip()]
            text = str(value or '').strip()
            if not text:
                return []
            return [x.strip() for x in text.split(',') if x.strip()]

        if ftype == 'json':
            if isinstance(value, (dict, list)):
                parsed = value
            else:
                text = str(value or '').strip() or ('[]' if key == 'words' else '{}')
                parsed = json.loads(text)
            if key in REWARD_MAP_KEYS and isinstance(parsed, dict):
                return self._normalize_reward_map(parsed)
            return parsed

        return str(value).strip() if value is not None else ''

    def update_section(self, section_id: str, raw_values: dict[str, Any]) -> dict[str, Any]:
        section = self._section_by_id(section_id)
        current = self._get_section_merged(section)
        validated: dict[str, Any] = {}

        for field in section['fields']:
            key = field['key']
            if key not in raw_values:
                continue
            incoming = raw_values[key]
            if self._is_secret_field(field):
                if incoming in (None, '', MASK_PLACEHOLDER):
                    continue
            validated[key] = self._validate_field(field, incoming)

        if not validated:
            return current if isinstance(current, dict) else {}

        attr = section['config_attr']
        nested = section.get('nested_key')

        if nested:
            full = self._get_attr_data(attr)
            if not isinstance(full, dict):
                full = {}
            nested_current = full.get(nested, {})
            if not isinstance(nested_current, dict):
                nested_current = {}
            merged_nested = self._merge_section_values(nested_current, validated)
            full[nested] = merged_nested
            self._save_attr(attr, full)
            return merged_nested

        full = self._get_attr_data(attr)
        if not isinstance(full, dict):
            full = {}
        merged = self._merge_section_values(full, validated)
        self._save_attr(attr, merged)
        return merged

    def update_admin_password(self, new_password: str):
        panel = self._get_attr_data('ADMIN_PANEL_CONFIG')
        if not isinstance(panel, dict):
            panel = {}
        panel['password'] = new_password
        self._save_attr('ADMIN_PANEL_CONFIG', panel)


_store: SettingsStore | None = None


def get_settings_store() -> SettingsStore:
    global _store
    if _store is None:
        _store = SettingsStore()
    return _store


def init_runtime_settings():
    get_settings_store().apply_all()
