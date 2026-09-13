"""Fundamental analysis module."""
import yfinance as yf

def quarterly_analysis(qf):
    """Analyze quarterly financial data."""
    if not qf or not qf.get("available", False):
        return {"available": False, "message": "No quarterly data available"}
    
    try:
        data = qf.get("data", {})
        if not data:
            return {"available": False, "message": "No data points available"}
        
        # Get revenue and earnings data
        revenue = data.get("Total Revenue", [])
        net_income = data.get("Net Income", [])
        gross_profit = data.get("Gross Profit", [])
        
        if not revenue or len(revenue) < 2:
            return {"available": False, "message": "Insufficient quarterly data"}
        
        # Calculate growth rates
        revenue_yoy = ((revenue[-1] - revenue[0]) / revenue[0]) * 100 if revenue[0] != 0 else None
        revenue_qoq = ((revenue[-1] - revenue[-2]) / revenue[-2]) * 100 if len(revenue) > 1 and revenue[-2] != 0 else None
        
        earnings_yoy = ((net_income[-1] - net_income[0]) / net_income[0]) * 100 if net_income and net_income[0] != 0 else None
        earnings_qoq = ((net_income[-1] - net_income[-2]) / net_income[-2]) * 100 if net_income and len(net_income) > 1 and net_income[-2] != 0 else None
        
        # Profit margins
        profit_margin = (net_income[-1] / revenue[-1] * 100) if revenue[-1] != 0 else None
        
        return {
            "available": True,
            "latest": {
                "quarter": "Latest Quarter",
                "revenue_cr": round(revenue[-1] / 1e7, 2) if revenue[-1] else None,  # Convert to crores
                "net_income_cr": round(net_income[-1] / 1e7, 2) if net_income else None,
                "profit_margin_pct": round(profit_margin, 2) if profit_margin else None
            },
            "revenue_yoy_pct": round(revenue_yoy, 2) if revenue_yoy else None,
            "revenue_qoq_pct": round(revenue_qoq, 2) if revenue_qoq else None,
            "earnings_yoy_pct": round(earnings_yoy, 2) if earnings_yoy else None,
            "earnings_qoq_pct": round(earnings_qoq, 2) if earnings_qoq else None,
            "trend": {
                "revenue": [round(r / 1e7, 2) for r in revenue[-4:]],
                "earnings": [round(n / 1e7, 2) for n in net_income[-4:]] if net_income else []
            }
        }
    except Exception as e:
        return {"available": False, "message": f"Error analyzing data: {str(e)}"}

def analyst_ratings(info, current_price):
    """Analyze analyst ratings and targets."""
    if not info:
        return {"consensus": "N/A", "num_analysts": 0}
    
    # Extract analyst data
    recommendation = info.get("recommendationKey", "N/A")
    recommendation_mean = info.get("recommendationMean", 3)
    target_mean = info.get("targetMeanPrice", None)
    target_high = info.get("targetHighPrice", None)
    target_low = info.get("targetLowPrice", None)
    num_analysts = info.get("numberOfAnalystOpinions", 0)
    
    # Convert recommendation mean to consensus
    if recommendation_mean:
        if recommendation_mean <= 1.5:
            consensus = "Strong Buy"
        elif recommendation_mean <= 2.5:
            consensus = "Buy"
        elif recommendation_mean <= 3.5:
            consensus = "Hold"
        elif recommendation_mean <= 4.5:
            consensus = "Sell"
        else:
            consensus = "Strong Sell"
    else:
        consensus = "N/A"
    
    # Calculate upside potential
    if target_mean and current_price:
        upside_pct = ((target_mean - current_price) / current_price) * 100
    else:
        upside_pct = None
    
    return {
        "consensus": consensus,
        "num_analysts": num_analysts,
        "target_mean": round(target_mean, 2) if target_mean else None,
        "target_high": round(target_high, 2) if target_high else None,
        "target_low": round(target_low, 2) if target_low else None,
        "upside_pct": round(upside_pct, 2) if upside_pct else None,
        "recommendation_mean": round(recommendation_mean, 2) if recommendation_mean else None
    }

def valuation_snapshot(info):
    """Get valuation metrics snapshot."""
    if not info:
        return {
            "pe_trailing": None,
            "pe_forward": None,
            "peg": None,
            "pb": None,
            "roe": None,
            "debt_to_equity": None,
            "institutional_holding_pct": None
        }
    
    return {
        "pe_trailing": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
        "pe_forward": round(info.get("forwardPE", 0), 2) if info.get("forwardPE") else None,
        "peg": round(info.get("pegRatio", 0), 2) if info.get("pegRatio") else None,
        "pb": round(info.get("priceToBook", 0), 2) if info.get("priceToBook") else None,
        "roe": round(info.get("returnOnEquity", 0) * 100, 2) if info.get("returnOnEquity") else None,
        "debt_to_equity": round(info.get("debtToEquity", 0), 2) if info.get("debtToEquity") else None,
        "institutional_holding_pct": round(info.get("heldPercentInstitutions", 0) * 100, 2) if info.get("heldPercentInstitutions") else None
    }

def fundamental_score(fund_data, info, analyst):
    """Calculate fundamental score (0-100)."""
    score = 50  # Start from neutral
    
    # Quarterly growth (0-30 points)
    if fund_data.get("available", False):
        revenue_yoy = fund_data.get("revenue_yoy_pct")
        earnings_yoy = fund_data.get("earnings_yoy_pct")
        
        if revenue_yoy:
            if revenue_yoy > 20:
                score += 15
            elif revenue_yoy > 10:
                score += 10
            elif revenue_yoy > 5:
                score += 5
            elif revenue_yoy < -10:
                score -= 10
            elif revenue_yoy < 0:
                score -= 5
        
        if earnings_yoy:
            if earnings_yoy > 25:
                score += 15
            elif earnings_yoy > 15:
                score += 10
            elif earnings_yoy > 5:
                score += 5
            elif earnings_yoy < -15:
                score -= 10
            elif earnings_yoy < 0:
                score -= 5
    
    # Valuation (0-20 points)
    if info:
        pe = info.get("trailingPE")
        if pe:
            if pe < 15:
                score += 10
            elif pe < 25:
                score += 5
            elif pe > 40:
                score -= 10
            elif pe > 30:
                score -= 5
        
        roe = info.get("returnOnEquity")
        if roe:
            if roe > 0.20:
                score += 10
            elif roe > 0.15:
                score += 5
            elif roe < 0.05:
                score -= 5
        
        debt_to_equity = info.get("debtToEquity")
        if debt_to_equity:
            if debt_to_equity < 0.5:
                score += 5
            elif debt_to_equity > 1.5:
                score -= 5
    
    # Analyst ratings (0-15 points)
    if analyst and analyst.get("num_analysts", 0) > 0:
        if analyst.get("consensus") in ["Strong Buy", "Buy"]:
            score += 10
        elif analyst.get("consensus") in ["Sell", "Strong Sell"]:
            score -= 10
        
        if analyst.get("upside_pct", 0) > 15:
            score += 5
        elif analyst.get("upside_pct", 0) < -10:
            score -= 5
    
    # Cap at 0-100
    return max(0, min(100, score))