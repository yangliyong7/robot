"""
微信侧业务服务层。

- 电商转链：ecommerce（经 rebate_api → platforms）
- 本地/出行/票务等：见各 *Service 模块
- 联盟 HTTP 客户端在 src.platforms，勿在本包重复封装 *_api
"""

from src.modules.ecommerce import EcommerceService
from src.modules.local_life import LocalLifeService
from src.modules.travel import TravelService

__all__ = [
    'EcommerceService',
    'LocalLifeService',
    'TravelService',
]
