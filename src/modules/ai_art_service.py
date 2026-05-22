"""
AI 艺术创作模块
支持文生图、头像生成等付费服务
"""

import logging
from src.ai.deepseek_client import DeepSeekClient # 复用已有的客户端或新建一个

logger = logging.getLogger(__name__)


class AiArtService:
    def __init__(self):
        # 这里可以使用 DeepSeek 的 Key，或者单独配置通义万相的 Key
        self.client = DeepSeekClient() 
        self.price_per_image = 2.0  # 每张图收费 2 元

    async def generate_image(self, prompt: str) -> dict:
        """
        根据提示词生成图片
        :param prompt: 用户的描述
        :return: 包含图片链接和扣费信息的字典
        """
        logger.info(f"正在为用户生成 AI 图片: {prompt}")

        # 1. 优化提示词（利用 AI 把用户简单的话变成专业的绘图指令）
        optimized_prompt = await self._optimize_prompt(prompt)

        # 2. 调用绘图 API (此处以模拟为例，实际需接入 DashScope SDK)
        # from dashscope import ImageSynthesis
        # rsp = ImageSynthesis.call(model="wanx-v1", prompt=optimized_prompt, n=1)
        
        # 模拟返回结果
        image_url = "https://mock-ai-art-image.com/sample.jpg"
        
        return {
            'success': True,
            'image_url': image_url,
            'cost': self.price_per_image,
            'prompt_used': optimized_prompt
        }

    async def _optimize_prompt(self, user_input: str) -> str:
        """利用 LLM 优化绘图提示词"""
        system_prompt = "你是一个专业的 AI 绘画提示词工程师。请将用户的输入转化为适合 Midjourney 或 Stable Diffusion 的高质量英文提示词，包含光影、风格、细节描述。"
        # 调用 DeepSeek 进行转换
        return f"(High quality, 8k, masterpiece), {user_input}"

    async def get_service_menu(self) -> str:
        """获取 AI 绘画服务菜单"""
        return (
            f"🎨 **AI 艺术工作室**\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✨ 服务项目：\n"
            f"1. 专属头像定制 (¥{self.price_per_image}/张)\n"
            f"2. 小红书配图生成 (¥{self.price_per_image}/张)\n"
            f"3. 创意壁纸制作 (¥{self.price_per_image}/张)\n\n"
            f"💬 请直接发送你的需求，例如：\n"
            f"“帮我画一只在太空弹吉他的猫，赛博朋克风格”"
        )
