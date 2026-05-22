"""
DeepSeek AI 客户端封装
支持异步调用、流式输出及多种场景配置
"""

import logging
import asyncio
from openai import AsyncOpenAI
from config.config import DEEPSEEK_CONFIG

logger = logging.getLogger(__name__)


class DeepSeekClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=DEEPSEEK_CONFIG['api_key'],
            base_url=DEEPSEEK_CONFIG['base_url']
        )
        self.model = DEEPSEEK_CONFIG['model']

    async def chat_completion(self, messages, temperature=0.7, max_tokens=1000, stream=False):
        """
        通用聊天补全接口
        :param messages: 消息列表 [{"role": "user", "content": "..."}]
        :param temperature: 温度参数 (0-1)
        :param max_tokens: 最大 token 数
        :param stream: 是否流式输出
        :return: 回复内容字符串
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                # 流式处理逻辑（后续优化体验时使用）
                full_content = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content
                return full_content
            else:
                return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"DeepSeek API 调用失败: {e}")
            return "抱歉，AI 服务暂时繁忙，请稍后再试。"

    async def intent_recognize(self, user_input):
        """
        专用：意图识别
        :param user_input: 用户原始输入
        :return: JSON 格式的意图字典
        """
        from src.ai.prompts import INTENT_RECOGNITION_PROMPT
        
        messages = [
            {"role": "system", "content": INTENT_RECOGNITION_PROMPT},
            {"role": "user", "content": user_input}
        ]
        
        # 意图识别需要低温度以保证稳定性，并要求返回 JSON
        result = await self.chat_completion(messages, temperature=0.1, max_tokens=200)
        return result

    async def generate_advice(self, context, product_info=None):
        """
        专用：生成购物建议或推荐理由
        :param context: 对话上下文
        :param product_info: 商品详细信息字典
        :return: 建议文本
        """
        from src.ai.prompts import SHOPPING_ADVICE_PROMPT
        
        content = f"上下文：{context}\n商品信息：{product_info}"
        messages = [
            {"role": "system", "content": SHOPPING_ADVICE_PROMPT},
            {"role": "user", "content": content}
        ]
        
        return await self.chat_completion(messages, temperature=0.8, max_tokens=500)
