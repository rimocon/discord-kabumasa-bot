"""
chart.py - ポートフォリオの円グラフ画像を生成する
matplotlibで描画してDiscord用にBytesIOで返す
"""
import io
import asyncio
import math
import os
from typing import Optional

# matplotlibは重いので遅延インポート
def _make_chart(snapshot: dict) -> bytes:
    import matplotlib
    matplotlib.use("Agg")  # GUIなし
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import matplotlib.patches as mpatches
    from matplotlib import rcParams
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "fonts", "NotoSansCJKjp-Regular.otf")
    # 日本語フォント設定（Renderでは英語フォールバック）
    if os.path.exists(font_path):
        font_prop = fm.FontProperties(fname=font_path)
        rcParams["font.family"] = font_prop.get_name()
        print(f"Loaded font from: {font_path}")
    else:
        print(f"Warning: Font file not found! Expected path: {font_path}")

    cash               = snapshot["cash"]
    holdings           = snapshot["holdings"]
    valuations         = snapshot["valuations"]
    total_value        = snapshot["total_value"]
    total_gain_loss    = snapshot["total_gain_loss"]
    initial_balance    = snapshot["initial_balance"]
    total_market_value = snapshot["total_market_value"]

    # ---- データ構築 ----
    labels = []
    sizes  = []
    colors_list = []

    # 株式の配色パレット
    PALETTE = [
        "#4E79A7", "#F28E2B", "#E15759", "#76B7B2",
        "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7",
        "#9C755F", "#BAB0AC",
    ]

    for i, h in enumerate(holdings):
        v = valuations.get(h["ticker"], {})
        mv = v.get("market_value_jpy", h["avg_cost_jpy"] * h["shares"])
        if mv > 0:
            # tickerが長い場合は短縮
            label = h["company_name"]
            if len(label) > 8:
                label = label[:7] + "…"
            labels.append(label)
            sizes.append(mv)
            colors_list.append(PALETTE[i % len(PALETTE)])

    # 現金
    if cash > 0:
        labels.append("現金")
        sizes.append(cash)
        colors_list.append("#AAAAAA")

    if not sizes:
        # 資産がない場合は空のグラフ
        fig, ax = plt.subplots(figsize=(6, 4), facecolor="#2B2D31")
        ax.text(0.5, 0.5, "保有資産なし", ha="center", va="center",
                color="white", fontsize=16, transform=ax.transAxes)
        ax.axis("off")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return buf.getvalue()

    # ---- レイアウト: 左=円グラフ, 右=テキストサマリー ----
    fig = plt.figure(figsize=(11, 5.5), facecolor="#2B2D31")
    ax_pie  = fig.add_axes([0.02, 0.08, 0.48, 0.84])   # 円グラフ
    ax_text = fig.add_axes([0.52, 0.0,  0.46, 1.0])    # テキスト

    # ---- 円グラフ ----
    wedge_props = {"linewidth": 1.5, "edgecolor": "#2B2D31"}
    wedges, texts, autotexts = ax_pie.pie(
        sizes,
        labels=None,
        colors=colors_list,
        autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
        startangle=90,
        wedgeprops=wedge_props,
        pctdistance=0.78,
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(8)
        at.set_fontweight("bold")

    # 中心に総資産を表示（ドーナツ風）
    centre_circle = plt.Circle((0, 0), 0.55, fc="#2B2D31")
    ax_pie.add_patch(centre_circle)

    total_str = f"¥{total_value:,.0f}"
    ax_pie.text(0, 0.08, "総資産", ha="center", va="center",
                color="#AAAAAA", fontsize=9)
    ax_pie.text(0, -0.10, total_str, ha="center", va="center",
                color="white", fontsize=12, fontweight="bold")

    ax_pie.set_aspect("equal")

    # 凡例
    patches = [mpatches.Patch(color=c, label=l) for c, l in zip(colors_list, labels)]
    ax_pie.legend(handles=patches, loc="lower center", bbox_to_anchor=(0.5, -0.06),
                  ncol=3, fontsize=7.5, frameon=False,
                  labelcolor="white", facecolor="#2B2D31")

    # ---- テキストサマリー ----
    ax_text.axis("off")
    ax_text.set_facecolor("#2B2D31")

    gain_color = "#57F287" if total_gain_loss >= 0 else "#ED4245"
    gain_sign  = "+" if total_gain_loss >= 0 else ""
    overall_pct = ((total_value - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0

    summary_lines = [
        ("PORTFOLIO", "white", 14, "bold"),
        ("", "white", 4, "normal"),
        ("総資産",    "#AAAAAA", 8,  "normal"),
        (f"¥{total_value:,.0f}", "white", 15, "bold"),
        ("", "white", 6, "normal"),
        ("現金残高",    "#AAAAAA", 8, "normal"),
        (f"¥{cash:,.0f}", "white", 11, "normal"),
        ("", "white", 4, "normal"),
        ("株式評価額",  "#AAAAAA", 8, "normal"),
        (f"¥{total_market_value:,.0f}", "white", 11, "normal"),
        ("", "white", 6, "normal"),
        ("評価損益",   "#AAAAAA", 8, "normal"),
        (f"{gain_sign}¥{total_gain_loss:,.0f}  ({gain_sign}{overall_pct:.2f}%)",
         gain_color, 12, "bold"),
    ]

    y = 0.97
    for text, color, size, weight in summary_lines:
        ax_text.text(0.05, y, text, transform=ax_text.transAxes,
                     color=color, fontsize=size, fontweight=weight, va="top")
        # 行高さをフォントサイズに比例させる
        y -= (size / 220 + 0.005)

    # 保有銘柄テーブル
    y -= 0.03
    ax_text.text(0.05, y, "保有銘柄", transform=ax_text.transAxes,
                 color="#AAAAAA", fontsize=8, va="top")
    y -= 0.055

    for h in holdings:
        if y < 0.02:
            break
        v = valuations.get(h["ticker"], {})
        gl    = v.get("gain_loss_jpy", 0)
        gl_p  = v.get("gain_loss_pct", 0)
        mv    = v.get("market_value_jpy", 0)
        pct_of_total = (mv / total_value * 100) if total_value > 0 else 0
        c     = "#57F287" if gl >= 0 else "#ED4245"
        s     = "+" if gl >= 0 else ""
        name  = h["company_name"]
        if len(name) > 10:
            name = name[:9] + "…"
        line1 = f"{name} ({h['ticker']})"
        line2 = f"¥{mv:,.0f} ({pct_of_total:.1f}%)  {s}¥{gl:,.0f} ({s}{gl_p:.1f}%)"
        ax_text.text(0.05, y,     line1, transform=ax_text.transAxes,
                     color="white", fontsize=8, va="top")
        ax_text.text(0.05, y-0.04, line2, transform=ax_text.transAxes,
                     color=c, fontsize=7.5, va="top")
        y -= 0.095

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


async def generate_portfolio_chart(snapshot: dict) -> Optional[bytes]:
    """非同期ラッパー"""
    try:
        return await asyncio.to_thread(_make_chart, snapshot)
    except Exception as e:
        print(f"[Chart] グラフ生成エラー: {e}")
        return None
