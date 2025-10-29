#!/usr/bin/env python3
"""
Swap 執行器 - 可以被其他模組調用
提供一個簡單的 API 來執行代幣交換
"""

import asyncio
import logging
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv
import os
import aiohttp
from typing import Optional, Dict, Any
import config

logger = logging.getLogger(__name__)

# ==================== 日誌輔助函數 ====================
def log_debug(msg: str):
    """僅在 DEBUG 模式下輸出"""
    if getattr(config, 'LOG_DEBUG', False):
        logger.info(msg)
    else:
        logger.debug(msg)

load_dotenv()

class SwapExecutor:
    """使用 0x Protocol 執行 Swap"""
    
    def __init__(self, chain_id: int = 8453, slippage_percentage: float = None, log_level: str = "INFO"):
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('RPC_URL')
        self.chain_id = chain_id
        self.zx_api_key = os.getenv('ZX_API_KEY')
        self.slippage_percentage = slippage_percentage or config.SWAP_SLIPPAGE
        
        if not self.private_key or not self.rpc_url:
            raise ValueError("❌ 缺少 PRIVATE_KEY 或 RPC_URL")
        
        if not self.zx_api_key:
            raise ValueError("❌ 缺少 ZX_API_KEY (0x API Key)")
        
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        self.account = self.w3.eth.account.from_key(self.private_key)
        self.address = self.account.address
        
        # 設置日誌
        logging.basicConfig(level=getattr(logging, log_level))
        
        logger.info(f"✅ SwapExecutor 初始化")
        logger.info(f"   錢包: {self.address}")
        logger.info(f"   鏈 ID: {self.chain_id}")
    
    async def get_0x_quote(self, token_in: str, token_out: str, amount: int) -> Optional[Dict]:
        """獲取 0x 報價"""
        logger.info(f"🔍 獲取 0x 報價...")
        
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = "https://api.0x.org/swap/allowance-holder/quote"
            params = {
                'chainId': self.chain_id,
                'sellToken': token_in,
                'buyToken': token_out,
                'sellAmount': str(amount),
                'taker': Web3.to_checksum_address(self.address),
                'slippagePercentage': str(self.slippage_percentage),
            }
            
            headers = {
                '0x-api-key': self.zx_api_key,
                '0x-version': 'v2',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"   ✅ 報價成功: {data.get('buyAmount')} 買入金額")
                        return data
                    else:
                        logger.error(f"   ❌ 報價失敗: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"   ❌ 報價錯誤: {str(e)}")
            return None
    
    async def get_0x_swap_tx(self, token_in: str, token_out: str, amount: int) -> Optional[Dict]:
        """獲取 0x 交換交易數據"""
        logger.info(f"🔍 獲取 0x 交換交易數據...")
        
        try:
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = "https://api.0x.org/swap/allowance-holder/quote"
            params = {
                'chainId': self.chain_id,
                'sellToken': token_in,
                'buyToken': token_out,
                'sellAmount': str(amount),
                'taker': Web3.to_checksum_address(self.address),
                'slippagePercentage': str(self.slippage_percentage),
            }
            
            headers = {
                '0x-api-key': self.zx_api_key,
                '0x-version': 'v2',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"   ✅ 交換數據獲取成功")
                        return data
                    else:
                        logger.error(f"   ❌ 交換數據獲取失敗")
                        return None
        except Exception as e:
            logger.error(f"   ❌ 交換數據錯誤: {str(e)}")
            return None
    
    async def check_allowance(self, token_address: str, spender: str) -> int:
        """檢查授權額度"""
        try:
            token_address = Web3.to_checksum_address(token_address)
            spender = Web3.to_checksum_address(spender)
            
            contract = self.w3.eth.contract(
                address=token_address,
                abi=[
                    {
                        "constant": True,
                        "inputs": [
                            {"name": "_owner", "type": "address"},
                            {"name": "_spender", "type": "address"}
                        ],
                        "name": "allowance",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "type": "function"
                    }
                ]
            )
            
            allowance = contract.functions.allowance(self.address, spender).call()
            return allowance
        except Exception as e:
            logger.error(f"   ❌ 檢查授權失敗: {str(e)}")
            return 0
    
    async def approve_token(self, token_address: str, spender: str, amount: int) -> Optional[str]:
        """授權代幣"""
        logger.info(f"💰 授權代幣...")
        
        try:
            token_address = Web3.to_checksum_address(token_address)
            spender = Web3.to_checksum_address(spender)
            
            contract = self.w3.eth.contract(
                address=token_address,
                abi=[
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "_spender", "type": "address"},
                            {"name": "_value", "type": "uint256"}
                        ],
                        "name": "approve",
                        "outputs": [{"name": "", "type": "bool"}],
                        "type": "function"
                    }
                ]
            )
            
            tx = contract.functions.approve(spender, amount).build_transaction({
                'from': self.address,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"   ✅ 授權交易已發送: {tx_hash.hex()}")
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            logger.info(f"   ✅ 授權確認")
            
            return tx_hash.hex()
        except Exception as e:
            logger.error(f"   ❌ 授權失敗: {str(e)}")
            return None
    
    async def execute_swap(self, token_in: str, token_out: str, amount_in: int) -> Optional[str]:
        """
        執行完整的交換流程
        
        參數:
            token_in: 要賣出的代幣地址
            token_out: 要買入的代幣地址
            amount_in: 要賣出的金額 (wei)
        
        返回:
            交換交易哈希或 None
        """
        try:
            log_debug(f"\n🔄 開始執行交換")
            log_debug(f"   賣出: {amount_in} wei")
            log_debug(f"   從: {token_in}")
            log_debug(f"   到: {token_out}")
            
            # 1. 獲取報價
            log_debug(f"🔍 獲取 0x 報價...")
            quote = await self.get_0x_quote(token_in, token_out, amount_in)
            if not quote:
                logger.error("❌ 無法獲取報價")
                return None
            log_debug(f"   ✅ 報價成功: {quote.get('buyAmount', 'N/A')} 買入金額")
            
            # 2. 獲取交換交易數據
            log_debug(f"🔍 獲取 0x 交換交易數據...")
            swap_data = await self.get_0x_swap_tx(token_in, token_out, amount_in)
            if not swap_data:
                logger.error("❌ 無法獲取交換數據")
                return None
            log_debug(f"   ✅ 交換數據獲取成功")
            
            # 3. 檢查授權
            log_debug(f"🔐 檢查授權...")
            allowance_target = swap_data.get('allowanceTarget')
            current_allowance = await self.check_allowance(token_in, allowance_target)
            
            if current_allowance < amount_in:
                log_debug(f"   需要授權，執行授權交易...")
                await self.approve_token(token_in, allowance_target, amount_in * 2)
            else:
                log_debug(f"   ✅ 已有足夠授權")
            
            # 4. 構建交易
            log_debug(f"🏗️  構建交易...")
            tx_data = swap_data.get('transaction', {})
            tx_dict = {
                'to': Web3.to_checksum_address(tx_data['to']),
                'from': self.address,
                'data': tx_data.get('data', '0x'),
                'value': int(tx_data.get('value', 0)),
                'gas': int(tx_data.get('gas', 500000)),
                'gasPrice': int(tx_data.get('gasPrice', self.w3.eth.gas_price)),
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'chainId': self.chain_id
            }
            
            # 5. 簽名交易
            log_debug(f"✍️  簽名交易...")
            signed_tx = self.w3.eth.account.sign_transaction(tx_dict, self.private_key)
            
            # 6. 發送交易
            log_debug(f"📤 發送交易...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"🔄 開始執行交換")
            logger.info(f"   ✅ 交易已發送: {tx_hash.hex()}")
            
            # 7. 等待確認
            log_debug(f"⏳ 等待交易確認...")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                log_debug(f"🎉 交換成功！")
                log_debug(f"   區塊: {receipt['blockNumber']}")
                log_debug(f"   Gas 使用: {receipt['gasUsed']}")
                return tx_hash.hex()
            else:
                logger.error(f"❌ 交換失敗 - 交易被 Reverted")
                logger.error(f"   交易哈希: {tx_hash.hex()}")
                logger.error(f"   區塊: {receipt.get('blockNumber', 'N/A')}")
                logger.error(f"   Gas 使用: {receipt.get('gasUsed', 'N/A')}")
                logger.error(f"   Gas 限制: {receipt.get('gas', 'N/A')}")
                return None
                
        except Exception as e:
            logger.error(f"❌ 執行交換失敗: {str(e)}", exc_info=True)
            return None


# 便利函數，直接調用
async def swap(token_in: str, token_out: str, amount_in: int, chain_id: int = 8453) -> Optional[str]:
    """
    快速交換函數
    
    使用方式:
        tx_hash = await swap(
            token_in="0x...",
            token_out="0x...",
            amount_in=1000000000000000000
        )
    """
    executor = SwapExecutor(chain_id=chain_id)
    return await executor.execute_swap(token_in, token_out, amount_in)
