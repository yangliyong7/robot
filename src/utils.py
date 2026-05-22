"""
辅助功能模块
包含日志配置、敏感词过滤、工具函数等
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from config.config import LOG_CONFIG, SENSITIVE_WORDS


def setup_logger(name='RebateBot'):
    """
    配置日志系统
    :param name: 日志器名称
    :return: logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_CONFIG.get('level', 'INFO')))

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 日志格式
    formatter = logging.Formatter(
        LOG_CONFIG.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（带轮转）
    log_file = LOG_CONFIG.get('file', 'logs/bot.log')
    
    # 确保日志路径是相对于项目根目录的
    # 假设 utils.py 在 src/ 下，那么项目根目录是上一层
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isabs(log_file):
        log_file = os.path.join(project_root, log_file)
        
    log_dir = os.path.dirname(log_file)

    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_CONFIG.get('max_bytes', 10 * 1024 * 1024),
        backupCount=LOG_CONFIG.get('backup_count', 5),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


class SensitiveWordFilter:
    """敏感词过滤器"""

    def __init__(self, sensitive_words=None):
        """
        初始化敏感词过滤器
        :param sensitive_words: 敏感词列表，默认使用配置文件中的
        """
        self.sensitive_words = sensitive_words or SENSITIVE_WORDS
        # 构建敏感词模式（用于快速匹配）
        self._build_pattern()

    def _build_pattern(self):
        """构建敏感词正则表达式模式"""
        if self.sensitive_words:
            # 转义特殊字符并构建模式
            escaped_words = [re.escape(word) for word in self.sensitive_words]
            self.pattern = re.compile('|'.join(escaped_words), re.IGNORECASE)
        else:
            self.pattern = None

    def contains_sensitive_word(self, text):
        """
        检查文本是否包含敏感词
        :param text: 待检查文本
        :return: True表示包含敏感词
        """
        if not self.pattern:
            return False

        return bool(self.pattern.search(text))

    def filter_text(self, text, replace_char='*'):
        """
        过滤文本中的敏感词
        :param text: 原始文本
        :param replace_char: 替换字符
        :return: 过滤后的文本
        """
        if not self.pattern:
            return text

        def replace_match(match):
            word = match.group(0)
            return replace_char * len(word)

        return self.pattern.sub(replace_match, text)

    def add_sensitive_word(self, word):
        """添加敏感词"""
        if word not in self.sensitive_words:
            self.sensitive_words.append(word)
            self._build_pattern()

    def remove_sensitive_word(self, word):
        """移除敏感词"""
        if word in self.sensitive_words:
            self.sensitive_words.remove(word)
            self._build_pattern()


class TextUtils:
    """文本处理工具类"""

    @staticmethod
    def is_valid_url(url):
        """
        验证是否为有效的URL
        :param url: URL字符串
        :return: True/False
        """
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:[\w-]+\.)+[\w-]+'  # domain
            r'(?:\:[0-9]+)?'  # optional port
            r'(?:/[^\s]*)?$',  # path
            re.IGNORECASE
        )
        return bool(url_pattern.match(url))

    @staticmethod
    def truncate_text(text, max_length=100, suffix='...'):
        """
        截断文本到指定长度
        :param text: 原始文本
        :param max_length: 最大长度
        :param suffix: 截断后缀
        :return: 截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix

    @staticmethod
    def format_money(amount):
        """
        格式化金额显示
        :param amount: 金额
        :return: 格式化后的字符串
        """
        return f"¥{amount:.2f}"

    @staticmethod
    def mask_phone(phone):
        """
        手机号脱敏
        :param phone: 手机号
        :return: 脱敏后的手机号
        """
        if len(phone) == 11:
            return phone[:3] + '****' + phone[7:]
        return phone

    @staticmethod
    def mask_wechat_id(wechat_id):
        """
        微信号脱敏
        :param wechat_id: 微信号
        :return: 脱敏后的微信号
        """
        if len(wechat_id) > 4:
            return wechat_id[:2] + '***' + wechat_id[-2:]
        return '***'


class CommandParser:
    """指令解析器"""

    def __init__(self, commands_config):
        """
        初始化指令解析器
        :param commands_config: 指令配置字典
        """
        self.commands = commands_config
        # 构建反向映射：关键词 -> 指令类型
        self.keyword_to_command = {}
        for cmd_type, keywords in commands_config.items():
            for keyword in keywords:
                self.keyword_to_command[keyword.lower()] = cmd_type

    def parse_command(self, text):
        """
        解析用户输入的指令
        :param text: 用户输入文本
        :return: 指令类型，如果不是指令返回None
        """
        text_lower = text.strip().lower()

        # 精确匹配
        if text_lower in self.keyword_to_command:
            return self.keyword_to_command[text_lower]

        # 模糊匹配（包含关键词）
        for keyword, cmd_type in self.keyword_to_command.items():
            if keyword in text_lower:
                return cmd_type

        return None

    def is_command(self, text):
        """
        判断是否为已知指令
        :param text: 用户输入
        :return: True/False
        """
        return self.parse_command(text) is not None


# 创建全局实例
logger = setup_logger()
sensitive_filter = SensitiveWordFilter()
