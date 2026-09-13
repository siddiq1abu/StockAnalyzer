"""
stock_news_analyzer.py  (v2 — efficient + ML-scored)

An upgrade of the original trending_news.py that:
  1. Is much faster   -> concurrent feed fetching, disk-cached NSE list,
                         a single compiled regex for company matching.
  2. Is smarter (ML)  -> a LogisticRegression sentiment model trained at
                         startup on an embedded financial-news dataset
                         (no external API / download required),
                         TF-IDF relevance scoring, and a composite
                         "Opportunity Score" that ranks the best
                         stocks AND sectors mentioned in the news.

Outputs two ranked tables:
  * TRENDING tables (raw mention frequency)  -> "what is being talked about"
  * TOP PICKS tables (ML Opportunity Score)  -> "what looks most promising"

Design notes
------------
- Sentiment model: TfidfVectorizer + LogisticRegression, trained in-memory
  on ~90 hand-labeled Indian-market-style headlines. The trained pipeline is
  cached to disk with joblib so it is trained only once.
- Opportunity Score (z-normalized features, weighted sum):
      score = 0.30 * sentiment_strength      # net bullish conviction
            + 0.25 * tfidf_relevance         # how central the stock is
            + 0.25 * source_breadth          # # independent outlets covering it
            + 0.20 * recency_weight          # freshness (half-life decay)
- Sector score = weighted average of its member-stock scores + its own
  keyword-based news volume, so sector picks are driven by both.
- Everything falls back gracefully: if sklearn is missing, a simple
  lexicon-based sentiment is used; if the NSE CSV fails, tagging is skipped.
"""

import csv
import io
import json
import os
import re
import html
import time
import pickle
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

RSS_FEEDS = {
    "Moneycontrol - Markets":  "https://www.moneycontrol.com/rss/marketreports.xml",
    "Moneycontrol - Business": "https://www.moneycontrol.com/rss/business.xml",
    "Economic Times - Markets":"https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Business Standard - Markets":"https://www.business-standard.com/rss/markets-106.rss",
    "LiveMint - Markets":      "https://www.livemint.com/rss/markets",
}

NSE_EQUITY_LIST_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EQUITY_WORKBOOK_PATH = os.path.join(PROJECT_DIR, "Data", "EQUITY_L_with_sectors.xlsx")
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "stock_news_analyzer")
NSE_CACHE_TTL_SEC = 24 * 3600          # refresh the NSE list once a day
MODEL_CACHE_PATH = os.path.join(CACHE_DIR, "sentiment_model.joblib")

LOOKBACK_HOURS = 24
HALF_LIFE_HOURS = 8.0                  # recency decay half-life
REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
MAX_WORKERS = 5                        # one thread per feed

# Composite-score weights (must sum to 1.0)
W_SENTIMENT, W_RELEVANCE, W_BREADTH, W_RECENCY = 0.30, 0.25, 0.25, 0.20

# Embedded labeled training data: (headline, label)
# label: 1 = positive for the stock/sector, -1 = negative, 0 = neutral.
# Small but finance-specific; extend FREELY to improve accuracy.
TRAINING_DATA = [
    ("stock surges after strong quarterly results", 1),
    ("shares rally on upbeat earnings beat", 1),
    ("company wins large order worth crore", 1),
    ("brokerages upgrade stock to buy, raise target", 1),
    ("board approves share buyback plan", 1),
    ("record high profit margin drives stock up", 1),
    ("firm secures multi-year contract with government", 1),
    ("sector outlook turns positive on policy support", 1),
    ("exports jump, revenue guidance raised", 1),
    ("stock hits 52 week high on volume surge", 1),
    ("credit rating upgraded on strong balance sheet", 1),
    ("promoter increases stake, signals confidence", 1),
    ("new product launch lifts sales outlook", 1),
    ("GST cut boosts auto demand, dealers upbeat", 1),
    ("RBI rate cut cheers banking stocks", 1),
    ("foreign investors turn buyers in midcaps", 1),
    ("institutional investors raise holdings", 1),
    ("company announces dividend, special payout", 1),
    ("capacity expansion to drive future growth", 1),
    ("merger synergies to unlock value, say analysts", 1),
    ("robust order book, margins improve sequentially", 1),
    ("stock tanks after weak quarterly results", -1),
    ("shares crash on profit decline miss", -1),
    ("company loses major client contract", -1),
    ("brokerages downgrade stock to sell", -1),
    ("fraud probe initiated against promoters", -1),
    ("credit rating downgraded to junk", -1),
    ("promoter pledges entire stake, stock plunges", -1),
    ("SEBI imposes penalty on company", -1),
    ("plant shut down due to regulatory action", -1),
    ("recall hits sales, outlook cut to negative", -1),
    ("debt default fears rise, lenders worried", -1),
    ("stock hits lower circuit for third day", -1),
    ("shares crash after client cancels major contract", -1),
    ("company crashes on weak quarterly numbers", -1),
    ("stock tanks as margins shrink, costs surge", -1),
    ("plunges after missing street estimates badly", -1),
    ("posts loss for second straight quarter", -1),
    ("demand slumps, dealer inventories pile up", -1),
    ("order cancellations hit revenue outlook", -1),
    ("fitch downgrades outlook to negative", -1),
    ("stock slides on promoter selling worries", -1),
    ("regulator bars company from launching products", -1),
    ("wins big order from global client, shares rally", 1),
    ("posts record sales growth in december", 1),
    ("strong q2 numbers beat street estimates", 1),
    ("shares jump after stellar quarterly performance", 1),
    ("net profit doubles, declares interim dividend", 1),
    ("company turns profitable after three quarters", 1),
    ("block deal at premium lifts sentiment", 1),
    ("ace investor buys stake, stock spikes", 1),
    ("deal wins, pipeline growth cheer investors", 1),
    ("auditor resigns citing governance issues", -1),
    ("guidance slashed, margins under pressure", -1),
    ("imports surge, domestic players hurt", -1),
    ("tax hike dampens demand in sector", -1),
    ("funds exit stock on liquidity concerns", -1),
    ("insider selling raises red flags", -1),
    ("market opens flat, indices steady", 0),
    ("top stocks to watch today in trade", 0),
    ("sensex nifty end mixed in volatile session", 0),
    ("stock trades ex-dividend today", 0),
    ("board meeting scheduled next week", 0),
    ("company files quarterly compliance report", 0),
    ("trading volume rises in afternoon session", 0),
    ("analysts await clarity on policy details", 0),
    ("results announcement date confirmed", 0),
    ("stock remains rangebound ahead of earnings", 0),
    ("investor presentation to be held tomorrow", 0),
    ("no material information to disclose", 0),
    ("week ahead: key events to track in markets", 0),
    ("bulk deals: who bought and sold what", 0),
    ("shareholding pattern filed with exchanges", 0),
    ("market holiday announced for festival", 0),
    ("IPO subscription status update", 0),
    ("commodity prices steady in early trade", 0),
]

SECTOR_KEYWORDS = {
    "Banking":   ["bank", "hdfc bank", "icici bank", "sbi", "axis bank", "kotak", "rbi", "npa", "credit growth"],
    "IT":        ["infosys", "tcs", "wipro", "hcl tech", "tech mahindra", "it stocks", "software services", "digital deal"],
    "Auto":      ["maruti", "tata motors", "bajaj auto", "hero motocorp", "eicher motors", "auto sector", "vehicle sales"],
    "Pharma":    ["pharma", "sun pharma", "cipla", "dr reddy", "drug approval", "usfda"],
    "FMCG":      ["fmcg", "hindustan unilever", "itc ", "nestle india", "britannia", "rural demand"],
    "Energy":    ["crude oil", "ongc", "reliance industries", "power sector", "renewable energy", "adani", "gas price"],
    "Metals":    ["steel", "tata steel", "jsw steel", "hindalco", "metal stocks", "iron ore", "aluminium"],
    "Realty":    ["realty", "real estate", "dlf", "godrej properties", "housing sales"],
}

# Manual symbol -> sector map (only for sector aggregation of top picks;
# full list would be too long to maintain — extend as needed).
SYMBOL_SECTOR = {
    "RELIANCE": "Energy", "ONGC": "Energy", "ADANIENT": "Energy", "ADANIPORTS": "Energy",
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "AXISBANK": "Banking",
    "KOTAKBANK": "Banking", "INDUSINDBK": "Banking", "PNB": "Banking", "BANKBARODA": "Banking",
    "INFY": "IT", "TCS": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT", "LTIM": "IT",
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "BAJAJ-AUTO": "Auto", "HEROMOTOCO": "Auto",
    "EICHERMOT": "Auto", "M&M": "Auto", "TVSMOTOR": "Auto",
    "SUNPHARMA": "Pharma", "CIPLA": "Pharma", "DRREDDY": "Pharma", "DIVISLAB": "Pharma",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals", "JINDALSTEL": "Metals",
    "DLF": "Realty", "GODREJPROP": "Realty", "OBEROIRLTY": "Realty",
}

# Fallback lexicon (used only if scikit-learn is unavailable)
POS_LEX = ("surge rally beat win wins won upgrade upgrade upgraded buyout buyback "
           "growth profit record high boost upside confident").split()
NEG_LEX = ("crash tank plunge plunge fall miss downgrade downgrade fraud probe penalty "
           "default shut recall junk resign resigns exit cut cuts weak loss").split()

HTML_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# 1. Caching utilities
# ---------------------------------------------------------------------------

def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _xlsx_cell_value(cell, shared_strings):
    value = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    if value is not None:
        text = value.text or ""
        if cell.attrib.get("t") == "s":
            return shared_strings[int(text)]
        return text
    inline = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
    return "".join(inline.itertext()) if inline is not None else ""


def load_nse_symbols_from_workbook():
    """Load {company_name_lower: symbol} from the project's NSE workbook."""
    if not os.path.exists(EQUITY_WORKBOOK_PATH):
        return {}

    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    try:
        with zipfile.ZipFile(EQUITY_WORKBOOK_PATH) as workbook:
            shared_strings = []
            if "xl/sharedStrings.xml" in workbook.namelist():
                shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
                shared_strings = ["".join(item.itertext())
                                  for item in shared_root.findall(f"{{{main_ns}}}si")]

            workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
            rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            relationships = {rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
                            for rel in rel_root.findall(f"{{{rel_ns}}}Relationship")}
            first_sheet = workbook_root.find(f"{{{main_ns}}}sheets/{{{main_ns}}}sheet")
            target = relationships[first_sheet.attrib[f"{{{office_rel_ns}}}id"]]
            target = target if target.startswith("xl/") else f"xl/{target}"
            sheet_root = ET.fromstring(workbook.read(target))
            rows = sheet_root.findall(f".//{{{main_ns}}}sheetData/{{{main_ns}}}row")

            if not rows:
                return {}
            headers = {}
            for cell in rows[0].findall(f"{{{main_ns}}}c"):
                headers[cell.attrib.get("r", "A1").rstrip("0123456789")] = _xlsx_cell_value(
                    cell, shared_strings).strip().upper()
            symbol_col = next(col for col, value in headers.items() if value == "SYMBOL")
            name_col = next(col for col, value in headers.items() if value == "NAME OF COMPANY")

            symbol_map = {}
            for row in rows[1:]:
                values = {cell.attrib.get("r", "A1").rstrip("0123456789"): _xlsx_cell_value(
                    cell, shared_strings).strip() for cell in row.findall(f"{{{main_ns}}}c")}
                name, symbol = values.get(name_col, ""), values.get(symbol_col, "")
                if name and symbol:
                    symbol_map[name.lower()] = symbol
            return symbol_map
    except (KeyError, OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"[warn] Equity workbook unavailable ({exc}); trying NSE CSV.")
        return {}


def load_nse_symbols():
    """{company_name_lower: symbol} map from the project workbook, with CSV fallback."""
    workbook_symbols = load_nse_symbols_from_workbook()
    if workbook_symbols:
        return workbook_symbols

    _ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, "nse_equity_list.json")
    if os.path.exists(cache_file):
        age = time.time() - os.path.getmtime(cache_file)
        if age < NSE_CACHE_TTL_SEC:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    return data
            except (json.JSONDecodeError, OSError):
                pass

    symbol_map = {}
    try:
        resp = requests.get(NSE_EQUITY_LIST_URL,
                            headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        for row in csv.DictReader(io.StringIO(resp.text)):
            name = (row.get("NAME OF COMPANY") or "").strip()
            symbol = (row.get("SYMBOL") or "").strip()
            if name and symbol:
                symbol_map[name.lower()] = symbol
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(symbol_map, f)
    except Exception as e:
        print(f"[warn] NSE symbol list unavailable ({e}); stock tagging limited.")

    return symbol_map


def compile_company_matcher(symbol_map):
    """
    Build ONE compiled regex that matches any company name.
    This replaces the original O(articles x companies) substring loop
    with a single linear pass per article. Returns (pattern, name_map).
    """
    # sort by length desc so 'reliance industries ltd' wins over 'reliance'
    names = sorted((n for n in symbol_map if len(n) > 3), key=len, reverse=True)
    if not names:
        return None, {}
    pattern = re.compile("|".join(re.escape(n) for n in names))
    return pattern, symbol_map


# ---------------------------------------------------------------------------
# 2. Fetch latest news concurrently
# ---------------------------------------------------------------------------

def parse_pub_date(entry):
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if getattr(entry, "updated_parsed", None):
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return None


def clean_text(raw):
    raw = HTML_TAG_RE.sub(" ", raw or "")
    return html.unescape(WS_RE.sub(" ", raw)).strip()


def _fetch_feed(source, url, cutoff):
    """Fetch one feed; returns list of deduped, fresh items."""
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"[warn] {source}: fetch failed ({e})")
        return []
    items = []
    for entry in feed.entries:
        pub_date = parse_pub_date(entry)
        if pub_date is None or pub_date < cutoff:
            continue  # not "latest" -- skip stale or undated items
        items.append({
            "source": source,
            "title": clean_text(entry.get("title")),
            "summary": clean_text(entry.get("summary")),
            "link": entry.get("link", ""),
            "published": pub_date,
        })
    return items


def fetch_latest_news(lookback_hours=LOOKBACK_HOURS):
    """Fetch all feeds in parallel and dedupe by canonical link."""
    if not HAS_FEEDPARSER:
        raise RuntimeError("feedparser is required: pip install feedparser")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    items, seen_links = [], set()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_feed, src, url, cutoff): src
                   for src, url in RSS_FEEDS.items()}
        for fut in as_completed(futures):
            for item in fut.result():
                link = item["link"]
                if link and link in seen_links:
                    continue
                if link:
                    seen_links.add(link)
                items.append(item)

    items.sort(key=lambda x: x["published"], reverse=True)
    return items


# ---------------------------------------------------------------------------
# 3. ML: train (or load) the sentiment model
# ---------------------------------------------------------------------------

def train_sentiment_model():
    """
    Train TfidfVectorizer + LogisticRegression on the embedded labeled
    headlines. The fitted pipeline is cached to disk so it is trained
    only once. Extend TRAINING_DATA above to improve accuracy.
    """
    _ensure_cache_dir()
    if os.path.exists(MODEL_CACHE_PATH):
        try:
            with open(MODEL_CACHE_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass

    if not HAS_SKLEARN:
        return None

    X = [t for t, _ in TRAINING_DATA]
    y = [l for _, l in TRAINING_DATA]
    model = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(C=2.0, max_iter=1000)),
    ])
    model.fit(X, y)
    with open(MODEL_CACHE_PATH, "wb") as f:
        pickle.dump(model, f)
    return model


def sentiment_score(text, model):
    """Return polarity in [-1, 1] using the trained model (or lexicon fallback)."""
    if model is not None:
        proba = model.predict_proba([text])[0]      # order of classes: -1, 0, 1
        classes = list(model.classes_)
        return proba[classes.index(1)] - proba[classes.index(-1)]
    toks = set(re.findall(r"[a-z]+", text.lower()))
    pos, neg = len(toks & set(POS_LEX)), len(toks & set(NEG_LEX))
    return (pos - neg) / max(pos + neg, 1)


# ---------------------------------------------------------------------------
# 4. Tag + enrich news
# ---------------------------------------------------------------------------

def tag_stocks(text, company_pattern, symbol_map):
    if company_pattern is None:
        return set()
    return {symbol_map[m.group(0).lower()] for m in company_pattern.finditer(text.lower())}


def tag_sectors(text):
    text_l = text.lower()
    return {s for s, kws in SECTOR_KEYWORDS.items() if any(k in text_l for k in kws)}


def enrich_news(items, company_pattern, symbol_map, model):
    """Add stocks, sectors, sentiment and recency weight to every item."""
    now = datetime.now(timezone.utc)
    for item in items:
        full = f"{item['title']} {item['summary']}"
        item["stocks"] = tag_stocks(full, company_pattern, symbol_map)
        item["sectors"] = tag_sectors(full)
        item["sentiment"] = sentiment_score(full, model)
        age_h = (now - item["published"]).total_seconds() / 3600.0
        item["recency"] = 0.5 ** (age_h / HALF_LIFE_HOURS)   # half-life decay
    return items


# ---------------------------------------------------------------------------
# 5. Ranking: trending tables + ML Opportunity Score
# ---------------------------------------------------------------------------

def zscore(values):
    n = len(values)
    if n < 2:
        return [0.0] * n
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    sd = var ** 0.5
    return [0.0 if sd == 0 else (v - mean) / sd for v in values]


def rank_stocks(items, top_n=10):
    """
    Build per-stock feature vectors:
      sentiment_strength = sum(sentiment * recency)        -> directional conviction
      tfidf_relevance    = mean TF-IDF norm of matched docs -> centrality in news
      source_breadth     = # independent outlets mentioning it
      recency_weight     = max recency (most recent mention)
    Then z-normalize and combine into an Opportunity Score.
    Returns ranked list of dicts.
    """
    by_stock = defaultdict(list)
    for item in items:
        for sym in item["stocks"]:
            by_stock[sym].append(item)

    if not by_stock:
        return []

    # TF-IDF relevance: how informative each matched article is
    docs = ["%s %s" % (i["title"], i["summary"]) for i in items]
    if HAS_SKLEARN and docs:
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit(docs)
        norms = [float(v.sum()) for v in vec.transform(docs)]  # per-doc TF-IDF mass
    else:
        norms = [1.0] * len(items)
    id2norm = {id(i): n for i, n in zip(items, norms)}

    symbols = list(by_stock)
    sent, rel, breadth, rec = [], [], [], []
    for sym in symbols:
        arts = by_stock[sym]
        sent.append(sum(a["sentiment"] * a["recency"] for a in arts))
        rel.append(sum(id2norm[id(a)] for a in arts) / len(arts))
        breadth.append(len({a["source"] for a in arts}))
        rec.append(max(a["recency"] for a in arts))

    zs, zr, zb, zc = zscore(sent), zscore(rel), zscore(breadth), zscore(rec)
    ranked = []
    for i, sym in enumerate(symbols):
        score = (W_SENTIMENT * zs[i] + W_RELEVANCE * zr[i]
                 + W_BREADTH * zb[i] + W_RECENCY * zc[i])
        ranked.append({
            "symbol": sym,
            "score": round(score, 3),
            "mentions": len(by_stock[sym]),
            "net_sentiment": round(sum(a["sentiment"] for a in by_stock[sym]), 2),
            "sources": sorted({a["source"] for a in by_stock[sym]}),
            "latest": max(a["published"] for a in by_stock[sym]),
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:top_n]


def rank_sectors(items, stock_rank, top_n=8):
    """
    Sector score = mean member-stock Opportunity Score (if mapped)
                   + z-normalized keyword-mention volume + mean sentiment.
    Falls back to keyword volume alone for sectors with no mapped stocks.
    """
    sec_volume = Counter()
    sec_sent = defaultdict(list)
    for item in items:
        for sec in item["sectors"]:
            sec_volume[sec] += 1
            sec_sent[sec].append(item["sentiment"])

    member_scores = defaultdict(list)
    for r in stock_rank:
        sec = SYMBOL_SECTOR.get(r["symbol"])
        if sec:
            member_scores[sec].append(r["score"])

    secs = set(sec_volume) | set(member_scores)
    if not secs:
        return []

    vol = zscore([sec_volume.get(s, 0) for s in secs])
    mem = zscore([sum(member_scores.get(s, [0.0])) for s in secs])
    sen = zscore([sum(sec_sent.get(s, [0.0])) / max(len(sec_sent.get(s, [1])), 1) for s in secs])

    ranked = []
    for i, sec in enumerate(secs):
        score = 0.45 * vol[i] + 0.35 * mem[i] + 0.20 * sen[i]
        ranked.append({
            "sector": sec,
            "score": round(score, 3),
            "mentions": sec_volume.get(sec, 0),
            "avg_sentiment": round(sum(sec_sent.get(sec, [0.0])) / max(len(sec_sent.get(sec, [1])), 1), 2),
            "top_stocks": [r["symbol"] for r in stock_rank if SYMBOL_SECTOR.get(r["symbol"]) == sec][:3],
        })
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:top_n]


def get_trending(items, top_n=10):
    stock_counter, sector_counter = Counter(), Counter()
    for item in items:
        stock_counter.update(item["stocks"])
        sector_counter.update(item["sectors"])
    return stock_counter.most_common(top_n), sector_counter.most_common(top_n)


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print(f"Fetching news from the last {LOOKBACK_HOURS}h "
          f"across {len(RSS_FEEDS)} sources...\n")

    symbol_map = load_nse_symbols()
    pattern, name_map = compile_company_matcher(symbol_map)
    model = train_sentiment_model()
    if model is not None:
        print("Sentiment model: trained LogisticRegression (cached).")
    else:
        print("Sentiment model: lexicon fallback (install scikit-learn for ML).")

    news = fetch_latest_news()
    news = enrich_news(news, pattern, name_map, model)

    print(f"Found {len(news)} latest items in {time.time()-t0:.1f}s.\n")
    print("=" * 72)
    print("LATEST NEWS (with tags + sentiment)")
    print("=" * 72)
    for item in news[:15]:
        st = ", ".join(sorted(item["stocks"])) or "-"
        sc = ", ".join(sorted(item["sectors"])) or "-"
        print(f"[{item['published'].strftime('%Y-%m-%d %H:%M UTC')}] ({item['source']})")
        print(f"  {item['title']}")
        print(f"  Stocks: {st} | Sectors: {sc} | Sentiment: {item['sentiment']:+.2f}")
        print(f"  {item['link']}\n")

    trending_stocks, trending_sectors = get_trending(news)
    print("=" * 72)
    print("TRENDING (raw mention frequency)")
    print("=" * 72)
    print("  Stocks:  " + (", ".join(f"{s}({c})" for s, c in trending_stocks) or "none"))
    print("  Sectors: " + (", ".join(f"{s}({c})" for s, c in trending_sectors) or "none") + "\n")

    picks = rank_stocks(news)
    print("=" * 72)
    print("TOP STOCK PICKS (ML Opportunity Score)")
    print("=" * 72)
    if picks:
        for i, r in enumerate(picks, 1):
            print(f"  {i:>2}. {r['symbol']:<14} score={r['score']:+.2f} "
                  f"mentions={r['mentions']} net_sent={r['net_sentiment']:+.2f} "
                  f"latest={r['latest'].strftime('%H:%M UTC')}")
    else:
        print("  No specific stocks matched in this window.")

    sectors = rank_sectors(news, picks)
    print()
    print("=" * 72)
    print("TOP SECTOR PICKS (ML-weighted)")
    print("=" * 72)
    if sectors:
        for i, r in enumerate(sectors, 1):
            print(f"  {i:>2}. {r['sector']:<10} score={r['score']:+.2f} "
                  f"mentions={r['mentions']} avg_sent={r['avg_sentiment']:+.2f} "
                  f"stocks={', '.join(r['top_stocks']) or '-'}")
    else:
        print("  No sector keywords matched in this window.")

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    main()