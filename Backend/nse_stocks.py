"""Curated analysis universe and workbook-backed NSE search universe."""
import os
import zipfile
import xml.etree.ElementTree as ET


PROJECT_WORKBOOK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Data", "EQUITY_L_with_sectors.xlsx")


UNIVERSE = [
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries", "sector": "Energy"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank", "sector": "Banking"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank", "sector": "Banking"},
    {"symbol": "INFY.NS", "name": "Infosys", "sector": "IT"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever", "sector": "FMCG"},
    {"symbol": "ITC.NS", "name": "ITC", "sector": "FMCG"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel", "sector": "Telecom"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank", "sector": "Banking"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro", "sector": "Infrastructure"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank", "sector": "Banking"},
    {"symbol": "ASIANPAINT.NS", "name": "Asian Paints", "sector": "Consumer"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki", "sector": "Auto"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharma", "sector": "Pharma"},
    {"symbol": "TITAN.NS", "name": "Titan Company", "sector": "Consumer"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement", "sector": "Cement"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance", "sector": "NBFC"},
    {"symbol": "WIPRO.NS", "name": "Wipro", "sector": "IT"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra", "sector": "Auto"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies", "sector": "IT"},
    {"symbol": "NTPC.NS", "name": "NTPC", "sector": "Power"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corp", "sector": "Power"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors", "sector": "Auto"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel", "sector": "Metals"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises", "sector": "Diversified"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports", "sector": "Infrastructure"},
    {"symbol": "COALINDIA.NS", "name": "Coal India", "sector": "Metals"},
    {"symbol": "ONGC.NS", "name": "Oil & Natural Gas Corp", "sector": "Energy"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel", "sector": "Metals"},
    {"symbol": "HINDZINC.NS", "name": "Hindustan Zinc", "sector": "Metals"},
    {"symbol": "DMART.NS", "name": "Avenue Supermarts", "sector": "Retail"},
    {"symbol": "BAJAJAUTO.NS", "name": "Bajaj Auto", "sector": "Auto"},
    {"symbol": "NESTLEIND.NS", "name": "Nestle India", "sector": "FMCG"},
    {"symbol": "BRITANNIA.NS", "name": "Britannia Industries", "sector": "FMCG"},
    {"symbol": "CIPLA.NS", "name": "Cipla", "sector": "Pharma"},
    {"symbol": "DRREDDY.NS", "name": "Dr Reddy's Labs", "sector": "Pharma"},
    {"symbol": "EICHERMOT.NS", "name": "Eicher Motors", "sector": "Auto"},
    {"symbol": "HEROMOTOCO.NS", "name": "Hero MotoCorp", "sector": "Auto"},
    {"symbol": "TVSMOTOR.NS", "name": "TVS Motor", "sector": "Auto"},
    {"symbol": "PIDILITIND.NS", "name": "Pidilite Industries", "sector": "Chemicals"},
    {"symbol": "DIVISLAB.NS", "name": "Divi's Labs", "sector": "Pharma"},
    {"symbol": "ZOMATO.NS", "name": "Zomato (Eternal)", "sector": "Tech"},
    {"symbol": "PAYTM.NS", "name": "One97 Communications", "sector": "Fintech"},
    {"symbol": "IRCTC.NS", "name": "IRCTC", "sector": "Consumer"},
    {"symbol": "HAL.NS", "name": "Hindustan Aeronautics", "sector": "Defence"},
    {"symbol": "BEL.NS", "name": "Bharat Electronics", "sector": "Defence"},
    {"symbol": "BHEL.NS", "name": "Bharat Heavy Electricals", "sector": "Capital Goods"},
    {"symbol": "SIEMENS.NS", "name": "Siemens India", "sector": "Capital Goods"},
    {"symbol": "ABB.NS", "name": "ABB India", "sector": "Capital Goods"},
    {"symbol": "GODREJCP.NS", "name": "Godrej Consumer", "sector": "FMCG"},
    {"symbol": "DABUR.NS", "name": "Dabur India", "sector": "FMCG"},
    {"symbol": "COLPAL.NS", "name": "Colgate-Palmolive India", "sector": "FMCG"},
    {"symbol": "TECHM.NS", "name": "Tech Mahindra", "sector": "IT"},
    {"symbol": "LTIM.NS", "name": "LTIMindtree", "sector": "IT"},
    {"symbol": "MINDTREE.NS", "name": "Mindtree (LTIM)", "sector": "IT"},
    {"symbol": "PERSISTENT.NS", "name": "Persistent Systems", "sector": "IT"},
    {"symbol": "COFORGE.NS", "name": "Coforge", "sector": "IT"},
    {"symbol": "MPHASIS.NS", "name": "Mphasis", "sector": "IT"},
    {"symbol": "POLYCAB.NS", "name": "Polycab India", "sector": "Consumer"},
    {"symbol": "KEI.NS", "name": "KEI Industries", "sector": "Capital Goods"},
    {"symbol": "HAVELLS.NS", "name": "Havells India", "sector": "Consumer"},
    {"symbol": "VOLTAS.NS", "name": "Voltas", "sector": "Consumer"},
    {"symbol": "INDIGO.NS", "name": "InterGlobe Aviation", "sector": "Aviation"},
    {"symbol": "IRFC.NS", "name": "Indian Railway Finance", "sector": "NBFC"},
    {"symbol": "RVNL.NS", "name": "Rail Vikas Nigam", "sector": "Infrastructure"},
    {"symbol": "JIOFIN.NS", "name": "Jio Financial Services", "sector": "NBFC"},
    {"symbol": "IDEA.NS", "name": "Vodafone Idea", "sector": "Telecom"},
    {"symbol": "PNB.NS", "name": "Punjab National Bank", "sector": "Banking"},
    {"symbol": "BANKBARODA.NS", "name": "Bank of Baroda", "sector": "Banking"},
    {"symbol": "CANBK.NS", "name": "Canara Bank", "sector": "Banking"},
    {"symbol": "YESBANK.NS", "name": "Yes Bank", "sector": "Banking"},
    {"symbol": "IDEA.NS", "name": "Vodafone Idea", "sector": "Telecom"},
    {"symbol": "AUROPHARMA.NS", "name": "Aurobindo Pharma", "sector": "Pharma"},
    {"symbol": "LUPIN.NS", "name": "Lupin", "sector": "Pharma"},
    {"symbol": "GLENMARK.NS", "name": "Glenmark Pharma", "sector": "Pharma"},
    {"symbol": "TRENT.NS", "name": "Trent (Tata)", "sector": "Retail"},
    {"symbol": "PAGEIND.NS", "name": "Page Industries", "sector": "Consumer"},
]


def _load_search_universe():
    """Load all searchable NSE companies from the project workbook."""
    if not os.path.exists(PROJECT_WORKBOOK):
        return UNIVERSE

    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    try:
        with zipfile.ZipFile(PROJECT_WORKBOOK) as workbook:
            workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
            rel_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
            relationships = {rel.attrib["Id"]: rel.attrib["Target"].lstrip("/")
                            for rel in rel_root.findall(f"{{{rel_ns}}}Relationship")}
            sheet = workbook_root.find(f"{{{ns}}}sheets/{{{ns}}}sheet")
            target = relationships[sheet.attrib[f"{{{office_rel_ns}}}id"]]
            target = target if target.startswith("xl/") else f"xl/{target}"
            root = ET.fromstring(workbook.read(target))
            rows = root.findall(f".//{{{ns}}}sheetData/{{{ns}}}row")
            if not rows:
                return UNIVERSE

            def cell_text(cell):
                inline = cell.find(f"{{{ns}}}is")
                return "".join(inline.itertext()).strip() if inline is not None else ""

            headers = {}
            for cell in rows[0].findall(f"{{{ns}}}c"):
                column = cell.attrib.get("r", "A1").rstrip("0123456789")
                headers[column] = cell_text(cell).upper()
            symbol_col = next(col for col, value in headers.items() if value == "SYMBOL")
            name_col = next(col for col, value in headers.items() if value == "NAME OF COMPANY")
            sector_col = next(col for col, value in headers.items() if value == "SECTOR")

            result = []
            for row in rows[1:]:
                values = {cell.attrib.get("r", "A1").rstrip("0123456789"): cell_text(cell)
                          for cell in row.findall(f"{{{ns}}}c")}
                symbol, name = values.get(symbol_col, ""), values.get(name_col, "")
                if symbol and name:
                    result.append({
                        "symbol": f"{symbol}.NS",
                        "name": name,
                        "sector": values.get(sector_col, "Unclassified") or "Unclassified",
                    })
            return result or UNIVERSE
    except (KeyError, OSError, ValueError, ET.ParseError, zipfile.BadZipFile):
        return UNIVERSE


SEARCH_UNIVERSE = _load_search_universe()