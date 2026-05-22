"""美团联盟 CPS Open API 签名（media.meituan.com/cps_open）"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from src.platforms.base import http_request, parse_json_response

CPS_BASE = 'https://media.meituan.com/cps_open/common/api/v1'


def _content_md5(body: bytes) -> str:
    return base64.b64encode(hashlib.md5(body).digest()).decode('utf-8')


def build_cps_headers(
    method: str,
    url: str,
    body: str,
    app_key: str,
    app_secret: str,
    timestamp_ms: Optional[str] = None,
) -> Dict[str, str]:
    """阿里云 API 网关风格签名（S-Ca-*）"""
    ts = timestamp_ms or str(int(time.time() * 1000))
    body_bytes = (body or '').encode('utf-8')
    content_md5 = _content_md5(body_bytes)
    accept = 'application/json'
    content_type = 'application/json; charset=UTF-8'

    sign_headers = {'S-Ca-App': app_key, 'S-Ca-Timestamp': ts}
    headers_part = ''.join(f'{k}:{sign_headers[k]}\n' for k in sorted(sign_headers))

    path = urlparse(url).path or '/'
    string_to_sign = (
        f'{method.upper()}\n{accept}\n{content_md5}\n{content_type}\n\n'
        f'{headers_part}{path}'
    )
    signature = base64.b64encode(
        hmac.new(app_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode('utf-8')

    return {
        'Accept': accept,
        'Content-Type': content_type,
        'Content-MD5': content_md5,
        'S-Ca-App': app_key,
        'S-Ca-Timestamp': ts,
        'S-Ca-Signature': signature,
        'S-Ca-Signature-Headers': 'S-Ca-Timestamp,S-Ca-App',
    }


async def cps_post(path: str, payload: dict, app_key: str, app_secret: str) -> dict:
    url = f'{CPS_BASE}/{path.lstrip("/")}'
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    headers = build_cps_headers('POST', url, body, app_key, app_secret)
    resp = await http_request('POST', url, data=body.encode('utf-8'), headers=headers)
    return parse_json_response(resp)
