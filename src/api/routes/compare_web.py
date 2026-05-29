"""全网比价页：链接仅含令牌，商品参数经 POST 在服务端查询。"""

from __future__ import annotations

import html
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.compare_tokens import resolve_compare_token
from src.modules.price_comparison import PriceComparisonService

router = APIRouter(tags=['compare'])


class CompareRunRequest(BaseModel):
    token: str = Field(..., min_length=8, max_length=128)


class CompareRunResponse(BaseModel):
    success: bool
    message: str = ''


def _compare_base_html(title: str, body_html: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, "Segoe UI", sans-serif; margin: 16px; line-height: 1.5; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 15px; }}
    .err {{ color: #b91c1c; }}
  </style>
</head>
<body>
{body_html}
</body>
</html>'''


@router.get('/compare/{token}', response_class=HTMLResponse)
async def compare_page_shell(token: str):
    """打开比价页：页面内 POST 提交令牌，URL 中不出现商品名。"""
    token_json = json.dumps(token)
    body = f'''
  <p id="status">正在查询全网比价…</p>
  <pre id="result" style="display:none;"></pre>
  <script>
    (async function () {{
      const status = document.getElementById('status');
      const result = document.getElementById('result');
      try {{
        const res = await fetch('/compare/run', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ token: {token_json} }}),
        }});
        const data = await res.json();
        status.style.display = 'none';
        result.style.display = 'block';
        if (!res.ok) {{
          const err = data.detail || data.message || '查询失败';
          result.innerHTML = '<span class="err">' + err + '</span>';
          return;
        }}
        if (data.success) {{
          result.textContent = data.message || '暂无结果';
        }} else {{
          result.innerHTML = '<span class="err">' + (data.message || '查询失败') + '</span>';
        }}
      }} catch (e) {{
        status.innerHTML = '<span class="err">网络错误，请稍后重试</span>';
      }}
    }})();
  </script>'''
    return HTMLResponse(_compare_base_html('全网比价', body))


@router.post('/compare/run', response_model=CompareRunResponse)
async def compare_run(body: CompareRunRequest):
    """POST 提交令牌，服务端解析商品并比价（仅无推广签发的令牌有效）。"""
    data = resolve_compare_token(body.token)
    if not data:
        raise HTTPException(
            status_code=404,
            detail='链接已失效或无效，请回到微信重新发送商品链接后再打开比价',
        )

    svc = PriceComparisonService()
    result = await svc.compare_price(
        keyword=data['keyword'],
        exclude_platform=data.get('platform'),
        wxid=data.get('wxid') or None,
    )
    message = svc.format_comparison_message(result)
    return CompareRunResponse(success=bool(result.get('success')), message=message)
