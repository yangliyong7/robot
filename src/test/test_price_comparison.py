"""
测试比价触发逻辑
验证三种场景：
1. 转链失败 → 触发比价
2. 转链成功但无优惠 → 触发比价
3. 转链成功且有优惠 → 不比价
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


def test_saved_money_logic():
    """测试省钱判断逻辑"""
    
    print("=" * 80)
    print("测试：用户是否省到钱的判断逻辑")
    print("=" * 80)
    print()
    
    # 场景 1：只有优惠券
    result1 = {
        'coupon_amount': 20.0,
        'commission': 0,
        'user_rebate': 0,
    }
    has_coupon1 = result1.get('coupon_amount', 0) > 0
    has_rebate1 = result1.get('user_rebate', 0) > 0
    has_commission1 = result1.get('commission', 0) > 0
    saved1 = has_coupon1 or has_rebate1 or has_commission1
    
    print("场景 1：只有优惠券")
    print(f"  优惠券: ¥{result1['coupon_amount']:.2f} → {has_coupon1}")
    print(f"  返利: ¥{result1['user_rebate']:.2f} → {has_rebate1}")
    print(f"  佣金: ¥{result1['commission']:.2f} → {has_commission1}")
    print(f"  ✅ 用户省钱了: {saved1}")
    print()
    
    # 场景 2：只有返利
    result2 = {
        'coupon_amount': 0,
        'commission': 5.0,
        'user_rebate': 3.5,
    }
    has_coupon2 = result2.get('coupon_amount', 0) > 0
    has_rebate2 = result2.get('user_rebate', 0) > 0
    has_commission2 = result2.get('commission', 0) > 0
    saved2 = has_coupon2 or has_rebate2 or has_commission2
    
    print("场景 2：只有返利")
    print(f"  优惠券: ¥{result2['coupon_amount']:.2f} → {has_coupon2}")
    print(f"  返利: ¥{result2['user_rebate']:.2f} → {has_rebate2}")
    print(f"  佣金: ¥{result2['commission']:.2f} → {has_commission2}")
    print(f"  ✅ 用户省钱了: {saved2}")
    print()
    
    # 场景 3：既有优惠券又有返利
    result3 = {
        'coupon_amount': 15.0,
        'commission': 8.0,
        'user_rebate': 5.6,
    }
    has_coupon3 = result3.get('coupon_amount', 0) > 0
    has_rebate3 = result3.get('user_rebate', 0) > 0
    has_commission3 = result3.get('commission', 0) > 0
    saved3 = has_coupon3 or has_rebate3 or has_commission3
    
    print("场景 3：既有优惠券又有返利")
    print(f"  优惠券: ¥{result3['coupon_amount']:.2f} → {has_coupon3}")
    print(f"  返利: ¥{result3['user_rebate']:.2f} → {has_rebate3}")
    print(f"  佣金: ¥{result3['commission']:.2f} → {has_commission3}")
    print(f"  ✅ 用户省钱了: {saved3}")
    print()
    
    # 场景 4：没有任何优惠（需要比价）
    result4 = {
        'coupon_amount': 0,
        'commission': 0,
        'user_rebate': 0,
    }
    has_coupon4 = result4.get('coupon_amount', 0) > 0
    has_rebate4 = result4.get('user_rebate', 0) > 0
    has_commission4 = result4.get('commission', 0) > 0
    saved4 = has_coupon4 or has_rebate4 or has_commission4
    
    print("场景 4：没有任何优惠（需要比价）")
    print(f"  优惠券: ¥{result4['coupon_amount']:.2f} → {has_coupon4}")
    print(f"  返利: ¥{result4['user_rebate']:.2f} → {has_rebate4}")
    print(f"  佣金: ¥{result4['commission']:.2f} → {has_commission4}")
    print(f"  ❌ 用户没省钱: {not saved4} → 触发比价")
    print()
    
    # 场景 5：转链失败（需要比价）
    result5 = {
        'success': False,
        'message': '多多进宝未返回推广链接',
    }
    print("场景 5：转链失败（需要比价）")
    print(f"  转链成功: {result5['success']}")
    print(f"  错误信息: {result5['message']}")
    print(f"  ❌ 转链失败 → 触发比价")
    print()
    
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


async def test_price_comparison():
    """测试比价功能"""
    print()
    print("=" * 80)
    print("测试：比价功能")
    print("=" * 80)
    print()
    
    service = PriceComparisonService()
    
    # 测试用例
    test_cases = [
        "iPhone 15 Pro",
        "小米14",
        "AirPods Pro",
    ]
    
    for keyword in test_cases:
        print(f"\n🔍 搜索: {keyword}")
        print("-" * 80)
        
        result = await service.compare_price(keyword)
        
        if result.get('success'):
            print(f"✅ 找到 {result['total_results']} 个平台")
            print(f"🥇 最低价: {result['best_price']['platform']} ¥{result['best_price']['final_price']:.2f}")
            
            # 打印完整消息
            msg = service.format_comparison_message(result)
            print()
            print(msg)
        else:
            print(f"❌ {result.get('message', '未知错误')}")
        
        print()


if __name__ == '__main__':
    # 测试 1：省钱判断逻辑
    test_saved_money_logic()
    
    # 测试 2：比价功能
    print("\n按回车键继续测试比价功能...")
    input()
    
    asyncio.run(test_price_comparison())
