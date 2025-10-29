"""
聚合器基礎類 - 定義所有聚合器必須實現的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional
from decimal import Decimal

class AggregatorBase(ABC):
    """所有 DEX 聚合器的基礎類"""
    
    def __init__(self, name: str, api_key: str = None):
        """初始化聚合器"""
        self.name = name
        self.api_key = api_key
        self.chain_id = None
    
    @abstractmethod
    async def get_quote(self, 
                       token_in: str, 
                       token_out: str, 
                       amount: int) -> Optional[Dict]:
        """獲取交換報價"""
        pass
    
    @abstractmethod
    async def get_swap_tx(self,
                         token_in: str,
                         token_out: str,
                         amount: int,
                         from_address: str,
                         slippage: float = 1.0) -> Optional[Dict]:
        """獲取交換交易數據"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """檢查聚合器是否可用"""
        pass
    
    def set_chain(self, chain_id: int):
        """設置鏈 ID"""
        self.chain_id = chain_id
