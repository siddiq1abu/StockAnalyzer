"""Indian Stock Analyzer - Flask API + static frontend server."""
import os, time
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import indicators, patterns, fundamentals, canslim, data_provider as dp
import api_clients
from nse_stocks import SEARCH_UNIVERSE, UNIVERSE

BASE = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(BASE, "..", "Frontend")

app = Flask(__name__, static_folder=FRONTEND, static_url_path="")
CORS(app)

_market_cache = {"data": None, "ts": 0}
_trending_cache = {"data": None, "ts": 0}
_recommendations_cache = {"data": None, "ts": 0}

SECTOR_MAP = {s["symbol"]: s["sector"] for s in UNIVERSE}
NAME_MAP = {s["symbol"]: s["name"] for s in UNIVERSE}


def get_market() -> dict:
    """Nifty 50 trend + market breadth for CANSLIM 'M'."""
    now = time.time()
    if _market_cache["data"] and now - _market_cache["ts"] < 1800:
        return _market_cache["data"]

    nifty = dp.get_history("^NSEI", period="1y")
    mkt = {}
    if nifty is not None and len(nifty) > 200:
        c = nifty["Close"]
        mkt["nifty_above_50dma"] = bool(c.iloc[-1] > c.rolling(50).mean().iloc[-1])
        mkt["nifty_above_200dma"] = bool(c.iloc[-1] > c.rolling(200).mean().iloc[-1])
        mkt["nifty_trend"] = "uptrend" if mkt["nifty_above_50dma"] else "downtrend"
        mkt["nifty_level"] = round(float(c.iloc[-1]), 2)
    # breadth: % of universe above 50-DMA
    def above_50dma(stock):
        history = dp.get_history(stock["symbol"], period="6mo")
        if history is None or len(history) <= 60:
            return None
        return history["Close"].iloc[-1] > history["Close"].rolling(50).mean().iloc[-1]

    with ThreadPoolExecutor(max_workers=8) as pool:
        breadth = [value for value in pool.map(above_50dma, UNIVERSE[:35]) if value is not None]
    above = sum(breadth)
    total = len(breadth)
    mkt["breadth_pct_above_50dma"] = round(above / total * 100, 1) if total else None
    _market_cache.update(data=mkt, ts=now)
    return mkt


def normalize_symbol(raw: str) -> str:
    sym = raw.strip().upper().replace(" ", "")
    if not sym.endswith((".NS", ".BO")):
        sym += ".NS"
    return sym


@app.route("/api/search")
def search():
    q = request.args.get("q", "")
    return jsonify(dp.search_symbols(q, SEARCH_UNIVERSE))


@app.route("/api/analyze/<raw_symbol>")
def analyze(raw_symbol):
    symbol = normalize_symbol(raw_symbol)
    df = dp.get_history(symbol, period="1y")
    if df is None or len(df) < 60:
        return jsonify({"error": f"Could not fetch data for {symbol}"}), 404

    info = dp.get_info(symbol)
    qf = dp.get_quarterly_financials(symbol)
    news = dp.get_news(symbol)
    benchmark = dp.get_history("^NSEI", period="1y")

    tech = indicators.technical_snapshot(df)
    chart_patterns = patterns.detect_patterns(df)
    fund = fundamentals.quarterly_analysis(qf)
    analyst = fundamentals.analyst_ratings(info, float(df["Close"].iloc[-1]))
    fund_score = fundamentals.fundamental_score(fund if fund.get("available") else {}, info, analyst)
    market = get_market()
    cns = canslim.compute_canslim(info, fund, tech, df, benchmark, market,
                                  analyst=analyst, news_count=len(news))

    close = df["Close"]
    overall = round(0.40 * cns["overall"] + 0.30 * tech["technical_score"]
                    + 0.30 * fund_score, 1)
    rating = ("Strong Buy" if overall >= 72 else "Buy" if overall >= 58 else
              "Hold" if overall >= 45 else "Reduce" if overall >= 33 else "Avoid")

    hist = df.tail(180).reset_index()
    chart_data = {
        "dates": [str(d.date()) for d in hist["Date"]],
        "ohlc": [[round(float(r["Open"]), 2), round(float(r["Close"]), 2),
                  round(float(r["Low"]), 2), round(float(r["High"]), 2)] for _, r in hist.iterrows()],
        "volumes": [int(v) for v in hist["Volume"]],
    }

    return jsonify({
        "symbol": symbol,
        "name": NAME_MAP.get(symbol, info.get("longName", symbol)),
        "sector": info.get("sector", SECTOR_MAP.get(symbol, "N/A")),
        "price": round(float(close.iloc[-1]), 2),
        "day_change_pct": round(float((close.iloc[-1] / close.iloc[-2] - 1) * 100), 2),
        "week_change_pct": round(float((close.iloc[-1] / close.iloc[-6] - 1) * 100), 2) if len(close) > 6 else None,
        "month_change_pct": round(float((close.iloc[-1] / close.iloc[-22] - 1) * 100), 2) if len(close) > 22 else None,
        "overall_score": overall,
        "rating": rating,
        "canslim": cns,
        "technical": tech,
        "chart_patterns": chart_patterns,
        "fundamentals": fund,
        "fundamental_score": fund_score,
        "valuation": fundamentals.valuation_snapshot(info),
        "analyst": analyst,
        "news": news,
        "chart": chart_data,
        "market": market,
    })


@app.route("/api/trending")
def trending():
    now = time.time()
    if _trending_cache["data"] and now - _trending_cache["ts"] < 900:
        return jsonify(_trending_cache["data"])

    def trend_row(stock):
        history = dp.get_history(stock["symbol"], period="3mo")
        if history is None or len(history) < 5:
            return None
        close = history["Close"]
        volume = history["Volume"]
        average_volume = float(volume.tail(20).mean())
        return {
            "symbol": stock["symbol"], "name": stock["name"], "sector": stock["sector"],
            "price": round(float(close.iloc[-1]), 2),
            "change_1d_pct": round(float((close.iloc[-1] / close.iloc[-2] - 1) * 100), 2),
            "change_1m_pct": round(float((close.iloc[-1] / close.iloc[-22] - 1) * 100), 2) if len(close) > 22 else None,
            "volume_ratio": round(float(volume.iloc[-1] / average_volume), 2) if average_volume else 0,
            "near_52w_high": bool(close.iloc[-1] >= close.tail(252).max() * 0.95) if len(close) > 60 else False,
        }

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = [row for row in pool.map(trend_row, UNIVERSE) if row]
    gainers = sorted(rows, key=lambda r: r["change_1d_pct"], reverse=True)[:10]
    momentum = sorted(rows, key=lambda r: (r["change_1m_pct"] or 0), reverse=True)[:10]
    active = sorted(rows, key=lambda r: r["volume_ratio"], reverse=True)[:10]
    high = [r for r in rows if r["near_52w_high"]][:10]
    sectors = {}
    for r in rows:
        sectors.setdefault(r["sector"], []).append(r["change_1d_pct"])
    sector_perf = [{"sector": k, "avg_change_pct": round(sum(v) / len(v), 2), "stocks": len(v)}
                   for k, v in sectors.items()]
    sector_perf.sort(key=lambda x: x["avg_change_pct"], reverse=True)

    out = {"gainers": gainers, "momentum": momentum, "most_active": active,
           "near_52w_high": high, "sector_performance": sector_perf, "market": get_market()}
    _trending_cache.update(data=out, ts=now)
    return jsonify(out)


@app.route("/api/recommendations")
def recommendations():
    """Top CANSLIM-scored stocks from the universe (heavy - uses cache)."""
    now = time.time()
    if _recommendations_cache["data"] and now - _recommendations_cache["ts"] < 900:
        return jsonify(_recommendations_cache["data"])
    market = get_market()
    benchmark = dp.get_history("^NSEI", period="1y")
    results = []
    for s in UNIVERSE[:35]:
        df = dp.get_history(s["symbol"], period="1y")
        if df is None or len(df) < 200:
            continue
        tech = indicators.technical_snapshot(df)
        fund = fundamentals.quarterly_analysis({"available": False})
        analyst = fundamentals.analyst_ratings({}, float(df["Close"].iloc[-1]))
        cns = canslim.compute_canslim({}, fund, tech, df, benchmark, market,
                                      analyst=analyst, news_count=0)
        fund_score = fundamentals.fundamental_score({}, {}, analyst)
        overall = round(0.40 * cns["overall"] + 0.30 * tech["technical_score"] + 0.30 * fund_score, 1)
        results.append({"symbol": s["symbol"], "name": s["name"], "sector": s["sector"],
                        "score": overall, "canslim": cns["overall"],
                        "verdict": cns["verdict"],
                        "price": round(float(df["Close"].iloc[-1]), 2)})
    results.sort(key=lambda r: r["score"], reverse=True)
    output = results[:12]
    _recommendations_cache.update(data=output, ts=now)
    return jsonify(output)


@app.route("/api/settings/status")
def settings_status():
    return jsonify(api_clients.credential_status())


@app.route("/api/settings", methods=["POST"])
def save_settings():
    payload = request.get_json(silent=True) or {}
    existing = api_clients.load_credentials()
    updated = {}
    for section, fields in {
        "groq": ("api_key",),
        "angel_one": ("api_key", "totp", "mpin", "client_id"),
    }.items():
        values = {}
        incoming = payload.get(section) or {}
        for field in fields:
            value = str(incoming.get(field, "")).strip()
            if value:
                values[field] = value
            elif existing.get(section, {}).get(field):
                values[field] = existing[section][field]
        updated[section] = values
    api_clients.save_credentials(updated)
    return jsonify({"message": "Credentials saved locally", "status": api_clients.credential_status()})


@app.route("/api/settings/test/<service>", methods=["POST"])
def test_settings(service):
    try:
        message = api_clients.test_groq() if service == "groq" else api_clients.test_angel_one() if service == "angel_one" else None
        if message is None:
            return jsonify({"error": "Unknown service"}), 404
        return jsonify({"message": message})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    payload = request.get_json(silent=True) or {}
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt or len(prompt) > 4000:
        return jsonify({"error": "Prompt is required and must be 4000 characters or less"}), 400
    try:
        return jsonify({"response": api_clients.groq_chat(prompt)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/")
def index():
    return send_from_directory(FRONTEND, "front.html")


@app.route("/settings")
def settings():
    return send_from_directory(FRONTEND, "settings.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)