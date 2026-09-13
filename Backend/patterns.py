"""Chart pattern detection module."""
import numpy as np

def detect_patterns(df):
    """Detect chart patterns in price data."""
    if df is None or len(df) < 30:
        return []
    
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    
    patterns = []
    
    # Detect patterns using recent data
    patterns.extend(detect_head_and_shoulders(close))
    patterns.extend(detect_double_top_bottom(close))
    patterns.extend(detect_triangle(high, low))
    patterns.extend(detect_breakout(close, high, low))
    
    return patterns

def detect_head_and_shoulders(close):
    """Detect head and shoulders pattern."""
    patterns = []
    n = len(close)
    if n < 30:
        return patterns
    
    # Look for pattern in last 60 bars
    for i in range(max(0, n-60), n-20):
        # Need at least 5 points for pattern
        if i + 20 > n:
            continue
        
        # Simplified detection
        left_shoulder = close[i:i+5].max()
        head = close[i+5:i+15].max()
        right_shoulder = close[i+15:i+20].max()
        
        if head > left_shoulder and head > right_shoulder:
            # Check if shoulders are roughly equal
            shoulder_diff = abs(left_shoulder - right_shoulder) / left_shoulder
            if shoulder_diff < 0.05:
                # Check if pattern is recent
                if max([left_shoulder, head, right_shoulder]) > close[-1]:
                    patterns.append({
                        "pattern": "Head and Shoulders",
                        "direction": "bearish" if head > close[-1] else "bullish",
                        "strength": 70 if head > close[-1] else 60,
                        "note": f"Head at {head:.2f}, shoulders at {left_shoulder:.2f}/{right_shoulder:.2f}"
                    })
    
    return patterns[:2]

def detect_double_top_bottom(close):
    """Detect double top or double bottom patterns."""
    patterns = []
    n = len(close)
    if n < 30:
        return patterns
    
    # Simplified detection
    recent = close[-30:]
    max_idx = np.argmax(recent)
    min_idx = np.argmin(recent)
    
    # Double top
    if max_idx > 5 and max_idx < 25:
        first_peak = recent[:max_idx].max() if max_idx > 0 else recent[0]
        valley = recent[max_idx:].min()
        if valley < first_peak * 0.9:  # Significant pullback
            patterns.append({
                "pattern": "Double Top",
                "direction": "bearish",
                "strength": 65,
                "note": f"Potential reversal at {recent[max_idx]:.2f}"
            })
    
    # Double bottom
    if min_idx > 5 and min_idx < 25:
        first_bottom = recent[:min_idx].min() if min_idx > 0 else recent[0]
        peak = recent[min_idx:].max()
        if peak > first_bottom * 1.1:  # Significant bounce
            patterns.append({
                "pattern": "Double Bottom",
                "direction": "bullish",
                "strength": 65,
                "note": f"Potential reversal at {recent[min_idx]:.2f}"
            })
    
    return patterns[:2]

def detect_triangle(high, low):
    """Detect symmetrical/ascending/descending triangle patterns."""
    patterns = []
    n = len(high)
    if n < 20:
        return patterns
    
    recent_high = high[-20:]
    recent_low = low[-20:]
    
    # Check for converging trendlines (triangle)
    high_slope = (recent_high[-1] - recent_high[0]) / len(recent_high)
    low_slope = (recent_low[-1] - recent_low[0]) / len(recent_low)
    
    # Check if trendlines are converging
    if abs(high_slope) < 0.1 and abs(low_slope) < 0.1:
        return patterns
    
    # Symmetrical triangle
    if high_slope < 0 and low_slope > 0:
        patterns.append({
            "pattern": "Symmetrical Triangle",
            "direction": "neutral",
            "strength": 60,
            "note": "Converging trendlines, breakout likely"
        })
    # Ascending triangle
    elif high_slope > 0 and low_slope > 0:
        patterns.append({
            "pattern": "Ascending Triangle",
            "direction": "bullish",
            "strength": 70,
            "note": "Higher lows, potential breakout above resistance"
        })
    # Descending triangle
    elif high_slope < 0 and low_slope < 0:
        patterns.append({
            "pattern": "Descending Triangle",
            "direction": "bearish",
            "strength": 70,
            "note": "Lower highs, potential breakdown below support"
        })
    
    return patterns[:1]

def detect_breakout(close, high, low):
    """Detect potential breakouts."""
    patterns = []
    n = len(close)
    if n < 20:
        return patterns
    
    current = close[-1]
    recent_high = high[-20:].max()
    recent_low = low[-20:].min()
    
    # Breakout above recent high with volume
    if current > recent_high * 1.01:  # 1% above recent high
        patterns.append({
            "pattern": "Breakout",
            "direction": "bullish",
            "strength": 75,
            "note": f"Price broke above resistance at {recent_high:.2f}"
        })
    # Breakdown below recent low
    elif current < recent_low * 0.99:  # 1% below recent low
        patterns.append({
            "pattern": "Breakdown",
            "direction": "bearish",
            "strength": 75,
            "note": f"Price broke below support at {recent_low:.2f}"
        })
    
    return patterns