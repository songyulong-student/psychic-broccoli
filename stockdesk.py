import os
import json
import requests
import yfinance as yf
from datetime import datetime
import zoneinfo

# 🔒 专属密码
BOT_TOKEN = "9238442861:AAFKdxsbDK-FYaqNRNcXCoFVO2NVVkGiW98"
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
    
    # 1. 获取大盘基准 (SPY) 与 宏观数据
    try:
        spy_df = yf.Ticker("SPY").history(period="1mo")
        spy_ret20 = (float(spy_df["Close"].iloc[-1]) / float(spy_df["Close"].iloc[0])) - 1
        spy_price = round(float(spy_df["Close"].iloc[-1]), 2)
    except:
        spy_ret20 = 0
        spy_price = "N/A"

    tickers = {"NVDA": "NVDA", "VIX": "^VIX", "BRENT": "BZ=F"}
    snap = {}
    for key, ticker in tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if not hist.empty: snap[key] = round(float(hist["Close"].iloc[-1]), 2)
        except: snap[key] = None

    # 2. 宏观否决系统
    vetoes = []
    if snap.get("NVDA") and snap["NVDA"] < 181.46: vetoes.append("NVDA跌破181.46 (AI情绪崩溃)")
    if snap.get("BRENT") and snap["BRENT"] > 101: vetoes.append("布伦特原油>101 (地缘风险)")
    if snap.get("VIX") and snap["VIX"] > 28: vetoes.append("VIX>28 (极度恐慌)")

    # 3. 高级选股池 (科技高弹性 + 资源矿产)
    candidates = ["AMD", "MU", "TSLA", "PLTR", "AVGO", "SMCI", "MP", "FCX", "ALB", "XOM"]
    valid_cards = []
    
    for sym in candidates:
        try:
            df = yf.Ticker(sym).history(period="1mo")
            if len(df) < 20: continue
            
            price = float(df["Close"].iloc[-1])
            ema20 = float(df["Close"].ewm(span=20).mean().iloc[-1])
            vol_ratio = float(df["Volume"].iloc[-1] / df["Volume"].tail(20).mean())
            
            # 相对强弱 (RS) = 个股涨幅 - 大盘涨幅
            stock_ret20 = (price / float(df["Close"].iloc[0])) - 1
            rs_score = stock_ret20 - spy_ret20
            
            # 核心过滤：必须在均线上方，且强于大盘
            if price > ema20 and rs_score > 0:
                stop = round(price * 0.97, 2) # 3% 止损
                target = round(price * 1.06, 2) # 6% 止盈 (1:2盈亏比)
                shares = int(250 / (price - stop)) if price > stop else 0
                
                if shares > 0:
                    # 形态诊断
                    if vol_ratio > 1.5:
                        action = "🔥 <b>放量突破</b> (可顺势买)"
                    elif price < ema20 * 1.02:
                        action = "🎯 <b>精准回踩</b> (盈亏比极佳)"
                    else:
                        action = "📈 <b>强势延续</b> (找分时低点)"
                    
                    valid_cards.append({
                        "symbol": sym, "price": price, "stop": stop, 
                        "target": target, "shares": shares, 
                        "rs": round(rs_score * 100, 2), "action": action,
                        "vol": round(vol_ratio, 2)
                    })
        except:
            pass

    # 按强弱排序，只取前3名
    valid_cards.sort(key=lambda x: x["rs"], reverse=True)
    top_cards = valid_cards[:3]

    # 4. 组装终极战报
    msg = f"<b>📊 东京交易台 - 盘前狙击 (完全体)</b>\n时间: {now_jst}\n-------------------\n"
    msg += f"<b>宏观环境：</b>\n"
    msg += f"SPY: ${spy_price} (20日涨幅 {round(spy_ret20*100,2)}%)\n"
    msg += f"NVDA: ${snap.get('NVDA')} | VIX: {snap.get('VIX')} | 油: ${snap.get('BRENT')}\n\n"

    if vetoes:
        msg += f"<b>🚨 宏观否决触发：</b>\n"
        for v in vetoes: msg += f"❌ {v}\n"
        msg += "⚠️ <i>规则：今日禁止开新仓，只准减仓或空仓！</i>\n\n"
    else:
        msg += f"✅ <b>宏观状态健康，开启猎人模式</b>\n\n"

    if top_cards:
        msg += f"<b>🎯 发现猎物 (单笔风控 $250)：</b>\n"
        for c in top_cards:
            msg += f"👉 <b>{c['symbol']}</b> (强于大盘 <b>{c['rs']}%</b>, 量比 {c['vol']})\n"
            msg += f"策略：{c['action']}\n"
            msg += f"参考入场: ${c['price']} | 🛑 止损: ${c['stop']}\n"
            msg += f"🎯 目标: ${c['target']} | 📦 建议买入: {c['shares']} 股\n"
            msg += f"-------------------\n"
    else:
        msg += "今日没有股票同时满足“强于大盘”且“形态突破”。\n<b>空仓也是一种仓位，绝不强行交易！</b>\n"

    msg += "\n<i>系统提供计算卡片，扣动扳机需由你人工确认。</i>"
    
    send_tg(msg)
    print("扫描完成。")

if __name__ == "__main__":
    scan_market()
