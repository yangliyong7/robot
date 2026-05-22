"""
拼多多转链测试脚本
用于测试多多进宝 API 是否正常工作
"""

import asyncio
import sys
import os
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.platforms.pdd import PDDClient
from src.rebate_api import extract_url_from_text


async def test_pdd_convert():
    """测试拼多多转链功能"""
    
    # 测试链接
    test_url = "https://mobile.yangkeduo.com/goods.html?refer_share_id=Lt4vfykygpSHr8AeVyhU9O370lpNDwQR&refer_share_channel=message&pxq_secret_key=PCXC6QSRGAJTCQLPQSCADSB5HKSVK7ZAITVW5TFAR755P5K2GM4A&_x_ddjb_act=%7B%22st%22%3A%221%22%7D&_oak_share_time=1779417510&_x_ddjb_id=1636940_247148443%7CCC_260522_1636940_247148443_86abea3683d7d66faa51c963218a4b23&share_oak_rcto=YWKNxPksjdgnSPgtpxlvI-B6qoQnqK-r60XqeC76W1VKDMWreF5Z2Vfnbn772K8kiuYA27ZDMk82Hg&share_uin=V7MGODRS3KCWAHFTARMKZHQADM_GEXDA&page_from=29&_x_hungary_clipboard_biz=jinbao&_x_ddjb_gs=%7B%22gs_src%22%3A%2213%22%2C%22gs_scn%22%3A%2221%22%7D&refer_share_uin=V7MGODRS3KCWAHFTARMKZHQADM_GEXDA&goods_id=942714949152&_x_hungary_module_id=ddjb_clipboard_wd&_oak_share_snapshot_num=5850&_oak_share_ticket=01-0000000029-99520bdb56d61527c02eaa6c1d4b414be0c72c6ac29cc9d0c2596c30440142f2-1780713542#pushState"
    
    print("=" * 80)
    print("拼多多转链测试")
    print("=" * 80)
    print()
    
    # 1. 提取链接
    print("【步骤 1】提取链接...")
    urls = extract_url_from_text(test_url)
    if not urls:
        print("❌ 无法从文本中提取链接")
        return
    
    clean_url = urls[0]
    print(f"✅ 提取成功: {clean_url[:80]}...")
    print()
    
    # 2. 初始化 PDD 客户端
    print("【步骤 2】初始化多多进宝客户端...")
    try:
        client = PDDClient()
        print(f"✅ 客户端初始化成功")
        print(f"   - client_id: {client.client_id[:10]}***")
        print(f"   - pid: {client.pid}")
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        return
    print()
    
    # 3. 调用转链 API
    print("【步骤 3】调用转链 API...")
    print("   正在请求多多进宝 API，请稍候...")
    print()
    
    try:
        result = await client.convert(clean_url, wxid="test_user_001")
        
        print("【步骤 4】API 响应结果:")
        print("-" * 80)
        
        if result.get('success'):
            print("✅ 转链成功！")
            print()
            print(f"📦 商品名称: {result.get('title', '未知')}")
            print(f"💰 商品价格: ¥{result.get('original_price', 0):.2f}")
            print(f"🎁 佣金比例: {result.get('commission', 0):.2f}%")
            print(f"💵 预估佣金: ¥{result.get('user_rebate', 0):.2f}")
            print()
            print(f"🔗 原始链接:")
            print(f"   {result.get('original_url', '')[:100]}...")
            print()
            print(f"🔗 推广链接:")
            print(f"   {result.get('rebate_url', '')}")
            print()
            
            # 打印原始响应调试信息
            if result.get('raw'):
                print("📄 原始 API 响应（调试）:")
                import json
                raw_resp = result['raw']
                resp_data = raw_resp.get('goods_zs_unit_generate_response', {})
                print(f"   返回字段: {list(resp_data.keys())}")
                print(f"   goods_name: {resp_data.get('goods_name', '无')}")
                print(f"   goods_price: {resp_data.get('goods_price', '无')}")
                print(f"   promotion_rate: {resp_data.get('promotion_rate', '无')}")
            
            if result.get('need_filing'):
                print("⚠️  需要备案提示:")
                print(f"   {result.get('message', '')}")
                print()
                print(f"📋 请先访问以下链接完成授权备案:")
                print(f"   {result.get('auth_url', '')}")
        else:
            print("❌ 转链失败")
            print()
            print(f"错误信息: {result.get('message', '未知错误')}")
            print()
            
            if result.get('need_filing'):
                print("⚠️  需要备案:")
                print(f"   {result.get('message', '')}")
                print()
                print(f"📋 请访问以下链接完成授权备案:")
                print(f"   {result.get('auth_url', '')}")
            
            # 打印原始响应（调试用）
            if result.get('raw'):
                print()
                print("📄 原始 API 响应:")
                import json
                print(json.dumps(result['raw'], ensure_ascii=False, indent=2))
                
                # 检查具体错误码
                raw = result['raw']
                err = raw.get('error_response', {})
                if err:
                    print()
                    print("🔍 错误详情:")
                    print(f"   错误码: {err.get('error_code', '未知')}")
                    print(f"   错误消息: {err.get('error_msg', '未知')}")
                    print(f"   子错误码: {err.get('sub_code', '未知')}")
                    print(f"   子错误消息: {err.get('sub_msg', '未知')}")
        
        print("-" * 80)
        
    except Exception as e:
        print(f"❌ 转链过程发生异常: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(test_pdd_convert())
