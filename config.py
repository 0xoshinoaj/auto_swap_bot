"""
配置文件 - 將所有可配置的常量集中管理
隱私信息（私鑰、RPC URL、API Key）在 .env 中配置
"""

# ==================== 區塊鏈配置 ====================
# 鏈 ID 和對應信息
CHAIN_ID_MAPPING = {
    1: {"name": "Ethereum", "symbol": "ETH"},
    56: {"name": "BSC", "symbol": "BNB"},
    137: {"name": "Polygon", "symbol": "MATIC"},
    8453: {"name": "Base", "symbol": "ETH"},
}

# ==================== 交易參數 ====================
# Swap 滑點容忍度 (%) - 用於 0x Protocol 報價
SWAP_SLIPPAGE = 5.0

# 最小流動性要求 (USD)
MIN_LIQUIDITY = 3000

# Gas 倍數 (加速交易)
GAS_MULTIPLIER = 1.2

# 最小賣出金額 (USD)
MIN_SELL_AMOUNT = 10

# ==================== 安全配置 ====================
# 安全模式（true=啟用所有檢查，false=快速但風險高）
SAFE_MODE = True

# Gas 價格上限 (gwei)
MAX_GAS_PRICE = 500

# 最大滑點容忍度 (%)
MAX_SLIPPAGE = 5.0

# 監控間隔 (秒)
MONITOR_INTERVAL = 10

# ==================== 日誌設定 ====================
# 日誌級別：
# - True: 詳細模式，顯示所有信息包括調試信息（適合開發測試）
# - False: 簡約模式，只顯示重要結果（綠色勾和錯誤）
LOG_DEBUG = False  # 改為 True 查看詳細日誌

# ==================== 重複檢測冷卻 ====================
# 同一代幣在多少個區塊內不會被重複檢測
# 用於防止代幣因多個 Transfer 事件在短時間內被重複處理
# 
# 各鏈區塊時間參考：
# - Ethereum: ~12 秒/區塊 (100 區塊 ≈ 20 分鐘)
# - BSC: ~3 秒/區塊 (100 區塊 ≈ 5 分鐘)
# - Polygon: ~2.5 秒/區塊 (100 區塊 ≈ 4 分鐘)
# - Base: ~2 秒/區塊 (100 區塊 ≈ 3 分鐘)
# - Arbitrum: ~0.25 秒/區塊 (1000 區塊 ≈ 4 分鐘)
DUPLICATE_CHECK_BLOCKS = 3  # 調整此值以改變冷卻期長度

# ==================== 穩定幣配置 ====================
# 已廢棄 - 現在直接交換成 Gas Token (WETH/WBNB 等)
# 不再需要穩定幣中間層

# ==================== Wrapped 原生幣地址 ====================
# 不同鏈上的 Wrapped Native Token (WETH/WBNB/etc)
WRAPPED_NATIVE_TOKENS = {
    1: "0xC02aaA39b223FE8D0A0e8e4F27ead9083C756Cc2",      # WETH on Ethereum
    56: "0xbb4CdB9CBd36B01bD1cbaEBF2De08d9173bc095c",     # WBNB on BSC
    137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",    # WMATIC on Polygon
    8453: "0x4200000000000000000000000000000000000006",    # WETH on Base
}

# ==================== 日誌配置 ====================
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ==================== 聚合器優先級 ====================
# 嘗試聚合器的順序
AGGREGATOR_PRIORITY = ["1inch", "0x", "uniswap", "okx"]

# ==================== 超時配置 ====================
API_TIMEOUT = 15  # 秒
BLOCK_SCAN_TIMEOUT = 30  # 秒

# ==================== DexScreener API 配置 ====================
DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/tokens"
DEXSCREENER_TIMEOUT = 10  # 秒

# ==================== 聚合器端點 ====================
AGGREGATOR_ENDPOINTS = {
    '1inch': {
        'base_url': 'https://api.1inch.dev/v5.2',
        'supports_chains': [1, 56, 137, 8453, 43114, 250],
    },
    '0x': {
        'base_url': 'https://api.0x.org/swap/allowance-holder',
        'supports_chains': [1, 56, 137, 8453, 42161, 10],
    },
    'uniswap': {
        'base_url': 'https://api.uniswap.org/v1',
        'supports_chains': [1, 56, 137, 43114, 250, 8453],
    },
    'okx': {
        'base_url': 'https://web3.okx.com/api/v6/dex',
        'supports_chains': [1, 56, 137, 43114, 250, 8453],
    },
}

# ==================== 白名單/黑名單默認值 ====================
# 默認白名單代幣（空=允許所有）
DEFAULT_WHITELIST_TOKENS = []

# 默認黑名單代幣（已知騙局代幣等）
DEFAULT_BLACKLIST_TOKENS = [
    "0x0000000000000000000000000000000000000000",  # 零地址
]

# ==================== 功能開關 ====================
# 是否啟用 WebSocket 監聽
# 注意：需在 .env 中設置 WS_RPC_URL
# 如果 WS_RPC_URL 未配置或 WebSocket 不可用，將自動降級為輪詢模式
# - True: 使用 WebSocket 實時監聽（需要 WS_RPC_URL）
# - False: 使用輪詢方式監聽
ENABLE_WEBSOCKET = True

# 是否啟用 DexScreener 流動性檢查
ENABLE_LIQUIDITY_CHECK = True

# 是否啟用自動交換（false=僅監聽不交換）
ENABLE_AUTO_SWAP = True

# ==================== 重試配置 ====================
# 最大重試次數
MAX_RETRIES = 5

# 重試間隔 (秒)
RETRY_INTERVAL = 5

# 監控失敗後的休息時間 (秒)
MONITOR_FAILURE_SLEEP = 10

# ==================== 交易確認配置 ====================
# 最多等待確認的時間 (秒)
TX_CONFIRMATION_TIMEOUT = 300

# 確認塊數
TX_CONFIRMATION_BLOCKS = 1
