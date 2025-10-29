"""
1inch DEX 聚合器實現（模組化）
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Optional
from web3 import Web3
from .base import AggregatorBase

logger = logging.getLogger(__name__)

class OneInchAggregator(AggregatorBase):
    """1inch DEX 聚合器"""
    
    def __init__(self, api_key: str = None):
        super().__init__(name="1inch", api_key=api_key)
        self.base_url = "https://api.1inch.dev/v5.2"
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount: int) -> Optional[Dict]:
        """獲取 1inch 報價"""
        try:
            if not self.api_key:
                return None
            
            if not self.chain_id:
                logger.error("❌ 1inch: 未設置 chain_id")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = f"{self.base_url}/{self.chain_id}/quote"
            params = {
                'tokenIn': token_in,
                'tokenOut': token_out,
                'amount': str(amount)
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}'
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
                            'toAmount': int(data.get('toAmount', 0)),
                            'estimatedGas': int(data.get('estimatedGas', 150000)),
                            'source': '1inch',
                            'protocols': data.get('protocols', [])
                        }
                    elif resp.status == 401:
                        logger.warning(f"⚠️  1inch API Key 無效")
                        return None
                    elif resp.status == 429:
                        logger.warning(f"⚠️  1inch 速率限制")
                        return None
                    else:
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  1inch API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  1inch 報價錯誤: {str(e)}")
            return None
    
    async def get_swap_tx(self,
                         token_in: str,
                         token_out: str,
                         amount: int,
                         from_address: str,
                         slippage: float = 1.0) -> Optional[Dict]:
        """獲取 1inch 交換交易數據"""
        try:
            if not self.api_key:
                logger.warning(f"⚠️  1inch API Key 未配置")
                return None
            
            if not self.chain_id:
                logger.error("❌ 1inch: 未設置 chain_id")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            from_address = Web3.to_checksum_address(from_address)
            
            url = f"{self.base_url}/{self.chain_id}/swap"
            params = {
                'tokenIn': token_in,
                'tokenOut': token_out,
                'amount': str(amount),
                'from': from_address,
                'slippage': str(slippage)
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}'
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
                        tx_data = data.get('tx', {})
                        
                        return {
                            'to': tx_data.get('to'),
                            'data': tx_data.get('data'),
                            'value': tx_data.get('value', '0'),
                            'gas': int(tx_data.get('gas', 300000)),
                            'minAmount': int(data.get('toAmount', 0)),
                            'source': '1inch'
                        }
                    elif resp.status == 401:
                        logger.warning(f"⚠️  1inch API Key 無效")
                        return None
                    elif resp.status == 429:
                        logger.warning(f"⚠️  1inch 速率限制")
                        return None
                    else:
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  1inch API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  1inch 交換錯誤: {str(e)}")
            return None
    
    async def is_available(self) -> bool:
        """檢查 1inch 是否可用"""
        if not self.api_key:
            return False
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/{self.chain_id}/healthcheck",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except:
            return False
