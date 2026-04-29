# 📈 Discord 擬似トレードBot

AIが最新ニュース・市場動向を分析して、10分ごとに自動でBUY/SELLを判断する擬似トレードDiscord Botです。

## 機能一覧

### スラッシュコマンド

| コマンド | 説明 |
|---|---|
| `/trade [amount]` | 指定金額(円)でAI分析トレードを手動実行 |
| `/sell <ticker> [ratio]` | 保有株を売却（オートコンプリート対応） |
| `/portfolio` | ポートフォリオを円グラフ付きで表示 |
| `/history` | 直近10件のトレード履歴を表示 |
| `/status` | Botの稼働状況・次回トレード時刻を確認 |

### 自動トレード

- **20分ごと**にAIが自動でBUY/SELL/HOLDを判断して実行
- トレード結果 → ポートフォリオ円グラフの順にチャンネルへ自動投稿
- 保有銘柄の評価損益をAIに渡して売り判断も行う（SELL → BUY の順に実行）

### その他

- Gemini または Claude API によるWebニュース収集・銘柄分析
- yfinance で日本株・米国株の株価取得（日本株は `.T` suffix）
- USD→JPY 自動換算
- SQLite でポートフォリオ・トレード履歴を永続化
- 円グラフ（matplotlib）でポートフォリオを視覚化

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
   - BOT PERMISSIONS: `Send Messages`, `Embed Links`, `Read Message History`, `Attach Files`
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
| Health Check Path | `/` |

5. **Environment Variables** で以下を追加：

```
DISCORD_TOKEN        = <BotのTOKEN>
TRADE_CHANNEL_ID     = <チャンネルID>
GEMINI_API_KEY       = <GeminiのAPIキー>       # Gemini使用時
ANTHROPIC_API_KEY    = <ClaudeのAPIキー>        # Claude使用時
AI_PROVIDER          = gemini                   # "gemini" または "claude"
DAILY_TRADE_AMOUNT   = 10000                   # 1回あたりの自動トレード金額(円)
INITIAL_BALANCE      = 1000000                 # ポートフォリオ初期資金(円)
```

6. **Deploy** をクリック

> ⚠️ **Renderの無料プランについて**
> 無料プランは15分間アクセスがないとスリープします。
> `render_start.py` の簡易HTTPサーバーがヘルスチェックに応答しますが、
> 10分ごとの自動トレードを安定稼働させるには有料プラン（$7/月〜）を推奨します。

---

## 環境変数一覧

| 変数名 | 必須 | 説明 | デフォルト |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | Discord BotのTOKEN | - |
| `TRADE_CHANNEL_ID` | ✅ | 投稿先チャンネルID | - |
| `GEMINI_API_KEY` | ※1 | Gemini APIキー | - |
| `ANTHROPIC_API_KEY` | ※1 | Claude APIキー | - |
| `AI_PROVIDER` | | 使用するAI (`gemini` / `claude`) | `gemini` |
| `DAILY_TRADE_AMOUNT` | | 1回あたりの自動トレード金額(円) | `10000` |
| `INITIAL_BALANCE` | | 初期資金(円)・損益計算の基準 | `1000000` |

※1 `AI_PROVIDER` に合わせてどちらか一方を設定

---

## 資産額を変更したい場合

`INITIAL_BALANCE` は損益計算の基準値です。**すでにDBが作られている場合、環境変数を変えてもDBの現金残高は自動では変わりません。**

DBを直接更新してください：

```bash
# Render の Shell タブ、またはローカルで実行
sqlite3 data/portfolio.db "UPDATE portfolio SET cash_jpy = 500000 WHERE id=1;"
```

完全にリセットしたい場合は `data/portfolio.db` を削除してBot再起動。

---

## ディレクトリ構成

```
discord-trade-bot/
├── bot.py               # メインBot・スラッシュコマンド・スケジューラー
├── render_start.py      # Render用起動スクリプト（ヘルスチェックサーバー併設）
├── requirements.txt
├── .env.example
├── data/
│   └── portfolio.db     # SQLiteデータベース（自動生成）
└── src/
    ├── __init__.py
    ├── ai_analyzer.py   # AI分析（Gemini/Claude・BUY/SELL/HOLD判断）
    ├── chart.py         # ポートフォリオ円グラフ生成（matplotlib）
    ├── database.py      # DB操作（portfolio / holdings / trades）
    ├── embeds.py        # Discord Embedメッセージ整形
    ├── stock_fetcher.py # 株価取得・USD→JPY換算（yfinance）
    └── trader.py        # トレード実行ロジック（BUY / SELL）
```

---

## カスタマイズ

### 自動トレードの間隔を変える

`bot.py` の `IntervalTrigger` を編集：

```python
# 例: 30分ごと
IntervalTrigger(minutes=30, timezone=JST)

# 例: 1時間ごと
IntervalTrigger(hours=1, timezone=JST)

# 例: 毎日9時に1回（CronTriggerに戻す場合）
from apscheduler.triggers.cron import CronTrigger
CronTrigger(hour=9, minute=0, timezone=JST)
```

### AIプロンプトを変える

`src/ai_analyzer.py` の `build_prompt()` を編集。保有銘柄情報は自動でプロンプトに含まれます。

例：日本株のみに絞る、特定セクターに特化する、損益が-10%を超えたら必ず売却を指示するなど。

### トレード戦略を変える

`src/trader.py` の `run_ai_auto_trade()` を編集。SELL→BUYの順序変更や、売却比率のデフォルト値調整などが可能です。

---

## 注意事項

- これは**擬似（シミュレーション）トレード**です。実際の株式売買は行いません
- AIの分析結果は投資アドバイスではありません
- 株価データはyfinance経由で取得するため、リアルタイムではなく若干の遅延があります
- 20分ごとのAPI呼び出しはレート制限・コストに注意してください
