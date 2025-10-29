"""
0x Protocol DEX 聚合器實現
✅ 支持官方 API
✅ 需要 API Key（免費獲取）
✅ 無 KYC 限制
✅ 無限請求（免費層）
✅ 最新 v2 API
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Optional
from web3 import Web3
from .base import AggregatorBase

logger = logging.getLogger(__name__)

class ZeroExAggregator(AggregatorBase):
    """0x Protocol DEX 聚合器 - 最優選擇"""
    
    def __init__(self, api_key: str = None):
        super().__init__(name="0x", api_key=api_key)
        # 0x 官方 API 端點 - 統一入口
        self.base_url = "https://api.0x.org/swap/allowance-holder"
        
        # 0x 支持的鏈
        self.chain_mapping = {
            1: 1,           # Ethereum
            56: 56,         # BSC
            137: 137,       # Polygon
            43114: 43114,   # Avalanche
            250: 250,       # Fantom
            8453: 8453,     # Base ✅
            42161: 42161,   # Arbitrum
            10: 10,         # Optimism
        }
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount: int) -> Optional[Dict]:
        """
        獲取 0x 交換報價（v2 API）
        """
        try:
            if not self.chain_id:
                logger.error("❌ 0x: 未設置 chain_id")
                return None
            
            chain_id = self.chain_mapping.get(self.chain_id)
            if not chain_id:
                logger.warning(f"⚠️  0x 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = f"{self.base_url}/quote"
            params = {
                'chainId': chain_id,
                'sellToken': token_in,
                'buyToken': token_out,
                'sellAmount': str(amount),
                'slippagePercentage': '1.0',
            }
            
            headers = {
                '0x-api-key': self.api_key or '',
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
                        
                        return {
                            'fromToken': token_in,
                            'toToken': token_out,
                            'toAmount': int(data.get('buyAmount', 0)),
                            'estimatedGas': int(data.get('route', {}).get('gas', 150000)),
                            'source': '0x',
                            'minAmount': int(data.get('minBuyAmount', 0)),
                            'rawData': data
                        }
                    elif resp.status == 400:
                        logger.warning(f"⚠️  0x 400 錯誤 - 可能無流動性")
                        return None
                    elif resp.status == 401:
                        logger.warning(f"⚠️  0x 401 - API Key 無效或未提供")
                        return None
                    else:
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  0x API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  0x 報價錯誤: {str(e)}")
            return None
    
    async def get_swap_tx(self,
                         token_in: str,
                         token_out: str,
                         amount: int,
                         from_address: str,
                         slippage: float = 1.0) -> Optional[Dict]:
        """
        獲取 0x 交換交易數據（v2 API）
        """
        try:
            if not self.chain_id:
                logger.error("❌ 0x: 未設置 chain_id")
                return None
            
            chain_id = self.chain_mapping.get(self.chain_id)
            if not chain_id:
                logger.warning(f"⚠️  0x 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            from_address = Web3.to_checksum_address(from_address)
            
            url = f"{self.base_url}/quote"
            
            params = {
                'chainId': chain_id,
                'sellToken': token_in,
                'buyToken': token_out,
                'sellAmount': str(amount),
                'taker': from_address,
                'slippagePercentage': str(slippage),
            }
            
            headers = {
                '0x-api-key': self.api_key or '',
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
                        route = data.get('route', {})
                        
                        return {
                            'to': route.get('to'),
                            'data': route.get('data'),
                            'value': route.get('value', '0'),
                            'gas': int(route.get('gas', 300000)),
                            'minAmount': int(data.get('minBuyAmount', 0)),
                            'source': '0x',
                            'rawData': data
                        }
                    else:
                        logger.warning(f"⚠️  0x 交換 ({resp.status})")
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  0x API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  0x 交換錯誤: {str(e)}")
            return None
    
    async def is_available(self) -> bool:
        """檢查 0x 是否可用"""
        try:
            # 簡單測試：查詢一個公知的交易對
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/quote",
                    params={
                        'chainId': 1,  # Ethereum
                        'sellToken': '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',  # WETH
                        'buyToken': '0x6b175474e89094c44da98b954eedeac495271d0f',  # DAI
                        'sellAmount': '1000000000000000000',  # 1 WETH
                    },
                    headers={
                        '0x-version': 'v2',
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    # 200 = 成功, 400 = 無流動性但 API 正常, 429 = 速率限制但 API 正常
                    return resp.status in [200, 400, 429]
        except:
            return False
