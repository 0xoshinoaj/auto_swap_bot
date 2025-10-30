"""
LP 池狙击者 - 自動販售模式
目的：監控指定的代幣合約，一旦有流動性就立即賣出

使用方式:
    python3 sniper_sell.py
"""

import os
import logging
from web3 import Web3
from dotenv import load_dotenv
from typing import Optional, Dict
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

# ==================== 🎯 目標代幣設定（在這裡修改要監控的代幣！）====================
TARGET_TOKEN = "0x2e622c04698e0970e7fb713a89f40a71fdcd1abc"  # 👈 改為你要監控的代幣地址
# =====================================================================================

# ==================== ⚙️ 狙擊策略配置（根據需要調整）====================
# 最小流動性要求 (USD)
MIN_LIQUIDITY_USD = 1000

# 流動性增長倍數（初始流動性 × 此倍數 才會觸發賣出）
# 例如：初始 $1000 → 需要增長到 $1500 (1.5倍) 才賣出
# 調整建議：
#   - 1.0 = 立即賣（容易被騙） 🔴 高風險
#   - 1.2 = 相對激進 🟠 中風險
#   - 1.5 = 平衡方案 🟡 推薦
#   - 2.0 = 保守方案 🟢 低風險
#   - 3.0 = 超保守 🟢🟢 極低風險
LIQUIDITY_GROWTH_THRESHOLD = 1.0

# 池子中代幣最少占比（防止項目方虛假流動性）
MIN_POOL_TOKEN_RATIO = 0.01  # 1%

# 檢查間隔 (秒)
CHECK_INTERVAL = 5

# 心跳顯示間隔 (秒)
HEARTBEAT_INTERVAL = 30
# =====================================================================================

# 音效支持
try:
    import winsound  # Windows
    SOUND_AVAILABLE = True
    SOUND_TYPE = 'windows'
except ImportError:
    try:
        from playsound import playsound  # 跨平台
        SOUND_AVAILABLE = True
        SOUND_TYPE = 'playsound'
    except ImportError:
        try:
            import os
            SOUND_AVAILABLE = True
            SOUND_TYPE = 'macos'  # macOS 內置
        except ImportError:
            SOUND_AVAILABLE = False
            SOUND_TYPE = None

# ==================== 配置日誌 ====================
def setup_logging():
    """根據配置設置日誌級別"""
    log_debug = getattr(config, 'LOG_DEBUG', False)
    
    if log_debug:
        level = logging.DEBUG
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    else:
        level = logging.INFO
        format_str = '%(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        force=True
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

# ==================== 音效通知 ====================
def play_alert_sound(alert_type: str = 'liquidity_found'):
    """播放警報聲音"""
    if not SOUND_AVAILABLE:
        logger.debug("⚠️  音效庫未安裝，跳過音效通知")
        return
    
    try:
        if SOUND_TYPE == 'windows':
            # Windows: 使用 winsound
            winsound.Beep(1000, 5000)  # 頻率 1000Hz，持續 500ms
            winsound.Beep(1200, 5000)  # 頻率 1200Hz，持續 500ms
            
        elif SOUND_TYPE == 'playsound':
            # 跨平台: 使用 playsound
            # 這需要音頻文件，我們生成一個簡單的警報
            logger.debug("🔔 已觸發警報音效")
            
        elif SOUND_TYPE == 'macos':
            # macOS: 使用原本的 Glass 聲音
            if alert_type == 'liquidity_found':
                # 發現流動性 - 播放 1 次
                os.system('afplay /System/Library/Sounds/Glass.aiff')
                
            elif alert_type == 'liquidity_growth_complete':
                # 流動性增長完成 - 播放 1 次
                os.system('afplay /System/Library/Sounds/Glass.aiff')
            
    except Exception as e:
        logger.debug(f"⚠️  播放音效失敗: {str(e)}")

# ==================== 配置管理 ====================
class Config:
    """配置管理類"""
    def __init__(self):
        load_dotenv()
        self.private_key = os.getenv('PRIVATE_KEY')
        self.rpc_url = os.getenv('RPC_URL')
        self.wss_url = os.getenv('WS_RPC_URL', '')
        
        try:
            w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            self.chain_id = w3.eth.chain_id
            logger.info(f"✅ 从 RPC 自动获取 Chain ID: {self.chain_id}")
        except:
            self.chain_id = int(os.getenv('CHAIN_ID', '8453'))
            logger.warning(f"⚠️ 无法从 RPC 获取 Chain ID，使用配置值: {self.chain_id}")
        
        # 從 config.py 讀取參數
        self.max_gas_price_gwei = config.MAX_GAS_PRICE
        self.safe_mode = config.SAFE_MODE
        self.min_liquidity_usd = config.MIN_LIQUIDITY
        self.DUPLICATE_CHECK_BLOCKS = config.DUPLICATE_CHECK_BLOCKS
        
        # ==================== 特定代幣監控配置 ====================
        # 要監控的代幣地址（硬編碼）
        # self.TARGET_TOKEN = "0x2e622c04698e0970e7fb713a89f40a71fdcd1abc"  # 改為你要監控的代幣
        
        # 流動性相關配置
        self.min_liquidity_usd = MIN_LIQUIDITY_USD
        self.min_pool_token_ratio = MIN_POOL_TOKEN_RATIO
        self.liquidity_growth_threshold = LIQUIDITY_GROWTH_THRESHOLD
        
        # 使用文件頂部設定的全局代幣地址
        self.TARGET_TOKEN = TARGET_TOKEN
        
        logger.info(f"🎯 監控目標代幣: {self.TARGET_TOKEN}")
        logger.info(f"   - 最小流動性: ${self.min_liquidity_usd}")
        logger.info(f"   - 最小池子代幣占比: {self.min_pool_token_ratio*100:.1f}%")
        logger.info(f"   - 流動性增長倍數: {self.liquidity_growth_threshold}x")

# ==================== Web3 連接管理 ====================
class Web3Manager:
    """Web3 連接和錢包管理"""
    def __init__(self, config: Config):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        self.account = self.w3.eth.account.from_key(config.private_key)
        self.address = self.account.address
        logger.info(f"✅ Web3 連接成功: {self.address}")
    
    def get_balance(self, token_address: str) -> float:
        """獲取代幣餘額"""
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=[
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
                    }
                ]
            )
            
            balance_wei = contract.functions.balanceOf(self.address).call()
            decimals = contract.functions.decimals().call()
            balance = balance_wei / (10 ** decimals)
            return balance
        except Exception as e:
            logger.error(f"❌ 獲取餘額失敗: {str(e)}")
            return 0
    
    def get_balance_wei(self, token_address: str) -> int:
        """獲取代幣餘額（精確的 wei 數量，不轉換成 float）"""
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=[
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
            )
            
            balance_wei = contract.functions.balanceOf(self.address).call()
            return balance_wei
        except Exception as e:
            logger.error(f"❌ 獲取 wei 餘額失敗: {str(e)}")
            return 0

# ==================== 流動性檢查 ====================
class LiquidityChecker:
    """檢查代幣是否有足夠的流動性"""
    def __init__(self, config: Config):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
    
    def get_token_total_supply(self, token_address: str) -> float:
        """獲取代幣總供應量"""
        try:
            contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=[
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "totalSupply",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "type": "function"
                    },
                    {
                        "constant": True,
                        "inputs": [],
                        "name": "decimals",
                        "outputs": [{"name": "", "type": "uint8"}],
                        "type": "function"
                    }
                ]
            )
            
            total_supply_wei = contract.functions.totalSupply().call()
            decimals = contract.functions.decimals().call()
            total_supply = total_supply_wei / (10 ** decimals)
            return total_supply
        except Exception as e:
            logger.error(f"❌ 獲取總供應量失敗: {str(e)}")
            return 0
    
    async def check_liquidity_dexscreener(self, token_address: str) -> Dict:
        """使用 DexScreener API 檢查流動性"""
        try:
            if token_address.lower() == '0x0000000000000000000000000000000000000000':
                logger.warning(f"⚠️ 零地址不是有效代幣: {token_address}")
                return {'has_liquidity': False, 'liquidity_usd': 0}
            
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
    
    async def estimate_swap_value(self, token_address: str, balance: float, liquidity_info: Dict) -> Dict:
        """
        根據 LP 池的實際比例，估算 swap 後能拿到多少原生幣
        
        返回：
        {
            'estimated_output': 0.123,  # 估算能拿到的 WETH/WBNB 等
            'pool_price': 1234.56,      # LP 池中的代幣價格
            'value_usd': 123.45         # USD 值
        }
        """
        try:
            # 如果有價格信息，直接用
            if 'price_usd' in liquidity_info and liquidity_info['price_usd'] > 0:
                price_usd = liquidity_info['price_usd']
                value_usd = balance * price_usd
                
                # 根據流動性估算輸出（假設流動性足夠，滑點較小）
                # 這是一個簡化的計算，實際還需考慮 AMM 公式
                estimated_output = value_usd / 1000  # 粗略估算（假設 WETH 約 $1000）
                
                log_debug(f"   💱 LP 價格信息:")
                log_debug(f"      代幣價格: ${price_usd:,.2f}")
                log_debug(f"      你的數量: {balance:.6f}")
                log_debug(f"      總價值: ${value_usd:,.2f}")
                log_debug(f"      估算換得: {estimated_output:.6f} WETH")
                
                return {
                    'estimated_output': estimated_output,
                    'pool_price': price_usd,
                    'value_usd': value_usd,
                    'has_price': True
                }
            else:
                # 沒有價格信息，根據流動性反推
                liquidity_usd = liquidity_info['liquidity_usd']
                
                # 假設你的代幣占池子的某個比例
                # 這是非常粗略的估算
                estimated_value = (balance * liquidity_usd) / max(balance, 1)
                
                return {
                    'estimated_output': 0,
                    'pool_price': 0,
                    'value_usd': 0,
                    'has_price': False
                }
                
        except Exception as e:
            logger.debug(f"⚠️  估算 swap 值失敗: {str(e)}")
            return {
                'estimated_output': 0,
                'pool_price': 0,
                'value_usd': 0,
                'has_price': False
            }

# ==================== 主要業務邏輯 ====================
class SpecificTokenMonitor:
    """特定代幣監控和販售"""
    def __init__(self):
        self.config = Config()
        self.w3_manager = Web3Manager(self.config)
        self.liquidity_checker = LiquidityChecker(self.config)
        self.swap_executor = SwapExecutor(chain_id=self.config.chain_id)
        self.last_check_time = 0
        self.has_liquidity_detected = False
        
        # 流動性追踪
        self.initial_liquidity = 0  # 首次檢測到的流動性
        self.current_liquidity = 0  # 當前流動性
        self.max_liquidity_seen = 0  # 見過的最高流動性
        self.liquidity_check_count = 0  # 檢查次數
        
        logger.info(f"🤖 特定代幣監控初始化完成")
        logger.info(f"   - 錢包: {self.w3_manager.address}")
        logger.info(f"   - 目標代幣: {self.config.TARGET_TOKEN}")
        logger.info(f"   - 最小流動性: ${self.config.min_liquidity_usd}")
    
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
    
    async def check_and_sell(self):
        """檢查流動性並販售"""
        try:
            # 1. 檢查錢包中是否有此代幣
            balance = self.w3_manager.get_balance(self.config.TARGET_TOKEN)
            
            if balance <= 0:
                log_debug(f"   ⚠️ 錢包中沒有此代幣")
                return
            
            logger.info(f"💰 檢測到錢包中有代幣: {balance:.6f}")
            
            # 2. 檢查流動性
            liquidity_info = await self.liquidity_checker.check_liquidity(self.config.TARGET_TOKEN)
            
            if not self.liquidity_checker.is_tradeable(liquidity_info):
                if not self.has_liquidity_detected:
                    log_debug(f"   ⏳ 流動性不足: ${liquidity_info['liquidity_usd']:.2f}")
                return
            
            # 3. 發現足夠的流動性！
            current_liquidity = liquidity_info['liquidity_usd']
            growth_ratio = 1.0  # 初始化
            
            if not self.has_liquidity_detected:
                # === 第一次發現流動性 ===
                self.has_liquidity_detected = True
                self.initial_liquidity = current_liquidity
                self.current_liquidity = current_liquidity
                self.max_liquidity_seen = current_liquidity
                self.liquidity_check_count = 1
                
                logger.info(f"\n{'='*60}")
                logger.info(f"🎉 發現足夠的流動性！")
                logger.info(f"{'='*60}\n")
                logger.info(f"   ✅ 初始流動性: ${current_liquidity:,.2f}")
                logger.info(f"   📊 DEX: {liquidity_info.get('dex', 'N/A')}")
                logger.info(f"   💎 你持有: {balance:.6f} 個代幣")
                
                # 播放一次提示音
                play_alert_sound('liquidity_found')
                
                # 判斷：是否需要等待流動性增長？
                if self.config.liquidity_growth_threshold > 1.0:
                    # TRUE: 需要等待增長
                    logger.info(f"   ⏳ 設定需要 {self.config.liquidity_growth_threshold}x 增長，記錄池子並繼續監控...")
                    return
                else:
                    # FALSE: 閾值 <= 1.0，直接進行交換
                    logger.info(f"   🚀 設定直接交換（無需等待增長），開始銷售！")
                    # 不 return，繼續執行下面的交換邏輯
            else:
                # === 已發現流動性，持續監控 ===
                self.liquidity_check_count += 1
                self.current_liquidity = current_liquidity
                if current_liquidity > self.max_liquidity_seen:
                    self.max_liquidity_seen = current_liquidity
                
                growth_ratio = current_liquidity / self.initial_liquidity if self.initial_liquidity > 0 else 0
                
                log_debug(f"   📊 流動性檢查 #{self.liquidity_check_count}: {growth_ratio:.2f}x")
                
                # 檢查是否達到增長目標
                if growth_ratio < self.config.liquidity_growth_threshold:
                    # 尚未達到，顯示實時信息並繼續監控
                    swap_estimate = await self.liquidity_checker.estimate_swap_value(
                        self.config.TARGET_TOKEN, 
                        balance, 
                        liquidity_info
                    )
                    
                    logger.info(f"\n   💎 當前持有: {balance:.6f} 個代幣")
                    if swap_estimate['has_price']:
                        logger.info(f"   📈 LP 價格: ${swap_estimate['pool_price']:,.2f}/個")
                        logger.info(f"   💰 持有價值: ${swap_estimate['value_usd']:,.2f}")
                    
                    log_debug(f"   ⏳ 池子增長中: {growth_ratio:.2f}x / {self.config.liquidity_growth_threshold}x")
                    return
                else:
                    # 達到增長目標，準備交換
                    logger.info(f"\n   ✅ 池子已增長到 {growth_ratio:.2f}x，開始銷售！")
            
            # ========== 執行交換部分 ==========
            logger.info(f"\n{'='*60}")
            logger.info(f"🚀 開始販售...")
            logger.info(f"{'='*60}\n")
            
            # 播放交換開始的提示音（如果需要）
            if self.liquidity_check_count > 2:  # 只在等待後的交換才播放
                play_alert_sound('liquidity_growth_complete')
            
            total_supply = self.liquidity_checker.get_token_total_supply(self.config.TARGET_TOKEN)
            if total_supply <= 0:
                logger.warning(f"   ⚠️ 無法獲取總供應量")
                return
            
            # 估算池子中的代幣數量（假設池子 50% 是該代幣）
            # 這是近似值，實際需要從 LP 合約查詢
            pool_token_ratio = 0.05  # 保守估計 5%（這是個粗略估計）
            
            logger.info(f"   📊 代幣總供應量: {total_supply:,.0f}")
            logger.info(f"   💧 流動性: ${current_liquidity:,.2f}")
            logger.info(f"   💎 你持有: {balance:.6f} 個代幣")
            logger.info(f"   ⚠️  警告: 這是估算值，實際比例可能不同")
            
            # 7. 執行販售
            logger.info(f"\n🚀 開始販售...")
            logger.info(f"   數量: {balance:.6f}")
            logger.info(f"   流動性倍數: {growth_ratio:.2f}x")
            
            native_token = self._get_wrapped_native_token()
            
            # 直接獲取精確的 wei 餘額，避免浮點數精度損失
            amount_wei = self.w3_manager.get_balance_wei(self.config.TARGET_TOKEN)
            
            if amount_wei <= 0:
                logger.warning(f"   ⚠️ 無法獲取精確的餘額 wei")
                return
            
            # 調用 SwapExecutor 執行交換
            tx_hash = await self.swap_executor.execute_swap(
                token_in=self.config.TARGET_TOKEN,
                token_out=native_token,
                amount_in=amount_wei
            )
            
            if tx_hash:
                logger.info(f"🔄 開始執行交換")
                logger.info(f"   ✅ 交易已發送: {tx_hash}")
            else:
                logger.warning(f"   ⚠️ 販售失敗")
                
        except Exception as e:
            logger.error(f"❌ 檢查並販售失敗: {str(e)}", exc_info=True)
    
    async def monitor_loop(self):
        """主監控迴圈"""
        logger.info("📡 啟動特定代幣監控...")
        check_interval = CHECK_INTERVAL
        heartbeat_interval = HEARTBEAT_INTERVAL
        last_heartbeat = 0
        
        while True:
            try:
                current_time = time.time()
                
                # 執行檢查
                await self.check_and_sell()
                
                # 心跳
                if current_time - last_heartbeat >= heartbeat_interval:
                    if self.has_liquidity_detected:
                        logger.info(f"💓 監控運行中... (已發現流動性)")
                    else:
                        logger.info(f"💓 監控運行中... (等待流動性)")
                    last_heartbeat = current_time
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"❌ 監控出錯: {str(e)}")
                await asyncio.sleep(5)

# ==================== 主程序 ====================
async def main():
    monitor = SpecificTokenMonitor()
    await monitor.monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())
