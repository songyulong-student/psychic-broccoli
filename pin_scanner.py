import os
import requests
import yfinance as yf
import pandas as pd
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

def scan_pinbars():
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    try:
        qqq_pre = yf.Ticker("QQQ").history(period="1d", interval="1m", prepost=True)
        qqq_change = (qqq_pre["Close"].iloc[-1] / qqq_pre["Close"].iloc[0]) - 1 if not qqq_pre.empty else 0
    except:
        qqq_change = 0

    msg = f"<b>🪡 华尔街插针预测敢死队 (盘前激进版)</b>\n"
    msg += f"时间: {now_jst} | 纳指盘前: {round(qqq_change*100, 2)}%\n"
    msg += f"-------------------\n"
    
    targets = {
        "SNDK": "闪迪", "BE": "Bloom Energy", "AVGO": "博通", 
        "MU": "美光", "NVDA": "英伟达", "AXTI": "AXT Inc"
    }
    
    for sym, name in targets.items():
        try:
            df_daily = yf.Ticker(sym).history(period="3mo")
            if len(df_daily) < 20: continue
            
            prev_close = float(df_daily["Close"].iloc[-1])
            prev_low = float(df_daily["Low"].iloc[-1])
            
            tr = pd.concat([
                df_daily["High"] - df_daily["Low"], 
                (df_daily["High"] - df_daily["Close"].shift()).abs(), 
                (df_daily["Low"] - df_daily["Close"].shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]

            df_pre = yf.Ticker(sym).history(period="1d", interval="1m", prepost=True)
            if not df_pre.empty:
                pre_price = float(df_pre["Close"].iloc[-1])
                pre_low = float(df_pre["Low"].min())
            else:
                pre_price, pre_low = prev_close, prev_close

            pre_change = (pre_price / prev_close) - 1
            predicted_low = min(pre_low, prev_low) - (atr * 0.2)
            
            if pre_change > 0.02: 
                predicted_low = max(prev_low, pre_price - (atr * 0.8))
                prob_A, prob_B, prob_C = 65, 25, 10
                analysis = f"盘前大涨 {round(pre_change*100,1)}%，极易高开低走。机构借高开出货，向下扫止损。"
            elif pre_change < -0.02:
                predicted_low = pre_price - (atr * 0.5)
                prob_A, prob_B, prob_C = 45, 40, 15
                analysis = f"盘前重挫 {round(pre_change*100,1)}%，开盘易引发恐慌抛售，极大概率砸出深坑后收回。"
            else:
                prob_A, prob_B, prob_C = 50, 30, 20
                analysis = f"盘前震荡，多空博弈激烈。大概率回踩前日低点或盘前低点洗盘。"

            if qqq_change < -0.01 and pre_change > 0:
                prob_A += 10
                prob_B -= 10
                analysis += " 纳指盘前走弱，个股高开易被带崩。"

            predicted_low = round(predicted_low, 2)
            entry_price = round(predicted_low * 1.005, 2) 
            stop_loss = round(predicted_low * 0.98, 2)    
            risk_per_share = entry_price - stop_loss
            
            shares = int(250 / risk_per_share) if risk_per_share > 0 else 0

            msg += f"🔍 <b>{sym}</b> ({name})\n"
            msg += f"昨收: ${round(prev_close, 2)} | 盘前现价: ${round(pre_price, 2)}\n"
            msg += f"预测盘中最低价 (插针区): <b>${predicted_low}</b>\n"
            msg += f"概率: A(深V收回) <b>{prob_A}%</b> | B(阴跌) {prob_B}% | C(高走) {prob_C}%\n"
            msg += f"💡 <b>逻辑:</b> {analysis}\n"
            
            if shares > 0:
                msg += f"👉 激进接针价: <b>${entry_price}</b> | 🛑 止损: ${stop_loss}\n"
                msg += f"📦 建议股数: {shares} 股 (风控$250)\n"
            msg += f"-------------------\n"
        except: pass

    msg += "⚠️ <i>务必使用限价单接针。跌破预测低点2%坚决止损！</i>"
    send_tg(msg)

if __name__ == "__main__":
    scan_pinbars()
