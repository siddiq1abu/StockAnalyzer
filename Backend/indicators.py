"""Technical indicators and analysis functions."""
import pandas as pd
import numpy as np

def technical_snapshot(df):
    """Generate comprehensive technical analysis snapshot."""
    if df is None or len(df) < 60:
        return {"error": "Insufficient data"}
    
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    
    # Calculate indicators
    rsi14 = calculate_rsi(close, 14)
    macd_line, signal_line, histogram = calculate_macd(close)
    
    # Moving averages
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) > 200 else None
    
    # Bollinger Bands
    bb_middle = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std
    bb_pct_b = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if bb_upper.iloc[-1] != bb_lower.iloc[-1] else 0.5
    bb_pct_b = max(0, min(1, bb_pct_b)) * 100
    
    # ATR
    atr_pct = calculate_atr(df, 14) / close.iloc[-1] * 100
    
    # Volume
    volume_ratio = volume.iloc[-1] / volume.tail(20).mean()
    
    # 52-week position
    year_high = close.tail(252).max() if len(close) > 252 else close.max()
    year_low = close.tail(252).min() if len(close) > 252 else close.min()
    price_52w_pos_pct = (close.iloc[-1] - year_low) / (year_high - year_low) * 100 if year_high != year_low else 50
    
    # Trend detection
    trend_data = detect_trend(df)
    
    # Support & Resistance
    support_resistance = find_support_resistance(df)
    
    # Technical signals
    signals = generate_technical_signals(df, {
        'rsi14': rsi14,
        'macd_line': macd_line,
        'macd_signal': signal_line,
        'sma20': sma20,
        'sma50': sma50,
        'sma200': sma200,
        'bb_pct_b': bb_pct_b,
        'volume_ratio': volume_ratio
    })
    
    # Technical score
    tech_score = calculate_technical_score(df, signals)
    
    return {
        "indicators": {
            "rsi14": round(rsi14, 2) if rsi14 else None,
            "macd": round(macd_line, 3) if macd_line else None,
            "macd_signal": round(signal_line, 3) if signal_line else None,
            "macd_histogram": round(histogram, 3) if histogram else None,
            "bb_pct_b": round(bb_pct_b, 2),
            "atr_pct": round(atr_pct, 2),
            "volume_ratio": round(volume_ratio, 2),
            "price_52w_pos_pct": round(price_52w_pos_pct, 2),
        },
        "trend": trend_data,
        "signals": signals,
        "support": support_resistance["support"],
        "resistance": support_resistance["resistance"],
        "technical_score": tech_score
    }

def calculate_rsi(close, period=14):
    """Calculate RSI indicator."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if len(rsi) > 0 else None

def calculate_macd(close, fast=12, slow=26, signal=9):
    """Calculate MACD indicator."""
    exp1 = close.ewm(span=fast, adjust=False).mean()
    exp2 = close.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def calculate_atr(df, period=14):
    """Calculate Average True Range."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.iloc[-1] if len(atr) > 0 else None

def detect_trend(df):
    """Detect price trend using multiple indicators."""
    close = df["Close"]
    current = close.iloc[-1]
    
    # Moving averages
    sma20 = close.rolling(20).mean().iloc[-1] if len(close) > 20 else None
    sma50 = close.rolling(50).mean().iloc[-1] if len(close) > 50 else None
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) > 200 else None
    
    # Determine trend
    above_20 = current > sma20 if sma20 else True
    above_50 = current > sma50 if sma50 else True
    above_200 = current > sma200 if sma200 else True
    
    # Trend strength
    if above_20 and above_50 and above_200:
        trend = "Strong Uptrend"
    elif above_20 and above_50:
        trend = "Moderate Uptrend"
    elif above_20:
        trend = "Weak Uptrend"
    elif not above_20 and not above_50 and not above_200:
        trend = "Strong Downtrend"
    elif not above_20 and not above_50:
        trend = "Moderate Downtrend"
    else:
        trend = "Consolidation"
    
    # Momentum
    momentum_1m = (current / close.iloc[-22] - 1) * 100 if len(close) > 22 else None
    momentum_3m = (current / close.iloc[-66] - 1) * 100 if len(close) > 66 else None
    momentum_6m = (current / close.iloc[-132] - 1) * 100 if len(close) > 132 else None
    
    return {
        "trend": trend,
        "above_sma20": bool(above_20),
        "above_sma50": bool(above_50),
        "above_sma200": bool(above_200) if sma200 else None,
        "sma20": round(sma20, 2) if sma20 else None,
        "sma50": round(sma50, 2) if sma50 else None,
        "sma200": round(sma200, 2) if sma200 else None,
        "momentum_1m_pct": round(momentum_1m, 2) if momentum_1m else None,
        "momentum_3m_pct": round(momentum_3m, 2) if momentum_3m else None,
        "momentum_6m_pct": round(momentum_6m, 2) if momentum_6m else None,
        "details": {
            "sma20": round(sma20, 2) if sma20 else None,
            "sma50": round(sma50, 2) if sma50 else None,
            "sma200": round(sma200, 2) if sma200 else None,
        }
    }

def find_support_resistance(df):
    """Find key support and resistance levels."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    
    # Use pivot points
    pivot_period = 10
    support_levels = []
    resistance_levels = []
    
    # Find swing lows and highs
    for i in range(pivot_period, len(df) - pivot_period, 5):
        # Swing low
        if low.iloc[i] < low.iloc[i-pivot_period:i].min() and low.iloc[i] < low.iloc[i+1:i+pivot_period+1].min():
            support_levels.append(round(float(low.iloc[i]), 2))
        # Swing high
        if high.iloc[i] > high.iloc[i-pivot_period:i].max() and high.iloc[i] > high.iloc[i+1:i+pivot_period+1].max():
            resistance_levels.append(round(float(high.iloc[i]), 2))
    
    # Get nearest levels to current price
    current = float(close.iloc[-1])
    support_levels = [s for s in support_levels if s < current][-3:] if support_levels else []
    resistance_levels = [r for r in resistance_levels if r > current][:3] if resistance_levels else []
    
    # Add MA levels
    if len(close) > 50:
        sma50 = float(close.rolling(50).mean().iloc[-1])
        if sma50 < current and sma50 not in support_levels:
            support_levels.append(round(sma50, 2))
        elif sma50 > current and sma50 not in resistance_levels:
            resistance_levels.append(round(sma50, 2))
    
    return {
        "support": [{"level": s, "type": "support"} for s in sorted(support_levels, reverse=True)[:3]],
        "resistance": [{"level": r, "type": "resistance"} for r in sorted(resistance_levels)[:3]]
    }

def generate_technical_signals(df, indicators):
    """Generate buy/sell signals based on technical analysis."""
    signals = []
    close = df["Close"]
    current = close.iloc[-1]
    
    # RSI
    rsi = indicators.get("rsi14", 50)
    if rsi and rsi < 30:
        signals.append({"signal": f"RSI oversold at {rsi:.1f}", "bias": "bullish"})
    elif rsi and rsi > 70:
        signals.append({"signal": f"RSI overbought at {rsi:.1f}", "bias": "bearish"})
    
    # MACD
    macd_line = indicators.get("macd_line")
    macd_signal = indicators.get("macd_signal")
    if macd_line and macd_signal:
        if macd_line > macd_signal:
            signals.append({"signal": "MACD bullish crossover", "bias": "bullish"})
        else:
            signals.append({"signal": "MACD bearish crossover", "bias": "bearish"})
    
    # Moving Average crosses
    sma20 = indicators.get("sma20")
    sma50 = indicators.get("sma50")
    if sma20 and sma50:
        if current > sma20 and current > sma50:
            signals.append({"signal": "Price above SMAs", "bias": "bullish"})
        elif current < sma20 and current < sma50:
            signals.append({"signal": "Price below SMAs", "bias": "bearish"})
    
    # Bollinger Bands
    bb_pct_b = indicators.get("bb_pct_b", 50)
    if bb_pct_b < 20:
        signals.append({"signal": "Price near lower Bollinger Band", "bias": "bullish"})
    elif bb_pct_b > 80:
        signals.append({"signal": "Price near upper Bollinger Band", "bias": "bearish"})
    
    # Volume
    volume_ratio = indicators.get("volume_ratio", 1)
    if volume_ratio > 1.5:
        signals.append({"signal": f"High volume ({volume_ratio:.1f}x average)", "bias": "bullish"})
    
    return signals

def calculate_technical_score(df, signals):
    """Calculate a technical score based on multiple factors."""
    score = 50  # Start from neutral
    close = df["Close"]
    current = close.iloc[-1]
    
    # Trend factor (0-30 points)
    if len(close) > 50:
        sma20 = close.rolling(20).mean().iloc[-1]
        sma50 = close.rolling(50).mean().iloc[-1]
        if current > sma20 and current > sma50:
            score += 15
        elif current > sma20 or current > sma50:
            score += 7
        else:
            score -= 10
    
    # RSI factor (0-20 points)
    rsi = calculate_rsi(close)
    if rsi:
        if 40 <= rsi <= 60:
            score += 5
        elif 30 <= rsi <= 40:
            score += 10
        elif 60 <= rsi <= 70:
            score -= 5
        elif rsi > 70:
            score -= 15
        elif rsi < 30:
            score += 15
    
    # MACD factor (0-20 points)
    macd_line, signal_line, _ = calculate_macd(close)
    if macd_line and signal_line:
        if macd_line > signal_line:
            score += 10
        else:
            score -= 10
    
    # Volume factor (0-15 points)
    volume_ratio = df["Volume"].iloc[-1] / df["Volume"].tail(20).mean()
    if volume_ratio > 1.2:
        score += 5
    elif volume_ratio < 0.8:
        score -= 5
    
    # Momentum factor (0-15 points)
    if len(close) > 22:
        momentum = (current / close.iloc[-22] - 1) * 100
        if momentum > 5:
            score += 10
        elif momentum > 0:
            score += 5
        elif momentum < -5:
            score -= 10
        elif momentum < 0:
            score -= 5
    
    # Cap at 0-100
    return max(0, min(100, score))