# 📈 Discord 擬似トレードBot

AIが最新ニュースを分析して毎日自動で擬似トレードを実行するDiscord Botです。

## 機能

| コマンド | 説明 |
|---|---|
| `/trade [amount]` | 指定金額(円)でAI分析トレードを実行 |
| `/portfolio` | ポートフォリオ・評価損益を表示 |
| `/history` | 直近10件のトレード履歴を表示 |
| `/status` | Botの稼働状況・次回トレード時刻を確認 |

- 毎日指定時刻にAIが自動でトレードを実行
- Gemini または Claude API によるニュース収集・銘柄分析
- yfinance で日本株・米国株のリアルタイム株価取得
- SQLite でポートフォリオ・履歴を永続化

---

## セットアップ手順

### 1. Discord Developer Portal でBotを作成

1. https://discord.com/developers/applications にアクセス
2. **New Application** → アプリ名を入力
3. 左メニュー **Bot** → **Add Bot**
4. **TOKEN** をコピー（後で使用）
5. **Privileged Gateway Intents** で以下を有効化：
   - `MESSAGE CONTENT INTENT`
6. 左メニュー **OAuth2 → URL Generator**
   - SCOPES: `bot`, `applications.commands` にチェック
   - BOT PERMISSIONS: `Send Messages`, `Embed Links`, `Read Message History`
   - 生成されたURLでBotをサーバーに招待

### 2. チャンネルIDの取得

1. Discord の設定 → 詳細設定 → **開発者モード** をON
2. トレード結果を投稿したいチャンネルを右クリック → **IDをコピー**

### 3. AI APIキーの取得

**Gemini（推奨・無料枠あり）:**
- https://aistudio.google.com/app/apikey でAPIキーを取得

**Claude:**
- https://console.anthropic.com でAPIキーを取得

### 4. ローカルで動作確認

```bash
# リポジトリをクローン
git clone <your-repo>
cd discord-trade-bot

# 依存関係インストール
pip install -r requirements.txt

# .env ファイルを作成
cp .env.example .env
# .env を編集して各キーを設定

# 起動
python bot.py
```

### 5. Renderにデプロイ

#### 5-1. GitHubにプッシュ

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin <your-github-repo>
git push -u origin main
```

#### 5-2. Renderでサービス作成

1. https://render.com にログイン
2. **New → Web Service**
3. GitHubリポジトリを接続
4. 以下の設定を入力：

| 項目 | 値 |
|---|---|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python render_start.py` |

5. **Environment Variables** で以下を追加：

```
DISCORD_TOKEN        = <BotのTOKEN>
TRADE_CHANNEL_ID     = <チャンネルID>
GEMINI_API_KEY       = <GeminiのAPIキー>
AI_PROVIDER          = gemini
DAILY_TRADE_AMOUNT   = 10000
DAILY_TRADE_HOUR     = 9
DAILY_TRADE_MINUTE   = 0
INITIAL_BALANCE      = 1000000
```

6. **Deploy** をクリック

> ⚠️ **Renderの無料プランについて**
> 無料プランは15分間アクセスがないとスリープします。
> `render_start.py` の簡易HTTPサーバーがヘルスチェックに応答するため、
> Renderの **Health Check Path** を `/` に設定してください。
> 継続稼働させたい場合は有料プラン（$7/月〜）を推奨します。

---

## ディレクトリ構成

```
discord-trade-bot/
├── bot.py              # メインBot・スラッシュコマンド定義
├── render_start.py     # Render用起動スクリプト
├── requirements.txt
├── .env.example
├── data/
│   └── portfolio.db    # SQLiteデータベース（自動生成）
└── src/
    ├── __init__.py
    ├── database.py     # DB操作
    ├── ai_analyzer.py  # AI分析（Gemini/Claude）
    ├── stock_fetcher.py # 株価取得（yfinance）
    ├── trader.py       # トレード実行ロジック
    └── embeds.py       # Discordメッセージ整形
```

---

## カスタマイズ

### AIプロンプトを変更する

`src/ai_analyzer.py` の `TRADE_PROMPT_TEMPLATE` を編集してください。

例：米国株のみに絞る、特定セクターに特化する、など。

### トレード戦略を変更する

`src/trader.py` の `run_ai_auto_trade()` を編集してください。

### 売却機能を追加する

`src/trader.py` に `execute_sell()` 関数を実装し、`bot.py` に `/sell` コマンドを追加してください。

---

## 注意事項

- これは**擬似（シミュレーション）トレード**です。実際の株式売買は行いません
- AI の分析結果は投資アドバイスではありません
- 株価データは yfinance 経由で取得するため、リアルタイムではなく若干の遅延があります
