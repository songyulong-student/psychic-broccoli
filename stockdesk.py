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
    
    # === 1. 获取大盘宏观基准 ===
    try:
        qqq_df = yf.Ticker("QQQ").history(period="2mo")
        spy_df = yf.Ticker("SPY").history(period="2mo")
        # 纳指今日涨跌幅 (用于判断是否洗盘)
        qqq_ret_today = (qqq_df["Close"].iloc[-1] / qqq_df["Close"].iloc[-2]) - 1
        # 标普20日涨跌幅 (用于计算相对强弱)
        spy_ret20 = (spy_df["Close"].iloc[-1] / spy_df["Close"].iloc[0]) - 1
    except Exception as e:
        print(f"获取大盘失败: {e}")
        qqq_ret_today, spy_ret20 = 0, 0

    # === 2. 四大金刚核心股票池 ===
    universe = {
        # 半导体 (AI算力)
        "AMD": "半导体", "NVDA": "半导体", "MU": "半导体", "AVGO": "半导体", "ARM": "半导体",
        # 电力 (AI基础设施)
        "VST": "电力", "CEG": "电力", "TLN": "电力", "GEV": "电力",
        # 医药 (降息防御)
        "LLY": "医药", "NVO": "医药", "MRK": "医药", "VRTX": "医药",
        # 新股与高弹性
        "RDDT": "新股", "PLTR": "新股", "ALAB": "新股", "COIN": "高弹性", "MSTR": "高弹性"
    }

    long_cards = []
    short_cards = []
    
    for sym, sector in universe.items():
        try:
            # 拉取3个月数据 (确保有足够的K线计算形态和ATR)
            df = yf.Ticker(sym).history(period="3mo")
            if len(df) < 40: continue
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            price = last["Close"]
            
            ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
            vol_ma20 = df["Volume"].tail(20).mean()
            vol_ratio = last["Volume"] / vol_ma20 if vol_ma20 > 0 else 1
            
            # 动能计算
            stock_ret_today = (last["Close"] / prev["Close"]) - 1
            rs_today = stock_ret_today - qqq_ret_today
            rs20 = (price / df["Close"].iloc[-20]) - 1 - spy_ret20
            
            # ATR 真实波动率计算 (用于动态止损)
            tr = pd.concat([
                df["High"] - df["Low"], 
                (df["High"] - df["Close"].shift()).abs(), 
                (df["Low"] - df["Close"].shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # === 3. 核心形态识别 (Price Action) ===
            body = abs(last["Close"] - last["Open"])
            lower_shadow = min(last["Open"], last["Close"]) - last["Low"]
            
            # 形态1：深V探底 (长下影线，下方有强支撑)
            is_deep_v = lower_shadow > body * 2 and lower_shadow > price * 0.02
            
            # 形态2：借纳指洗盘 (大盘跌超1%，但个股逆势抗跌)
            is_shakeout = qqq_ret_today < -0.01 and rs_today > 0.01
            
            # 形态3：放量突破 (创20日新高且放量)
            recent_high = df["High"].tail(20).max()
            is_breakout = price > recent_high and vol_ratio > 1.5
            
            # 形态4：缩量回踩 (在均线附近且极度缩量，跌无可跌)
            is_pullback = price <= ema20 * 1.02 and vol_ratio < 0.8
            
            # 形态5：死猫跳诱多 (在均线下方，缩量反弹)
            is_dead_cat = price < ema20 and stock_ret_today > 0 and vol_ratio < 0.8

            # === 4. 交易逻辑生成 ===
            # 🟢 做多逻辑
            if not is_dead_cat and price > ema20 and rs20 > 0:
                if is_breakout:
                    pattern = "🔥 放量突破 (真突破)"
                elif is_shakeout:
                    pattern = "🧹 借纳指洗盘 (逆势抗跌)"
                elif is_deep_v:
                    pattern = "🗡 深V探底 (长下影线)"
                elif is_pullback:
                    pattern = "🪶 缩量回踩 (极佳买点)"
                else:
                    pattern = "📈 趋势延续"
                
                stop = round(price - (1.5 * atr), 2)
                target = round(price + (1.5 * atr * 2), 2)
                shares = int(250 / (price - stop)) if price > stop else 0
                
                if shares > 0:
                    long_cards.append({
                        "sym": sym, "sector": sector, "pattern": pattern,
                        "price": round(price,2), "stop": stop, "target": target, "shares": shares, "rs": round(rs20*100,1)
                    })
            
            # 🔴 做空逻辑 (死猫跳诱多，或破位暴跌)
            elif (is_dead_cat and rs20 < 0) or (price < ema20 and is_breakout and stock_ret_today < 0):
                pattern = "💀 死猫跳诱多 (做空)" if is_dead_cat else "🩸 破位放量下杀"
                stop = round(price + (1.5 * atr), 2)
                target = round(price - (1.5 * atr * 2), 2)
                shares = int(250 / (stop - price)) if stop > price else 0
                
                if shares > 0:
                    short_cards.append({
                        "sym": sym, "sector": sector, "pattern": pattern,
                        "price": round(price,2), "stop": stop, "target": target, "shares": shares, "rs": round(rs20*100,1)
                    })
                    
        except Exception as e:
            pass

    # === 5. 组装战报 (按强弱排序) ===
    long_cards.sort(key=lambda x: x["rs"], reverse=True)
    short_cards.sort(key=lambda x: x["rs"])

    msg = f"<b>🦅 华尔街量价形态猎头 (完全体)</b>\n"
    msg += f"时间: {now_jst} | 纳指今日: {round(qqq_ret_today*100,2)}%\n"
    msg += f"-------------------\n"
    
    # 推送做多
    if long_cards:
        msg += f"<b>🟢 做多猎物：</b>\n"
        for c in long_cards[:3]: # 取前3名
            msg += f"👉 <b>{c['sym']}</b> ({c['sector']}) | 跑赢大盘 {c['rs']}%\n"
            msg += f"形态: <b>{c['pattern']}</b>\n"
            msg += f"现价: ${c['price']} | 🛑 止损: ${c['stop']} | 🎯 目标: ${c['target']}\n"
            msg += f"📦 风控股数: {c['shares']} 股 ($250)\n\n"

    # 推送做空
    if short_cards:
        msg += f"<b>🔴 做空猎物：</b>\n"
        for c in short_cards[:2]: # 取前2名
            msg += f"👉 <b>{c['sym']}</b> ({c['sector']}) | 弱于大盘 {c['rs']}%\n"
            msg += f"形态: <b>{c['pattern']}</b>\n"
            msg += f"现价: ${c['price']} | 🛑 止损: ${c['stop']} | 🎯 目标: ${c['target']}\n"
            msg += f"📦 风控股数: {c['shares']} 股 ($250)\n\n"

    if not long_cards and not short_cards:
        msg += "今日四大板块均未触发高胜率机构形态。\n<b>空仓也是一种仓位，按兵不动！</b>\n"

    msg += f"-------------------\n"
    msg += f"⚠️ <i>系统已启用ATR动态风控，请结合盘口人工确认后执行。</i>"
    
    send_tg(msg)
    print("扫描完成。")

if __name__ == "__main__":
    scan_market()
