"""
OKX DEX 聚合器實現
✅ 支持免費使用（某些端點）
✅ 支持認證使用（更高限額）
"""

import logging
import asyncio
import aiohttp
from typing import Dict, Optional
from web3 import Web3
from .base import AggregatorBase

logger = logging.getLogger(__name__)

class OKXAggregator(AggregatorBase):
    """OKX DEX 聚合器"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, api_passphrase: str = None, project_id: str = None):
        super().__init__(name="OKX", api_key=api_key)
        self.base_url = "https://web3.okx.com/api/v6/dex"
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.project_id = project_id  # Project ID 方式（最簡單）
        
        # OKX 支持的鏈
        self.chain_mapping = {
            1: "1",           # Ethereum
            56: "56",         # BSC
            137: "137",       # Polygon
            43114: "43114",   # Avalanche
            250: "250",       # Fantom
            8453: "8453",     # Base
        }
        
        # 用戶代理
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    def _build_headers(self) -> Dict[str, str]:
        """構建 OKX API 請求頭"""
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
        }
        
        # 優先使用 Project ID（最簡單）
        if self.project_id:
            headers['OK-ACCESS-PROJECT'] = self.project_id
            logger.debug(f"使用 OKX Project ID 認證")
        
        # 或者使用 API Key 認證（需要更多配置）
        elif self.api_key:
            headers['OK-ACCESS-KEY'] = self.api_key
            if self.api_passphrase:
                headers['OK-ACCESS-PASSPHRASE'] = self.api_passphrase
            logger.debug(f"使用 OKX API Key 認證")
        
        return headers
    
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount: int) -> Optional[Dict]:
        """
        獲取 OKX 交換報價
        """
        try:
            if not self.chain_id:
                logger.error("❌ OKX: 未設置 chain_id")
                return None
            
            chain_index = self.chain_mapping.get(self.chain_id)
            if not chain_index:
                logger.warning(f"⚠️  OKX 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            
            url = f"{self.base_url}/aggregator/quote"
            params = {
                'chainIndex': chain_index,
                'fromTokenAddress': token_in,
                'toTokenAddress': token_out,
                'amount': str(amount),
                'slippagePercent': '0.5',
            }
            
            headers = self._build_headers()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            result = data['data'][0]
                            
                            return {
                                'fromToken': token_in,
                                'toToken': token_out,
                                'toAmount': int(result.get('outAmount', 0)),
                                'estimatedGas': int(result.get('estimatedGas', 150000)),
                                'source': 'okx',
                                'priceImpact': float(result.get('priceImpact', 0)),
                                'rawData': result
                            }
                        else:
                            msg = data.get('msg', 'Unknown error')
                            logger.warning(f"⚠️  OKX API 錯誤: {msg}")
                            return None
                    elif resp.status == 401 or resp.status == 403:
                        logger.warning(f"⚠️  OKX API 認證失敗 ({resp.status})")
                        return None
                    else:
                        logger.warning(f"⚠️  OKX API ({resp.status})")
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  OKX API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  OKX 報價錯誤: {str(e)}")
            return None
    
    async def get_swap_tx(self,
                         token_in: str,
                         token_out: str,
                         amount: int,
                         from_address: str,
                         slippage: float = 0.5) -> Optional[Dict]:
        """
        獲取 OKX 交換交易數據
        """
        try:
            if not self.chain_id:
                logger.error("❌ OKX: 未設置 chain_id")
                return None
            
            chain_index = self.chain_mapping.get(self.chain_id)
            if not chain_index:
                logger.warning(f"⚠️  OKX 不支持鏈 ID {self.chain_id}")
                return None
            
            token_in = Web3.to_checksum_address(token_in)
            token_out = Web3.to_checksum_address(token_out)
            from_address = Web3.to_checksum_address(from_address)
            
            url = f"{self.base_url}/aggregator/swap"
            params = {
                'chainIndex': chain_index,
                'fromTokenAddress': token_in,
                'toTokenAddress': token_out,
                'amount': str(amount),
                'userAddr': from_address,
                'slippagePercent': str(slippage),
            }
            
            headers = self._build_headers()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get('code') == '0' and data.get('data'):
                            result = data['data'][0]
                            tx_data = result.get('tx', {})
                            
                            return {
                                'to': tx_data.get('to'),
                                'data': tx_data.get('data'),
                                'value': tx_data.get('value', '0'),
                                'gas': int(tx_data.get('gas', 300000)),
                                'minAmount': int(result.get('minOutAmount', 0)),
                                'source': 'okx',
                                'rawData': result
                            }
                        else:
                            msg = data.get('msg', 'Unknown error')
                            logger.warning(f"⚠️  OKX 交換錯誤: {msg}")
                            return None
                    else:
                        logger.warning(f"⚠️  OKX 交換 ({resp.status})")
                        return None
        
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  OKX API 超時")
            return None
        except Exception as e:
            logger.warning(f"⚠️  OKX 交換錯誤: {str(e)}")
            return None
    
    async def is_available(self) -> bool:
        """檢查 OKX 是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/aggregator/quote?chainIndex=8453&fromTokenAddress=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913&toTokenAddress=0x4200000000000000000000000000000000000006&amount=1000000",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status in [200, 401, 403]  # 即使需要認證也視為可用
        except:
            return False
