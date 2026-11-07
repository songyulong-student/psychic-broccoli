import os
import json
import requests
import yfinance as yf
from datetime import datetime
import zoneinfo

# 🔒 专属密码
BOT_TOKEN = "9238442861:AAFKdxsbDK-FYaqNRNcXCoFV02NVVkGiW98"
CHAT_ID = "6863511869"

JST = zoneinfo.ZoneInfo("Asia/Tokyo")

def send_tg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"发送失败: {e}")

def scan_market():
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    tickers = {"NVDA": "NVDA", "BRENT": "BZ=F", "VIX": "^VIX", "SPY": "SPY"}
    snap = {}
    for key, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty:
                snap[key] = round(float(hist["Close"].iloc[-1]), 2)
        except:
            snap[key] = None

    vetoes = []
    if snap.get("NVDA") and snap["NVDA"] < 181.46:
        vetoes.append("NVDA跌破181.46 (AI情绪崩溃)")
    if snap.get("BRENT") and snap["BRENT"] > 101:
        vetoes.append("布伦特原油>101 (地缘风险)")
    if snap.get("VIX") and snap["VIX"] > 28:
        vetoes.append("VIX>28 (市场恐慌)")

    candidates = ["AMD", "MU", "TSLA", "PLTR", "AVGO", "SMCI"]
    valid_cards = []
    
    for sym in candidates:
        try:
            df = yf.Ticker(sym).history(period="1mo")
            if len(df) < 20: continue
            price = float(df["Close"].iloc[-1])
            ema20 = float(df["Close"].ewm(span=20).mean().iloc[-1])
            vol_ratio = float(df["Volume"].iloc[-1] / df["Volume"].tail(20).mean())
            
            if price > ema20 and vol_ratio > 1.2:
                stop = round(price * 0.97, 2)
                target = round(price * 1.06, 2)
                shares = int(250 / (price - stop)) if price > stop else 0
                
                if shares > 0:
                    valid_cards.append({
                        "symbol": sym, "price": price, "stop": stop, 
                        "target": target, "shares": shares, "score": 85
                    })
        except:
            pass

    msg = f"<b>📊 东京交易台 - 盘前扫描</b>\n"
    msg += f"时间: {now_jst}\n"
    msg += f"-------------------\n"
    msg += f"<b>市场温度：</b>\n"
    msg += f"NVDA: ${snap.get('NVDA')} | VIX: {snap.get('VIX')} | 油: ${snap.get('BRENT')}\n\n"

    if vetoes:
        msg += f"<b>🚨 宏观否决触发：</b>\n"
        for v in vetoes:
            msg += f"❌ {v}\n"
        msg += "⚠️ <i>规则：触发否决，今日禁止开新仓，只准减仓！</i>\n\n"
    else:
        msg += f"✅ <b>宏观状态正常，寻找机会</b>\n\n"

    if valid_cards:
        msg += f"<b>🎯 今日交易候选（单笔上限$250）：</b>\n"
        for c in valid_cards[:2]:
            msg += f"👉 <b>{c['symbol']}</b> (评分{c['score']})\n"
            msg += f"参考入场: ${c['price']}\n"
            msg += f"🛑 止损: ${c['stop']}\n"
            msg += f"🎯 目标1: ${c['target']}\n"
            msg += f"📦 建议股数: {c['shares']} 股 (最大亏$250)\n"
            msg += f"-------------------\n"
    else:
        msg += "今日无符合形态的优质候选。\n<b>空仓也是一种仓位，按兵不动！</b>\n"

    msg += "\n<i>系统仅提供计算卡片，扣动扳机需由你人工确认。</i>"
    
    send_tg(msg)
    print("扫描完成。")

if __name__ == "__main__":
    scan_market()
