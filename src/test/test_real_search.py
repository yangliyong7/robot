"""
测试真实搜索 API
验证淘宝、京东、拼多多的搜索功能是否正常
"""

import asyncio
import sys
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.modules.price_comparison import PriceComparisonService


async def test_search():
    """测试三个平台的搜索功能"""
    
    print("=" * 80)
    print("测试真实搜索 API")
    print("=" * 80)
    print()
    
    service = PriceComparisonService()
    
    # 测试关键词
    keyword = "iPhone 15"
    print(f"📦 搜索关键词: {keyword}")
    print()
    
    # 测试 1：淘宝搜索
    print("【1】测试淘宝搜索（好单库）...")
    try:
        result = await service._search_taobao(keyword)
        if result:
            print(f"✅ 搜索成功")
            print(f"   - 商品: {result['title'][:50]}...")
            print(f"   - 原价: ¥{result['original_price']:.2f}")
            print(f"   - 到手价: ¥{result['final_price']:.2f}")
            print(f"   - 优惠券: ¥{result['coupon_amount']:.2f}")
            print(f"   - 佣金: ¥{result['commission']:.2f}")
            print(f"   - 返利: ¥{result['user_rebate']:.2f}")
        else:
            print("❌ 搜索失败或无结果")
    except Exception as e:
        print(f"❌ 搜索异常: {e}")
    print()
    
    # 测试 2：京东搜索
    print("【2】测试京东搜索（京东联盟）...")
    try:
        result = await service._search_jd(keyword)
        if result:
            print(f"✅ 搜索成功")
            print(f"   - 商品: {result['title'][:50]}...")
            print(f"   - 原价: ¥{result['original_price']:.2f}")
            print(f"   - 佣金: ¥{result['commission']:.2f}")
            print(f"   - 返利: ¥{result['user_rebate']:.2f}")
        else:
            print("❌ 搜索失败或无结果")
    except Exception as e:
        print(f"❌ 搜索异常: {e}")
    print()
    
    # 测试 3：拼多多搜索
    print("【3】测试拼多多搜索（多多进宝）...")
    try:
        result = await service._search_pdd(keyword)
        if result:
            print(f"✅ 搜索成功")
            print(f"   - 商品: {result['title'][:50]}...")
            print(f"   - 原价: ¥{result['original_price']:.2f}")
            print(f"   - 到手价: ¥{result['final_price']:.2f}")
            print(f"   - 优惠券: ¥{result['coupon_amount']:.2f}")
            print(f"   - 佣金: ¥{result['commission']:.2f}")
            print(f"   - 返利: ¥{result['user_rebate']:.2f}")
        else:
            print("❌ 搜索失败或无结果")
    except Exception as e:
        print(f"❌ 搜索异常: {e}")
    print()
    
    # 测试 4：完整比价流程
    print("【4】测试完整比价流程...")
    try:
        result = await service.compare_price(
            keyword=keyword,
            exclude_platform=None,
            wxid='test_user'
        )
        
        if result.get('success'):
            print(f"✅ 比价成功")
            print(f"   - 找到 {result['total_results']} 个平台")
            print(f"   - 最低价: ¥{result['best_price']['final_price']:.2f}")
            print(f"   - 平台: {result['best_price']['platform']}")
            print()
            print("📊 比价结果:")
            msg = service.format_comparison_message(result)
            print(msg)
        else:
            print(f"❌ 比价失败: {result.get('message')}")
    except Exception as e:
        print(f"❌ 比价异常: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(test_search())
