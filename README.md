# 🤖 Web3 自動交易機器人

一個功能強大的去中心化交易自動化工具，支援多鏈自動交換和流動性狙擊功能。

## ✨ 核心功能

### 🔄 **auto_swap.py** - 自動換幣
自動監控您的錢包，當接收到新資產時立即尋找流動性池並自動售出。

**應用場景：**
- 📦 收到空投代幣時自動賣出
- 🎯 自動將不需要的資產換成 Gas Token (ETH/BNB/MATIC 等)
- ⚡ 實時監控，快速反應市場機會

**主要特性：**
- ✅ WebSocket + 輪詢混合監聽（低延遲）
- ✅ 多層安全檢查和風險控制
- ✅ 支援多個聚合器（1inch、0x、Uniswap、OKX）
- ✅ 自動滑點控制和 Gas 費用優化
- ✅ 詳細的交易日誌和錯誤追蹤

### 🎯 **sniper_sell.py** - 流動性狙擊
監控指定的代幣合約，一旦流動性池上線立即自動售出。

**應用場景：**
- 🚀 項目方剛上線時立即套現
- 💰 早期投資者抄底後自動賣出
- 📈 流動性觸發後自動交易

**主要特性：**
- ✅ 實時監控特定代幣的流動性狀態
- ✅ 自訂流動性增長觸發閾值
- ✅ 防止虛假流動性欺騙
- ✅ 池子代幣占比檢查
- ✅ 自動化販售流程

## 🔗 支援的區塊鏈

| 鏈名稱 | Chain ID | Gas Token |
|--------|----------|-----------|
| Ethereum | 1 | ETH |
| Binance Smart Chain | 56 | BNB |
| Polygon | 137 | MATIC |
| Base | 8453 | ETH |

## 🚀 快速開始

### 1️⃣ 安裝依賴

```bash
# 創建虛擬環境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

# 安裝套件
pip install -r requirements.txt
```

### 2️⃣ 配置環境變量

複製並編輯 `.env` 文件：

```bash
# .env
PRIVATE_KEY=your_private_key_here
RPC_URL=https://rpc.mainnet.com
WS_RPC_URL=wss://rpc.mainnet.com  # 可選，用於 WebSocket 監聽

# API Keys（可選）
INCH_API_KEY=your_1inch_api_key
OX_API_KEY=your_0x_api_key
```

⚠️ **重要：** 絕對不要將 `.env` 提交到 Git！

### 3️⃣ 運行程式

**運行自動換幣模式：**
```bash
python3 auto_swap.py
```

**運行流動性狙擊模式：**
```bash
# 先編輯 sniper_sell.py，設置目標代幣地址
TARGET_TOKEN = "0x..."  # 在 sniper_sell.py 第 27 行修改

python3 sniper_sell.py
```

## ⚙️ 配置說明

所有可配置的參數位於 `config.py`：

### 交易參數
```python
SWAP_SLIPPAGE = 5.0           # Swap 滑點容忍度 (%)
MIN_LIQUIDITY = 3000          # 最小流動性要求 (USD)
GAS_MULTIPLIER = 1.2          # Gas 倍數（加速交易）
MIN_SELL_AMOUNT = 10          # 最小賣出金額 (USD)
```

### 安全配置
```python
SAFE_MODE = True              # 啟用所有安全檢查
MAX_GAS_PRICE = 500           # Gas 價格上限 (gwei)
MAX_SLIPPAGE = 5.0            # 最大滑點容忍度 (%)
MONITOR_INTERVAL = 10         # 監控間隔 (秒)
```

### 功能開關
```python
ENABLE_WEBSOCKET = True       # 使用 WebSocket 監聽
ENABLE_LIQUIDITY_CHECK = True # 流動性檢查
ENABLE_AUTO_SWAP = True       # 自動交換功能
```

## 📋 必要文件

```
1027-autosell/
├── auto_swap.py              # 🔄 自動換幣主程式
├── sniper_sell.py            # 🎯 流動性狙擊主程式
├── swap_executor.py          # 交易執行核心
├── config.py                 # 配置文件
├── requirements.txt          # 依賴列表
├── .env                      # 環境變量（勿提交到 Git）
├── .gitignore               # Git 忽略列表
├── aggregators/             # DEX 聚合器
│   ├── __init__.py
│   ├── base.py
│   ├── oneinch.py
│   ├── okx.py
│   └── ...
└── test_swap.py             # 測試文件
```

## 🔐 安全建議

1. **保護私鑰**
   - 在 `.env` 文件中管理，永遠不要硬編碼
   - 不要將 `.env` 提交到版本控制系統
   - 定期更換私鑰

2. **資金安全**
   - 先用小額測試
   - 啟用 `SAFE_MODE` 進行完整檢查
   - 設置合理的 `MAX_GAS_PRICE` 和 `MAX_SLIPPAGE`

3. **監控日誌**
   - 定期查看交易日誌
   - 設置 `LOG_DEBUG = True` 進行詳細診斷
   - 保存交易記錄用於審計

## 🛠️ 常見問題

### Q: 如何更改監控的鏈？
A: 在 `config.py` 中修改 `RPC_URL` 和 `WS_RPC_URL`，並確保 `CHAIN_ID` 正確。

### Q: WebSocket 連接失敗怎麼辦？
A: 程式會自動降級為輪詢模式。檢查 `WS_RPC_URL` 是否正確配置。

### Q: 如何只運行某個特定鏈上的交易？
A: 在 `config.py` 中設置 `ENABLE_WEBSOCKET = False` 並手動指定 RPC URL。

### Q: 最小流動性多少才安全？
A: 建議至少 $3000 USD。設置在 `config.py` 的 `MIN_LIQUIDITY` 參數。

## 📊 支援的 DEX 聚合器

- **1inch** - 流動性最佳，支援大多數鏈
- **0x** - 快速報價和執行
- **Uniswap** - 廣泛的流動性支援
- **OKX** - 多鏈支援和不錯的費用結構

## 📝 日誌輸出

程式輸出兩種模式：

**詳細模式** (`LOG_DEBUG = True`)：
```
2024-10-29 14:35:42 - auto_swap - DEBUG - 檢查新代幣...
2024-10-29 14:35:43 - auto_swap - INFO - ✅ 找到交易機會
```

**簡約模式** (`LOG_DEBUG = False`)：
```
✅ 交易成功: 100 TOKEN → 1.5 BNB (Gas: 0.002 BNB)
❌ 交易失敗: 滑點過高 5.2% > 5%
```

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## ⚖️ 免責聲明

本項目用於教育和研究目的。使用者自行承擔所有風險，包括但不限於：
- 資金損失
- 交易失敗
- 市場風險

**使用前請充分了解區塊鏈和 DeFi 的風險。**

## 📄 License

MIT License

---

**最後更新：** 2025-10-29  
**版本：** 1.0.0
