from datetime import datetime


def update_dashboard(
    code,
    result,
    stock_label,
    updated_label,
    price_label,
    change_label,
    rsi_label,
    macd_label,
    band_label,
    decision_label,
):
    lines = result.splitlines()

    # 銘柄・更新時刻
    stock_label.config(text=f"銘柄: {code}")
    updated_label.config(
        text=f"最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # 現在価格
    price = next(
        (line for line in lines if "今日:" in line),
        "価格: --"
    )
    price_label.config(text=price)

    # 前日比
    change = next(
        (line for line in lines if line.startswith("前日比:")),
        "前日比: --"
    )

    if "+" in change:
        change_label.config(text=change, fg="green")
    elif "-" in change:
        change_label.config(text=change, fg="red")
    else:
        change_label.config(text=change, fg="black")

    # RSI
    rsi = next(
        (line for line in lines if line.startswith("RSI:")),
        "RSI: --"
    )

    if "買われすぎ" in result:
        rsi_label.config(text=rsi, fg="red")
    elif "売られすぎ" in result:
        rsi_label.config(text=rsi, fg="green")
    else:
        rsi_label.config(text=rsi, fg="#66ccff")

    # MACD
    macd = next(
        (line for line in lines if line.startswith("MACD:")),
        "MACD: --"
    )

    if "MACD: 上向き" in result:
        macd_label.config(text=macd, fg="green")
    else:
        macd_label.config(text=macd, fg="red")

    # ボリンジャーバンド
    band = next(
        (line for line in lines if line.startswith("ボリンジャー")),
        "ボリンジャー: --"
    )

    if "高め" in band:
        band_label.config(text=band, fg="red")
    elif "安め" in band:
        band_label.config(text=band, fg="green")
    else:
        band_label.config(text=band, fg="#66ccff")
    # 総合判定
    decision = next(
        (line for line in lines if line.startswith("総合判定")),
        "総合判定: --"
    )

    if "買い" in decision:
        decision_label.config(text=decision, fg="#00ff66")
    elif "売り" in decision:
        decision_label.config(text=decision, fg="#ff5555")
    else:
        decision_label.config(text=decision, fg="#ffd700")