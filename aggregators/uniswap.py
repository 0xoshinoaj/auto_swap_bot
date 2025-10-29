"""
Uniswap V3 DEX 聚合器實現
✅ 完全免費
✅ 無需 API Key
✅ 無需認證
✅ 無限請求
✅ 完全去中心化
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Optional
from web3 import Web3
from .base import AggregatorBase

logger = logging.getLogger(__name__)

class UniswapAggregator(AggregatorBase):
    """Uniswap V3 DEX 聚合器 - 完全免費選擇"""
    
    def __init__(self):
        super().__init__(name="Uniswap", api_key=None)
        # Uniswap 官方 API - 完全免費，無需認證
        self.base_url = "https://api.uniswap.org/v1"
        
        # Uniswap 支持的鏈
        self.chain_mapping = {
            1: "ethereum",      # Ethereum
            56: "bnb",          # BSC
            137: "polygon",     # Polygon
            43114: "avalanche", # Avalanche
            250: "fantom",      # Fantom
            8453: "base",       # Base
        }
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount: int) -> Optional[Dict]:
        """
        獲取 Uniswap 交換報價
        """
        try:
            if not self.chain_id:
                logger.error("❌ Uniswap: 未設置 chain_id")
                return None
            
            chain_name = self.chain_mapping.get(self.chain_id)
            if not chain_name:
                logger.warning(f"⚠️  Uniswap 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = f"{self.base_url}/quote"
            params = {
                'tokenInAddress': token_in,
                'tokenOutAddress': token_out,
                'amount': str(amount),
                'type': 'exactIn',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    params=params, 
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if 'quote' in data:
                            quote = data['quote']
                            
                            return {
                                'fromToken': token_in,
                                'toToken': token_out,
                                'toAmount': int(quote),
                                'estimatedGas': 150000,
                                'source': 'uniswap',
                                'priceImpact': float(data.get('priceImpact', 0)),
                                'rawData': data
                            }
                        else:
                            logger.warning(f"⚠️  Uniswap 響應格式異常")
                            return None
                    else:
                        logger.warning(f"⚠️  Uniswap API ({resp.status})")
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  Uniswap API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  Uniswap 報價錯誤: {str(e)}")
            return None
    
    async def get_swap_tx(self,
                         token_in: str,
                         token_out: str,
                         amount: int,
                         from_address: str,
                         slippage: float = 0.5) -> Optional[Dict]:
        """
        獲取 Uniswap 交換交易數據
        """
        try:
            if not self.chain_id:
                logger.error("❌ Uniswap: 未設置 chain_id")
                return None
            
            chain_name = self.chain_mapping.get(self.chain_id)
            if not chain_name:
                logger.warning(f"⚠️  Uniswap 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            from_address = Web3.to_checksum_address(from_address)
            
            url = f"{self.base_url}/swap"
            params = {
                'tokenInAddress': token_in,
                'tokenOutAddress': token_out,
                'amount': str(amount),
                'recipient': from_address,
                'slippageTolerance': str(slippage),
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if 'transaction' in data:
                            tx = data['transaction']
                            
                            return {
                                'to': tx.get('to'),
                                'data': tx.get('data'),
                                'value': tx.get('value', '0'),
                                'gas': int(tx.get('gasLimit', 300000)),
                                'minAmount': int(data.get('minimumAmountOut', 0)),
                                'source': 'uniswap',
                                'rawData': data
                            }
                        else:
                            logger.warning(f"⚠️  Uniswap 交換響應格式異常")
                            return None
                    else:
                        logger.warning(f"⚠️  Uniswap 交換 ({resp.status})")
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  Uniswap API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  Uniswap 交換錯誤: {str(e)}")
            return None
    
    async def is_available(self) -> bool:
        """檢查 Uniswap 是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except:
            return False
