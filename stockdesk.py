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

def scan_market():
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    
    # 获取纳指 (QQQ) 和标普 (SPY) 作为大盘基准
    try:
        qqq_df = yf.Ticker("QQQ").history(period="2mo")
        spy_df = yf.Ticker("SPY").history(period="2mo")
        
        qqq_ret_today = (qqq_df["Close"].iloc[-1] / qqq_df["Close"].iloc[-2]) - 1
        spy_ret20 = (spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[0]) - 1
    except Exception as e:
        print(f"获取大盘失败: {e}")
        qqq_ret_today, spy_ret20 = 0, 0

    # 四大金刚股票池
    universe = {
        "AMD": "半导体", "NVDA": "半导体", "MU": "半导体", "AVGO": "半导体", "ARM": "半导体",
        "VST": "电力", "CEG": "电力", "TLN": "电力", "GEV": "电力",
        "LLY": "医药", "NVO": "医药", "MRK": "医药", "VRTX": "医药",
        "RDDT": "新股", "PLTR": "新股", "ALAB": "新股", "COIN": "高弹性", "MSTR": "高弹性"
    }

    valid_cards = []
    
    for sym, sector in universe.items():
        try:
            # 拉取3个月数据以计算长期形态
            df = yf.Ticker(sym).history(period="3mo")
            if len(df) < 40: continue
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = last["Close"]
            
            ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
            vol_ma20 = df["Volume"].tail(20).mean()
            vol_ratio = last["Volume"] / vol_ma20
            
            # 计算个股今日涨跌幅与相对大盘强弱
            stock_ret_today = (last["Close"] / prev["Close"]) - 1
            rs_today = stock_ret_today - qqq_ret_today
            rs20 = (price / df["Close"].iloc[-20]) - 1 - spy_ret20
            
            # 计算 ATR 波动率 (用于动态止损)
            tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # === 核心形态识别 (Price Action) ===
            pattern = ""
            
            # 1. 识别长下影线 (深V / 机构托底)
            body = abs(last["Close"] - last["Open"])
            lower_shadow = min(last["Open"], last["Close"]) - last["Low"]
            is_deep_v = lower_shadow > body * 2 and lower_shadow > price * 0.02
            
            # 2. 识别洗盘 (大盘跌，它抗跌)
            is_shakeout = qqq_ret_today < -0.01 and rs_today > 0.01
            
            # 3. 识别放量突破 (突破前20天高点)
            recent_high = df["High"].tail(20).max()
            is_breakout = price > recent_high and vol_ratio > 1.5
            
            # 4. 识别死猫跳 (均线下方，缩量反弹，严禁做多)
            is_dead_cat = price < ema20 and stock_ret_today > 0 and vol_ratio < 0.8

            # === 交易逻辑生成 ===
            if not is_dead_cat and price > ema20 and rs20 > 0:
                if is_breakout:
                    pattern = "🔥 放量突破 (真突破)"
                elif is_shakeout:
                    pattern = "🧹 借纳指洗盘 (抗跌)"
                elif is_deep_v:
                    pattern = "🗡 深V探底 (长下影线)"
                elif vol_ratio < 0.8 and price <= ema20 * 1.02:
                    pattern = "🪶 缩量回踩 (极佳买点)"
                else:
                    pattern = "📈 趋势延续"
                
                stop = round(price - (1.5 * atr), 2)
                target = round(price + (1.5 * atr * 2), 2)
                shares = int(250 / (price - stop)) if price > stop else 0
                
                if shares > 0:
                    valid_cards.append({
                        "sym": sym, "sector": sector, "dir": "🟢 做多", "pattern": pattern,
                        "price": round(price,2), "stop": stop, "target": target, "shares": shares, "rs": round(rs20*100,1)
                    })
            
            # 做空逻辑 (死猫跳是做空的好机会，破位放量也是)
            elif (is_dead_cat and rs20 < 0) or (price < ema20 and is_breakout and stock_ret_today < 0):
                pattern = "💀 死猫跳诱多 (做空)" if is_dead_cat else "🩸 破位放量下杀"
                stop = round(price + (1.5 * atr), 2)
                target = round(price - (1.5 * atr * 2), 2)
                shares = int(250 / (stop - price)) if stop > price else 0
                
                if shares > 0:
                    valid_cards.append({
                        "sym": sym, "sector": sector, "dir": "🔴 做空", "pattern": pattern,
                        "price": round(price,2), "stop": stop, "target": target, "shares": shares, "rs": round(rs20*100,1)
                    })
                    
        except Exception as e:
            pass

    # 组装战报
    msg = f"<b>🦅 华尔街量价形态猎头 (洗盘/死猫跳识别)</b>\n时间: {now_jst}\n"
    msg += f"纳指今日表现: <b>{round(qqq_ret_today*100,2)}%</b>\n-------------------\n"
    
    if valid_cards:
        for c in valid_cards[:5]: # 胜率最高的前5个
            msg += f"{c['dir']} | <b>{c['sym']}</b> ({c['sector']})\n"
            msg += f"形态: <b>{c['pattern']}</b>\n"
            msg += f"现价: ${c['price']} (强于大盘 {c['rs']}%)\n"
            msg += f"🛑 止损: ${c['stop']} | 🎯 目标: ${c['target']}\n"
            msg += f"📦 建议: {c['shares']} 股 (风控$250)\n"
            msg += f"-------------------\n"
    else:
        msg += "今日未捕捉到明显的机构洗盘或放量突破形态。\n<b>空仓也是一种仓位，绝不强行交易！</b>\n"

    msg += "\n⚠️ <i>提示：形态识别基于日线数据，请结合盘口人工确认！</i>"
    
    send_tg(msg)
    print("扫描完成。")

if __name__ == "__main__":
    scan_market()
