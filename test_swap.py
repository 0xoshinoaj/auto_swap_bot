#!/usr/bin/env python3
"""
Swap 測試腳本 - 使用 SwapExecutor 模組
用於調試和驗證 swap 的各個步驟

使用方式：
  python3 test_swap.py          # 只獲取報價，不執行交換
  python3 test_swap.py --execute  # 獲取報價並執行交換
"""

import asyncio
import logging
import sys
import os
from web3 import Web3
from dotenv import load_dotenv
from swap_executor import SwapExecutor

# ==================== 測試代幣配置 ====================
# 在這裡設置要測試的代幣
TEST_TOKEN_ADDRESS = "0x1111111111166b7FE7bd91427724B487980aFc69"  # 1inch Token on Base
TEST_WETH_ADDRESS = "0x4200000000000000000000000000000000000006"   # WETH on Base (Gas Token)
TEST_AMOUNT = 1  # 要交換的代幣數量 (單位)

# ==================== 日誌配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

async def main():
    """主測試流程"""
    try:
        # 初始化執行器
        executor = SwapExecutor(chain_id=8453)
        
        logger.info("\n" + "="*60)
        logger.info("🧪 開始 Swap 測試")
        logger.info("="*60)
        
        # 轉換金額為 wei
        amount_wei = int(TEST_AMOUNT * 10 ** 18)
        
        logger.info(f"\n📋 測試配置:")
        logger.info(f"   代幣: {TEST_TOKEN_ADDRESS}")
        logger.info(f"   目標: {TEST_WETH_ADDRESS}")
        logger.info(f"   金額: {TEST_AMOUNT} 個代幣 ({amount_wei} wei)")
        
        # 只獲取報價模式
        if len(sys.argv) <= 1 or sys.argv[1] != '--execute':
            logger.info("\n📊 模式：只獲取報價")
            
            # 獲取報價
            quote = await executor.get_0x_quote(TEST_TOKEN_ADDRESS, TEST_WETH_ADDRESS, amount_wei)
            if quote:
                logger.info(f"\n✅ 報價成功！")
                logger.info(f"   買入金額: {quote.get('buyAmount')} wei")
                logger.info(f"   最小買入: {quote.get('minBuyAmount')} wei")
                logger.info(f"   流動性: {quote.get('liquidityAvailable')}")
            else:
                logger.error(f"\n❌ 報價失敗")
            
            logger.info(f"\n💡 提示: 加上 --execute 標誌來真正執行交換")
            logger.info(f"   python3 test_swap.py --execute")
        
        # 執行交換模式
        else:
            logger.info("\n🚀 模式：獲取報價 + 執行交換")
            
            # 執行完整交換
            tx_hash = await executor.execute_swap(TEST_TOKEN_ADDRESS, TEST_WETH_ADDRESS, amount_wei)
            
            if tx_hash:
                logger.info(f"\n✅ 交換成功！")
                logger.info(f"   交易哈希: {tx_hash}")
            else:
                logger.error(f"\n❌ 交換失敗")
        
        logger.info("\n" + "="*60)
        logger.info("✅ 測試完成")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ 測試失敗: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
