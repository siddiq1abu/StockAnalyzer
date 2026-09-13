"""Data provider module for fetching financial data."""
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import time

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"


def _get_history_from_yahoo_chart(symbol, period):
    range_by_period = {"1y": "1y", "6mo": "6mo", "3mo": "3mo"}
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={"range": range_by_period.get(period, period), "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    result = response.json().get("chart", {}).get("result")
    if not result:
        return None

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    rows = []
    for index, timestamp in enumerate(timestamps):
        row = {
            name.capitalize(): values[index] if index < len(values) else None
            for name, values in quote.items()
        }
        row["Date"] = pd.to_datetime(timestamp, unit="s")
        rows.append(row)
    if not rows:
        return None
    frame = pd.DataFrame(rows)[["Date", "Open", "High", "Low", "Close", "Volume"]]
    frame = frame.dropna(subset=["Open", "High", "Low", "Close"])
    frame["Volume"] = frame["Volume"].fillna(0)
    return frame


def get_history(symbol, period="1y"):
    """Get historical price data for a symbol."""
    try:
        df = _get_history_from_yahoo_chart(symbol, period)
        if df is not None and not df.empty:
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
            # Try different methods to get financial data
            quarterly_data = {}
            
            # Get quarterly income statement
            income_stmt = ticker.quarterly_income_stmt
            if income_stmt is not None and not income_stmt.empty:
                quarterly_data["Total Revenue"] = income_stmt.loc["Total Revenue"].tolist() if "Total Revenue" in income_stmt.index else []
                quarterly_data["Net Income"] = income_stmt.loc["Net Income"].tolist() if "Net Income" in income_stmt.index else []
                quarterly_data["Gross Profit"] = income_stmt.loc["Gross Profit"].tolist() if "Gross Profit" in income_stmt.index else []
            
            # If quarterly data is empty, try annual data
            if not quarterly_data.get("Total Revenue"):
                income_stmt = ticker.income_stmt
                if income_stmt is not None and not income_stmt.empty:
                    quarterly_data["Total Revenue"] = income_stmt.loc["Total Revenue"].tolist() if "Total Revenue" in income_stmt.index else []
                    quarterly_data["Net Income"] = income_stmt.loc["Net Income"].tolist() if "Net Income" in income_stmt.index else []
                    quarterly_data["Gross Profit"] = income_stmt.loc["Gross Profit"].tolist() if "Gross Profit" in income_stmt.index else []
            
            if quarterly_data.get("Total Revenue") and len(quarterly_data["Total Revenue"]) > 0:
                return {
                    "available": True,
                    "data": quarterly_data
                }
        except Exception as e:
            print(f"Error getting income statement for {symbol}: {e}")
        
        # Try to get financials from info
        info = get_info(symbol)
        if info:
            # Use info data as fallback
            revenue = info.get("totalRevenue")
            net_income = info.get("netIncomeToCommon")
            if revenue or net_income:
                return {
                    "available": True,
                    "data": {
                        "Total Revenue": [revenue] if revenue else [],
                        "Net Income": [net_income] if net_income else [],
                        "Gross Profit": []
                    }
                }
        
        return {"available": False}
    except Exception as e:
        print(f"Error fetching quarterly financials for {symbol}: {e}")
        return {"available": False}

def get_news(symbol):
    """Get recent news for a symbol."""
    try:
        query = symbol.removesuffix(".NS").removesuffix(".BO")
        response = requests.get(
            YAHOO_SEARCH_URL,
            params={"q": query, "newsCount": 10, "quotesCount": 1},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
        search_news = response.json().get("news", [])
        if search_news:
            return [{
                "title": item.get("title", "Untitled"),
                "link": item.get("link", "#"),
                "publisher": item.get("publisher", "Yahoo Finance"),
                "published": datetime.fromtimestamp(item["providerPublishTime"]).strftime("%Y-%m-%d %H:%M")
                if item.get("providerPublishTime") else "Unknown",
                "type": item.get("type", "News"),
            } for item in search_news[:10]]
    except Exception as e:
        print(f"Yahoo search news failed for {symbol}: {e}; trying yfinance")

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
        symbol_l = symbol.lower()
        name_l = stock["name"].lower()
        sector_l = stock["sector"].lower()
        if query in symbol_l or query in name_l or query in sector_l:
            match_rank = (0 if symbol_l.startswith(query) else
                          1 if name_l.startswith(query) else
                          2 if query in symbol_l else
                          3 if query in name_l else 4)
            results.append((match_rank, stock["name"].lower(), {
                "symbol": stock["symbol"],
                "name": stock["name"],
                "sector": stock["sector"]
            }))
    
    return [item[2] for item in sorted(results, key=lambda item: item[:2])[:10]]