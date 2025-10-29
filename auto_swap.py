"""
自動賣幣機器人 - 安全第一版本
目的：自動將收到的代幣換成原生 Gas Token (ETH/BNB 等)
特性：WebSocket + 輪詢混合監聽、多層安全檢查、低延遲

使用方式:
    python3 auto_swap.py
"""

import os
import logging
from web3 import Web3
from web3.contract import Contract
from dotenv import load_dotenv
from typing import Dict, List, Optional, Set, Tuple
import asyncio
from decimal import Decimal
import aiohttp
import time
import config
from swap_executor import SwapExecutor
import json
try:
    import websockets
except ImportError:
    websockets = None

# 配置日誌
def setup_logging():
    """根據配置設置日誌級別"""
    log_debug = getattr(config, 'LOG_DEBUG', False)
    
    if log_debug:
        # 詳細模式：顯示 DEBUG 及以上所有信息
        level = logging.DEBUG
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    else:
        # 簡約模式：只顯示 INFO 及以上
        level = logging.INFO
        format_str = '%(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        force=True  # 強制覆蓋已有配置
    )

setup_logging()
logger = logging.getLogger(__name__)

# ==================== 日誌輔助函數 ====================
def log_debug(msg: str):
    """僅在 DEBUG 模式下輸出"""
    if config.LOG_DEBUG:
        logger.info(msg)
    else:
        logger.debug(msg)

# ==================== 配置管理 ====================
class Config:
    """配置管理類"""
    def __init__(self):
        load_dotenv()
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('RPC_URL')
        self.wss_url = os.getenv('WS_RPC_URL', '')  # WebSocket URL（可选）
        
        # 自動從 RPC 获取 Chain ID
        try:
            w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.chain_id = w3.eth.chain_id
            logger.info(f"✅ 从 RPC 自动获取 Chain ID: {self.chain_id}")
        except:
            # 备用方案：从 .env 读取，默认 Base
            self.chain_id = int(os.getenv('CHAIN_ID', '8453'))
            logger.warning(f"⚠️ 无法从 RPC 获取 Chain ID，使用配置值: {self.chain_id}")
        
        # API 配置（隱私信息，来自 .env）
        self.zx_api_key = os.getenv('ZX_API_KEY', '')
        self.oneinch_api_key = os.getenv('ONEINCH_API_KEY', '')
        
        # 所有功能参数从 config.py 读取（集中配置）
        self.min_liquidity_usd = config.MIN_LIQUIDITY
        self.gas_multiplier = config.GAS_MULTIPLIER
        self.min_sell_amount_usd = config.MIN_SELL_AMOUNT
        self.max_gas_price_gwei = config.MAX_GAS_PRICE
        self.monitor_interval = config.MONITOR_INTERVAL
        self.safe_mode = config.SAFE_MODE
        self.max_slippage_percent = config.MAX_SLIPPAGE
        self.DUPLICATE_CHECK_BLOCKS = config.DUPLICATE_CHECK_BLOCKS
        self.native_token_symbol = 'ETH'
        
        # 黑名單
        self.blacklist_tokens = set(
            addr.lower() for addr in config.DEFAULT_BLACKLIST_TOKENS
        )
        self.whitelist_tokens = set(
            addr.lower() for addr in config.DEFAULT_WHITELIST_TOKENS
        )

# ==================== Web3 連接管理 ====================
class Web3Manager:
    """Web3 連接和錢包管理"""
    def __init__(self, config: Config):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        self.account = self.w3.eth.account.from_key(config.private_key)
        self.address = self.account.address
        logger.info(f"✅ Web3 連接成功: {self.address}")
        
    def get_balance(self, token_address: Optional[str] = None) -> Decimal:
        """獲取餘額 (原生幣或 ERC20)"""
        if token_address is None:
            balance = self.w3.eth.get_balance(self.address)
            return Decimal(self.w3.from_wei(balance, 'ether'))
        else:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=self._get_erc20_abi()
            )
            balance = contract.functions.balanceOf(self.address).call()
            decimals = contract.functions.decimals().call()
            return Decimal(balance) / Decimal(10 ** decimals)
    
    def _get_erc20_abi(self) -> List:
        """基本 ERC20 ABI"""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
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
    
    def get_contract(self, token_address: str) -> Contract:
        """獲取合約實例"""
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=self._get_erc20_abi()
        )

# ==================== 安全檢查器 ====================
class SecurityChecker:
    """代幣安全檢查模組"""
    def __init__(self, config: Config, w3_manager: Web3Manager):
        self.config = config
        self.w3_manager = w3_manager
        self.checked_tokens: Dict[str, Dict] = {}  # 緩存檢查結果
        
    def is_in_whitelist(self, token_address: str) -> bool:
        """檢查是否在白名單中"""
        token_addr = token_address.lower()
        if not self.config.whitelist_tokens:
            return True  # 如果沒有白名單，則所有代幣通過
        return token_addr in self.config.whitelist_tokens
    
    def is_in_blacklist(self, token_address: str) -> bool:
        """檢查是否在黑名單中"""
        token_addr = token_address.lower()
        return token_addr in self.config.blacklist_tokens
    
    async def validate_token(self, token_address: str) -> Tuple[bool, str]:
        """
        全面驗證代幣安全性
        返回: (是否安全, 原因)
        """
        token_addr = token_address.lower()
        
        # 1. 檢查黑名單
        if self.is_in_blacklist(token_address):
            logger.warning(f"🚫 代幣在黑名單中: {token_address}")
            return False, "Token in blacklist"
        
        # 2. 檢查白名單（如果白名單存在）
        if not self.is_in_whitelist(token_address):
            logger.warning(f"🚫 代幣不在白名單中: {token_address}")
            return False, "Token not in whitelist"
        
        # 3. 檢查合約有效性
        if not self.w3_manager.w3.is_address(token_address):
            logger.error(f"❌ 無效地址: {token_address}")
            return False, "Invalid token address"
        
        try:
            # 4. 嘗試讀取基本信息（檢查合約是否有效）
            contract = self.w3_manager.get_contract(token_address)
            decimals = contract.functions.decimals().call()
            total_supply = contract.functions.totalSupply().call()
            
            if total_supply == 0:
                logger.warning(f"⚠️  代幣供應量為 0: {token_address}")
                return False, "Zero total supply"
            
            logger.info(f"✅ 代幣有效: {token_address} (decimals={decimals})")
            return True, "Token valid"
            
        except Exception as e:
            logger.error(f"❌ 驗證代幣失敗 {token_address}: {str(e)}")
            return False, f"Contract error: {str(e)}"
    
    async def check_gas_price(self) -> Tuple[bool, float]:
        """
        檢查當前 Gas 價格是否在可接受範圍
        返回: (是否接受, gas價格 gwei)
        """
        try:
            gas_price_wei = self.w3_manager.w3.eth.gas_price
            gas_price_gwei = self.w3_manager.w3.from_wei(gas_price_wei, 'gwei')
            
            if gas_price_gwei > self.config.max_gas_price_gwei:
                logger.warning(f"⚠️  Gas 價格過高: {gas_price_gwei} gwei (上限: {self.config.max_gas_price_gwei})")
                return False, gas_price_gwei
            
            logger.info(f"✅ Gas 價格正常: {gas_price_gwei} gwei")
            return True, gas_price_gwei
            
        except Exception as e:
            logger.error(f"❌ 無法獲取 Gas 價格: {str(e)}")
            return False, 0.0

# ==================== 代幣監控 ====================
class TokenMonitor:
    """
    監控錢包收到的新代幣
    使用 WebSocket + 輪詢混合方案
    """
    def __init__(self, config: Config, w3_manager: Web3Manager):
        self.config = config
        self.w3_manager = w3_manager
        self.known_tokens: Set[str] = set()
        self.processed_events: Set[Tuple[str, str]] = set()  # (token_address, tx_hash) 組合，防止同一轉入事件重複處理
        self.token_last_block: Dict[str, int] = {}  # 記錄代幣最後一次出現的區塊（用於區塊冷卻檢查）
        self.last_block_scanned = 0
        self.ws_connected = False
        
    async def scan_recent_blocks(self, num_blocks: int = 100) -> List[str]:
        """掃描最近的 N 個區塊找尋 Transfer 事件"""
        new_tokens = []
        
        try:
            current_block = self.w3_manager.w3.eth.block_number
            start_block = max(current_block - num_blocks, self.last_block_scanned + 1)
            
            # 構建 Transfer 事件過濾器
            # Transfer(address indexed from, address indexed to, uint256 value)
            event_signature = Web3.keccak(text="Transfer(address,address,uint256)")
            
            # 修復：Ankr RPC 對 topics 格式要求
            # 改用簡化的參數格式
            logs = self.w3_manager.w3.eth.get_logs({
                'fromBlock': start_block,
                'toBlock': current_block,
                'topics': [event_signature.hex()]  # 只包含 Transfer 簽名
            })
            
            # 手動過濾：只保留發送到我們地址的 Transfer
            my_address = Web3.to_checksum_address(self.w3_manager.address).lower()
            
            for log in logs:
                tx_hash = log['transactionHash'].hex()
                
                # 防重複檢查
                if (log['address'].lower(), tx_hash) in self.processed_events:
                    continue
                
                # Transfer 事件格式:
                # topics[0] = Transfer 簽名
                # topics[1] = from (indexed)
                # topics[2] = to (indexed)
                # data = value
                
                # 檢查 topics[2] 是否是我們的地址
                if len(log['topics']) >= 3:
                    to_address = log['topics'][2].hex()
                    # 補充為完整地址（移除前導 0）
                    to_address = '0x' + to_address[-40:].lower()
                    
                    if to_address == my_address:
                        token_address = log['address'].lower()
                        block_number = log['blockNumber']
                        
                        # 避免重複 - 檢查該代幣在最近區塊是否已被檢測
                        if token_address in self.token_last_block:
                            last_block = self.token_last_block[token_address]
                            # 如果在過去 DUPLICATE_CHECK_BLOCKS 個區塊內已檢測過，跳過
                            if block_number - last_block < self.config.DUPLICATE_CHECK_BLOCKS:
                                logger.debug(f"⏭️ 代幣 {token_address} 最近已檢測過（區塊 {last_block}），跳過")
                                continue
                        
                        # 新代幣或冷卻期已過的重新轉入
                        if token_address not in self.known_tokens:
                            self.known_tokens.add(token_address)
                        
                        self.token_last_block[token_address] = block_number
                        self.processed_events.add((token_address, tx_hash))
                        
                        new_tokens.append(Web3.to_checksum_address(token_address))
                        logger.info(f"🔍 發現新代幣: {token_address} (區塊 {block_number})")
            
            self.last_block_scanned = current_block
            
        except Exception as e:
            logger.error(f"❌ 掃描區塊失敗: {str(e)}")
        
        return new_tokens
    
    async def monitor_loop_polling(self, callback):
        """輪詢模式監控（備用方案）"""
        logger.info("📡 啟動輪詢監控...")
        retry_count = 0
        max_retries = 5
        heartbeat_interval = 30  # 每 30 秒顯示一次心跳
        last_heartbeat = 0
        
        while True:
            try:
                current_time = time.time()
                
                # 掃描最近區塊找新代幣
                new_tokens = await self.scan_recent_blocks(
                    num_blocks=self.config.monitor_interval
                )
                
                # 如果發現新代幣，立即處理
                if new_tokens:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"🎉 發現 {len(new_tokens)} 個新代幣！")
                    logger.info(f"{'='*60}\n")
                    
                    for token in new_tokens:
                        try:
                            logger.info(f"⚡ 正在處理: {token}")
                            await callback(token)
                        except Exception as e:
                            logger.error(f"❌ 處理代幣失敗 {token}: {str(e)}")
                else:
                    # 顯示心跳 - 每 30 秒顯示一次
                    if current_time - last_heartbeat >= heartbeat_interval:
                        logger.info(f"💓 機器人正常運行中... (已監控 {len(self.known_tokens)} 個代幣)")
                        last_heartbeat = current_time
                
                retry_count = 0  # 重置重試計數
                await asyncio.sleep(self.config.monitor_interval)
                
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ 輪詢出錯 (重試 {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count >= max_retries:
                    logger.error("❌ 輪詢失敗次數過多，重啟...")
                    retry_count = 0
                    await asyncio.sleep(10)
                else:
                    await asyncio.sleep(5)
    
    async def monitor_loop_websocket(self, callback):
        """WebSocket 模式監控（實時監聽）"""
        if not websockets:
            logger.warning("⚠️  websockets 庫未安裝，降級為輪詢模式")
            await self.monitor_loop_polling(callback)
            return
        
        if not self.config.wss_url:
            logger.warning("⚠️  WSS_URL 未配置，降級為輪詢模式")
            await self.monitor_loop_polling(callback)
            return
        
        logger.info("📡 啟動 WebSocket 監控...")
        retry_count = 0
        max_retries = 5
        heartbeat_interval = 30
        last_heartbeat = 0
        
        while True:
            try:
                async with websockets.connect(self.config.wss_url) as ws:
                    self.ws_connected = True
                    logger.info("✅ WebSocket 連接成功")
                    retry_count = 0
                    
                    # 訂閱 Transfer 事件
                    event_signature = Web3.keccak(text="Transfer(address,address,uint256)").hex()
                    my_address = Web3.to_checksum_address(self.w3_manager.address)
                    
                    # 構建訂閱請求
                    subscribe_msg = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_subscribe",
                        "params": [
                            "logs",
                            {
                                "topics": [event_signature],  # Transfer 事件簽名
                                "address": None  # 監聽所有合約的 Transfer
                            }
                        ]
                    }
                    
                    await ws.send(json.dumps(subscribe_msg))
                    subscription_id = None
                    
                    # 接收消息
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=60)
                            data = json.loads(message)
                            
                            # 處理訂閱確認
                            if data.get("method") == "eth_subscription" and data.get("params"):
                                result = data["params"].get("result")
                                if result and isinstance(result, dict):
                                    log_data = result
                                    
                                    # 檢查是否發送到我們的地址
                                    if len(log_data.get('topics', [])) >= 3:
                                        to_address = log_data['topics'][2]
                                        # 補全為 checksum 地址
                                        to_address_str = '0x' + to_address[-40:].lower()
                                        
                                        if to_address_str.lower() == my_address.lower():
                                            token_address = log_data['address'].lower()
                                            tx_hash = log_data.get('transactionHash', '')
                                            block_number = int(log_data.get('blockNumber', '0x0'), 16)
                                            
                                            # 防重複檢查
                                            if (token_address, tx_hash) in self.processed_events:
                                                continue
                                            
                                            # 檢查冷卻期
                                            if token_address in self.token_last_block:
                                                last_block = self.token_last_block[token_address]
                                                if block_number - last_block < self.config.DUPLICATE_CHECK_BLOCKS:
                                                    log_debug(f"⏭️ 代幣 {token_address} 最近已檢測過，跳過")
                                                    continue
                                            
                                            # 新代幣或冷卻期已過的重新轉入
                                            if token_address not in self.known_tokens:
                                                self.known_tokens.add(token_address)
                                            
                                            self.token_last_block[token_address] = block_number
                                            self.processed_events.add((token_address, tx_hash))
                                            
                                            logger.info(f"\n{'='*60}")
                                            logger.info(f"🎉 發現新代幣！")
                                            logger.info(f"{'='*60}\n")
                                            logger.info(f"⚡ 正在處理: {Web3.to_checksum_address(token_address)}")
                                            
                                            try:
                                                await callback(Web3.to_checksum_address(token_address))
                                            except Exception as e:
                                                logger.error(f"❌ 處理代幣失敗: {str(e)}")
                            
                            # 心跳
                            current_time = time.time()
                            if current_time - last_heartbeat >= heartbeat_interval:
                                logger.info(f"💓 WebSocket 運行中... (已監控 {len(self.known_tokens)} 個代幣)")
                                last_heartbeat = current_time
                                
                        except asyncio.TimeoutError:
                            # 心跳超時，保持連接
                            current_time = time.time()
                            if current_time - last_heartbeat >= heartbeat_interval:
                                logger.info(f"💓 WebSocket 運行中... (已監控 {len(self.known_tokens)} 個代幣)")
                                last_heartbeat = current_time
                            continue
                        except Exception as e:
                            log_debug(f"⚠️  WebSocket 消息處理出錯: {str(e)}")
                            break
                    
            except Exception as e:
                retry_count += 1
                self.ws_connected = False
                logger.error(f"❌ WebSocket 連接失敗 (重試 {retry_count}/{max_retries}): {str(e)}")
                
                if retry_count >= max_retries:
                    logger.error("❌ WebSocket 失敗次數過多，降級為輪詢模式...")
                    await self.monitor_loop_polling(callback)
                    return
                else:
                    await asyncio.sleep(5)
    
    async def start_monitoring(self, callback):
        """啟動監控"""
        logger.info("🚀 開始監控代幣...")
        
        # 根據配置選擇監控方式
        if config.ENABLE_WEBSOCKET:
            await self.monitor_loop_websocket(callback)
        else:
            await self.monitor_loop_polling(callback)

# ==================== 流動性檢查 ====================
class LiquidityChecker:
    """檢查代幣是否有足夠的流動性"""
    def __init__(self, config: Config, w3_manager: Web3Manager):
        self.config = config
        self.w3_manager = w3_manager
        
    async def check_liquidity_dexscreener(self, token_address: str) -> Dict:
        """使用 DexScreener API 檢查流動性"""
        try:
            # 邊界情況檢查：零地址不應該被查詢
            if token_address.lower() == '0x0000000000000000000000000000000000000000':
                logger.warning(f"⚠️ 零地址不是有效代幣: {token_address}")
                return {'has_liquidity': False, 'liquidity_usd': 0}
            
            # 邊界情況檢查：地址長度必須正確
            if not token_address.startswith('0x') or len(token_address) != 42:
                logger.warning(f"⚠️ 無效地址長度: {token_address}")
                return {'has_liquidity': False, 'liquidity_usd': 0}
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get('pairs', [])
                        
                        if not pairs:
                            return {'has_liquidity': False, 'liquidity_usd': 0}
                        
                        # 使用流動性最高的交易對
                        best_pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0)))
                        liquidity_usd = float(best_pair.get('liquidity', {}).get('usd', 0))
                        
                        return {
                            'has_liquidity': liquidity_usd > 0,
                            'liquidity_usd': liquidity_usd,
                            'best_pair': best_pair.get('pairAddress'),
                            'dex': best_pair.get('dexId'),
                            'price_usd': float(best_pair.get('priceUsd', 0))
                        }
        except Exception as e:
            logger.error(f"❌ DexScreener API 錯誤: {str(e)}")
        
        return {'has_liquidity': False, 'liquidity_usd': 0}
        
    async def check_liquidity(self, token_address: str) -> Dict:
        """檢查代幣流動性"""
        result = await self.check_liquidity_dexscreener(token_address)
        
        log_debug(f"💧 流動性檢查: {token_address}")
        log_debug(f"   - 流動性 USD: ${result['liquidity_usd']:.2f}")
        log_debug(f"   - DEX: {result.get('dex', 'N/A')}")
        
        return result
    
    def is_tradeable(self, liquidity_info: Dict) -> bool:
        """判斷是否可交易"""
        return (
            liquidity_info['has_liquidity'] and 
            liquidity_info['liquidity_usd'] >= self.config.min_liquidity_usd
        )

# ==================== 主要業務邏輯 ====================
class AutoSellBot:
    """自動賣幣機器人主類"""
    def __init__(self):
        self.config = Config()
        self.w3_manager = Web3Manager(self.config)
        self.security_checker = SecurityChecker(self.config, self.w3_manager)
        self.monitor = TokenMonitor(self.config, self.w3_manager)
        self.liquidity_checker = LiquidityChecker(self.config, self.w3_manager)
        self.swap_executor = SwapExecutor(chain_id=self.config.chain_id)
        
        logger.info(f"🤖 Bot 初始化完成")
        logger.info(f"   - 錢包: {self.w3_manager.address}")
        logger.info(f"   - 鏈 ID: {self.config.chain_id}")
        logger.info(f"   - 最小流動性: ${self.config.min_liquidity_usd}")
        logger.info(f"   - 安全模式: {'✅ 啟用' if self.config.safe_mode else '❌ 禁用'}")
    
    def _get_wrapped_native_token(self) -> str:
        """獲取原生幣的 Wrapped 版本地址"""
        wrapped_addresses = {
            1: "0xC02aaA39b223FE8D0A0e8e4F27ead9083C756Cc2",      # WETH on Ethereum
            56: "0xbb4CdB9CBd36B01bD1cbaEBF2De08d9173bc095c",     # WBNB on BSC
            137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",    # WMATIC on Polygon
            8453: "0x4200000000000000000000000000000000000006",    # WETH on Base
            43114: "0xB31f66AA3C1e785363F0875A1B74789A8B9b05409",  # WAVAX on Avalanche
            250: "0x74b23882a30290451A17c44f4F05a28f9A20be19",    # WETH on Fantom
        }
        
        wrapped = wrapped_addresses.get(self.config.chain_id)
        if not wrapped:
            logger.warning(f"⚠️ 未知的鏈 ID: {self.config.chain_id}，使用預設 WETH")
            wrapped = "0xC02aaA39b223FE8D0A0e8e4F27ead9083C756Cc2"
        
        return wrapped
    
    async def process_token(self, token_address: str):
        """處理單個代幣的完整流程 - 直接交換成原生 Gas Token"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 開始處理代幣: {token_address}")
        logger.info(f"{'='*60}")
        
        try:
            # 0. 檢查是否是目標 Gas Token（跳過自己）
            native_token = self._get_wrapped_native_token()
            if token_address.lower() == native_token.lower():
                log_debug(f"   ⏭️  代幣本身就是目標 Gas Token，跳過")
                return
            
            # 1. 安全驗證
            if self.config.safe_mode:
                log_debug("▶ 步驟 1/4: 安全驗證中...")
                is_safe, reason = await self.security_checker.validate_token(token_address)
                if not is_safe:
                    logger.warning(f"   🚫 代幣驗證失敗: {reason}")
                    return
                logger.info(f"▶ 步驟 1/4: 安全驗證中...")
                logger.info(f"   ✅ 代幣驗證通過")
            
            # 2. 檢查餘額（獲取全部代幣）
            log_debug("▶ 步驟 2/4: 檢查餘額...")
            balance = self.w3_manager.get_balance(token_address)
            if balance <= 0:
                logger.warning(f"   ❌ 餘額為 0，跳過")
                return
            
            logger.info("▶ 步驟 2/4: 檢查餘額...")
            logger.info(f"   ✅ 代幣餘額: {balance}")
            
            # 3. 檢查 Gas 價格
            log_debug("▶ 步驟 3/4: 檢查 Gas 價格...")
            gas_ok, gas_price = await self.security_checker.check_gas_price()
            if not gas_ok and self.config.safe_mode:
                logger.warning(f"   ⚠️  Gas 價格過高: {gas_price} gwei，跳過交換")
                return
            logger.info("▶ 步驟 3/4: 檢查 Gas 價格...")
            logger.info(f"   ✅ Gas 價格: {gas_price:.2f} gwei")
            
            # 4. 檢查流動性
            log_debug("▶ 步驟 4/4: 檢查流動性...")
            liquidity_info = await self.liquidity_checker.check_liquidity(token_address)
            if not self.liquidity_checker.is_tradeable(liquidity_info):
                logger.warning(f"   ❌ 流動性不足: ${liquidity_info['liquidity_usd']:.2f}")
                return
            
            logger.info("▶ 步驟 4/4: 檢查流動性...")
            logger.info(f"   ✅ 流動性充足: ${liquidity_info['liquidity_usd']:,.2f}")
            
            # 5. 執行交換: 代幣 → 原生 Gas Token (WETH/WBNB 等)
            log_debug("▶ 步驟 5/4: 執行交換...")
            native_token = self._get_wrapped_native_token()
            
            # 獲取代幣的 decimals
            contract = self.w3_manager.get_contract(token_address)
            try:
                decimals = contract.functions.decimals().call()
            except:
                logger.warning(f"   ⚠️  無法獲取代幣 decimals，使用預設值 18")
                decimals = 18
            
            # 轉換代幣數量為 wei (根據實際 decimals)
            amount_wei = int(balance * 10 ** decimals)
            
            log_debug(f"   準備交換:")
            log_debug(f"     從: {token_address}")
            log_debug(f"     到: {native_token}")
            log_debug(f"     數量: {balance} 個代幣 ({amount_wei} wei, decimals={decimals})")
            
            logger.info("▶ 步驟 5/4: 執行交換...")
            logger.info(f"🔄 開始執行交換")
            logger.info(f"   ✅ 交易已發送: <待確認>")
            
            # 調用 SwapExecutor 執行交換
            tx_hash = await self.swap_executor.execute_swap(
                token_in=token_address,
                token_out=native_token,
                amount_in=amount_wei
            )
            
            if tx_hash:
                logger.info(f"🔄 開始執行交換")
                logger.info(f"   ✅ 交易已發送: {tx_hash}")
            else:
                logger.warning(f"   ⚠️  交換失敗")
                
        except Exception as e:
            logger.error(f"❌ 處理失敗: {str(e)}", exc_info=True)
    
    async def run(self):
        """啟動機器人"""
        logger.info("🚀 啟動自動賣幣機器人...")
        await self.monitor.start_monitoring(self.process_token)

# ==================== 主程序 ====================
async def main():
    bot = AutoSellBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())