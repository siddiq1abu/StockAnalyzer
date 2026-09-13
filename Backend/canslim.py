"""Data provider module for fetching financial data."""
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

def get_history(symbol, period="1y"):
    """Get historical price data for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def get_info(symbol):
    """Get fundamental information for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return info
    except Exception as e:
        print(f"Error fetching info for {symbol}: {e}")
        return {}

def get_quarterly_financials(symbol):
    """Get quarterly financial data."""
    try:
        ticker = yf.Ticker(symbol)
        
        # Try to get quarterly income statement
        try:
            income_stmt = ticker.income_stmt
            if not income_stmt.empty:
                # Get revenue and net income
                revenue = income_stmt.loc["Total Revenue"] if "Total Revenue" in income_stmt.index else None
                net_income = income_stmt.loc["Net Income"] if "Net Income" in income_stmt.index else None
                gross_profit = income_stmt.loc["Gross Profit"] if "Gross Profit" in income_stmt.index else None
                
                if revenue is not None:
                    return {
                        "available": True,
                        "data": {
                            "Total Revenue": revenue.tolist()[:4],  # Last 4 quarters
                            "Net Income": net_income.tolist()[:4] if net_income is not None else [],
                            "Gross Profit": gross_profit.tolist()[:4] if gross_profit is not None else []
                        }
                    }
        except:
            pass
        
        # Try quarterly balance sheet for alternative data
        try:
            balance_sheet = ticker.balance_sheet
            if not balance_sheet.empty:
                return {
                    "available": True,
                    "data": {
                        "Total Revenue": [0],  # Placeholder
                        "Net Income": [0],
                        "Gross Profit": [0]
                    }
                }
        except:
            pass
        
        return {"available": False}
    except Exception as e:
        print(f"Error fetching quarterly financials for {symbol}: {e}")
        return {"available": False}

def get_news(symbol):
    """Get recent news for a symbol."""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news:
            return []
        
        # Extract relevant news data
        recent_news = []
        for item in news[:10]:
            try:
                # Parse published date
                published = item.get("providerPublishTime")
                if published:
                    published_date = datetime.fromtimestamp(published).strftime("%Y-%m-%d %H:%M")
                else:
                    published_date = "Unknown"
                
                recent_news.append({
                    "title": item.get("title", "Untitled"),
                    "link": item.get("link", "#"),
                    "publisher": item.get("publisher", "Unknown"),
                    "published": published_date,
                    "type": item.get("type", "News")
                })
            except:
                continue
        
        return recent_news
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")
        return []

def search_symbols(query, universe):
    """Search for symbols matching query."""
    if not query:
        return []
    
    query = query.lower()
    results = []
    
    for stock in universe:
        symbol = stock["symbol"].replace(".NS", "")
        if (query in symbol.lower() or 
            query in stock["name"].lower() or 
            query in stock["sector"].lower()):
            results.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "sector": stock["sector"]
            })
    
    return results[:10]


def compute_canslim(info, fund, tech, df, benchmark, market, analyst=None, news_count=0):
    """Return the CANSLIM score structure consumed by the API and frontend."""
    analyst = analyst or {}
    tech_score = float(tech.get("technical_score", 50)) if tech else 50.0
    fund_score = 50.0
    if fund and fund.get("available"):
        revenue = fund.get("revenue_yoy_pct") or 0
        earnings = fund.get("earnings_yoy_pct") or 0
        fund_score = max(0, min(100, 50 + revenue * 0.5 + earnings * 0.5))

    momentum = (tech.get("trend", {}).get("momentum_6m_pct") or 0) if tech else 0
    market_score = 50.0
    if market:
        market_score += 15 if market.get("nifty_above_50dma") else -15
        market_score += 15 if market.get("nifty_above_200dma") else -15
    market_score = max(0, min(100, market_score))

    scores = {
        "C": max(0, min(100, fund_score)),
        "A": max(0, min(100, fund_score)),
        "N": max(0, min(100, 50 + min(max(momentum, -50), 50))),
        "S": max(0, min(100, tech_score)),
        "L": max(0, min(100, tech_score + (10 if momentum > 0 else -10))),
        "I": 50.0,
        "M": market_score,
    }
    titles = {
        "C": "Current earnings",
        "A": "Annual earnings",
        "N": "New developments",
        "S": "Supply and demand",
        "L": "Leader or laggard",
        "I": "Institutional sponsorship",
        "M": "Market direction",
    }
    reasons = {
        "C": [f"Revenue growth: {fund.get('revenue_yoy_pct')}%" if fund and fund.get("available") else "Quarterly earnings unavailable"],
        "A": [f"Earnings growth: {fund.get('earnings_yoy_pct')}%" if fund and fund.get("available") else "Annual earnings unavailable"],
        "N": [f"{news_count} recent news items found"],
        "S": [f"Technical score: {round(tech_score, 1)}"],
        "L": [f"Six-month momentum: {round(momentum, 2)}%"],
        "I": [f"Analyst coverage: {analyst.get('num_analysts', 0)}"],
        "M": ["Market above key moving averages" if market_score >= 50 else "Market below key moving averages"],
    }
    letters = {
        key: {"title": titles[key], "score": round(scores[key], 1), "reasons": reasons[key]}
        for key in scores
    }
    overall = round(sum(scores.values()) / len(scores), 1)
    strongest = max(scores, key=scores.get)
    weakest = min(scores, key=scores.get)
    verdict = "Strong Buy" if overall >= 75 else "Buy" if overall >= 60 else "Hold" if overall >= 45 else "Avoid"
    return {
        "overall": overall,
        "verdict": verdict,
        "verdict_note": "Based on technical, fundamental, news, and market inputs.",
        "strongest_factor": f"{strongest}: {titles[strongest]}",
        "weakest_factor": f"{weakest}: {titles[weakest]}",
        "letters": letters,
    }