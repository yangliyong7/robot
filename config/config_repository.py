"""SQLite app_config 表读写（避免与 DatabaseManager 循环依赖）。"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def ensure_config_table(db_path: str) -> None:
    folder = os.path.dirname(db_path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS app_config (
                config_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        conn.commit()
    finally:
        conn.close()


def count_config_rows(db_path: str) -> int:
    ensure_config_table(db_path)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute('SELECT COUNT(*) FROM app_config').fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def load_all_config(db_path: str) -> dict[str, Any]:
    ensure_config_table(db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute('SELECT config_key, value_json FROM app_config').fetchall()
        out: dict[str, Any] = {}
        for key, raw in rows:
            try:
                out[key] = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.error('app_config 解析失败 %s: %s', key, e)
        return out
    finally:
        conn.close()


def save_config_key(db_path: str, config_key: str, value: Any) -> None:
    ensure_config_table(db_path)
    payload = json.dumps(value, ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            '''
            INSERT INTO app_config (config_key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            ''',
            (config_key, payload, now),
        )
        conn.commit()
    finally:
        conn.close()


def save_all_config(db_path: str, data: dict[str, Any]) -> None:
    for key, value in data.items():
        save_config_key(db_path, key, value)
