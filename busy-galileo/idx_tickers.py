"""Dynamic IDX ticker list fetcher — pulls live securities list from IDX public API."""

import random
import time
import requests
from typing import List

_TRENDING_POOL = [
    # Saham lapis 1 & lapis 2 yang paling sering ditransaksikan (high liquidity/volatile)
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "GOTO", "AMMN", 
    "BREN", "CUAN", "PANI", "BRPT", "TPIA", "PGEO", "ADRO", "ITMG", 
    "PTBA", "UNTR", "MEDC", "MDKA", "MBMA", "ANTM", "INCO", "INKP",
    "TKIM", "ICBP", "INDF", "UNVR", "MYOR", "CPIN", "JPFA", "KLBF"
]

# Expanded fallback pool of 150+ IDX tickers spanning all sectors.
# Used when IDX's public API is blocked (common — IDX doesn't publish an open REST API).
# Random sampling from this pool on every call ensures "always changing" behavior.
_FALLBACK_POOL = [
    # Perbankan & Keuangan
    "BNGA", "BDMN", "BJBR", "NISP", "PNBN", "MEGA", "BNII", "BJTM", "NAGA",
    "AGRO", "BBMD", "BMAS", "BSIM", "BTPN", "PNLF", "ADMF", "BFIN", "TRIM",
    # Barang Konsumsi / FMCG
    "MYOR", "DLTA", "ULTJ", "WIIM", "SKBM", "ROTI", "GOOD", "KINO", "MLBI",
    "CLEO", "ALTO", "ICBP", "UNVR", "HOKI", "DMND", "SKLT", "AISA", "LMSH",
    # Infrastruktur, Utilitas & Transportasi
    "TBIG", "ISAT", "FREN", "LINK", "EXCL", "SMDR", "BIRD", "SAFE", "JSMR",
    "BALI", "BULL", "NELY", "TMAS", "PPRE", "META",
    # Energi, Pertambangan & Sumber Daya Alam
    "INDY", "ESSA", "TINS", "HRUM", "MBMA", "BUMI", "ITMG", "GEMS", "DOID",
    "CTTH", "MYOH", "SMMT", "PTBA", "ITMG", "ADRO", "MEDC", "ELSA", "RUIS",
    "ENRG", "BIPI", "APEX",
    # Properti & Real Estate
    "CTRA", "BSDE", "PWON", "DMAS", "SMRA", "LPKR", "ASRI", "BKSL", "KIJA",
    "GPRA", "MDLN", "NIRO", "COWL", "BCIP", "PPRO", "SMDM", "EMDE",
    # Industri & Manufaktur
    "ARNA", "INTP", "SMSM", "JPFA", "WOOD", "TPIA", "KRAS", "ISSP", "ALKA",
    "LION", "NIKL", "BAJA", "GDST", "JKSW", "MLIA", "AMFG", "IKAI", "SPMA",
    "KDSI", "FASW", "INKP", "TKIM", "ASII", "SRIL", "STAR", "PBRX", "RICY",
    # Kesehatan & Farmasi
    "MIKA", "SILO", "PRDA", "PEHA", "KAEF", "KLBF", "PYFA", "IRRA", "SIDO",
    "TSPC", "DVLA", "MERK", "INAF", "HEAL",
    # Ritel & Perdagangan
    "RALS", "LPPF", "CSAP", "HERO", "ACES", "MAPI", "MPPA", "KOIN", "MIDI",
    "RANC", "DIGI",
    # Agribisnis & Perkebunan
    "AALI", "SIMP", "SSMS", "LSIP", "TBLA", "SGRO", "PALM", "ANJT", "GZCO",
    # Teknologi & Media
    "GOTO", "BUKA", "MDKA", "DMMX", "MTDL", "MLPT", "ATIC", "ARNA",
    # Konstruksi
    "ADHI", "PTPP", "WSKT", "WEGE", "WIKA", "NRCA", "PBSA", "TOTL",
]
# Deduplicate while preserving order
_FALLBACK_POOL = list(dict.fromkeys(_FALLBACK_POOL))


# Simple in-memory cache: (timestamp_fetched, list_of_tickers)
_cache: tuple = (0.0, [])
_CACHE_TTL = 3600  # 1 hour


def _fetch_from_idx() -> list[str]:
    """
    Tries multiple known IDX public endpoints in order.
    Returns flat list of stock codes (e.g. ['BBCA', 'TLKM', ...]).
    Raises ValueError if all endpoints fail.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.idx.co.id/",
        "Origin": "https://www.idx.co.id",
    }

    attempts = [
        # IDX main API (newer endpoint)
        ("GET", "https://www.idx.co.id/api/v1/company_securities", {"pageSize": 9999, "pageNumber": 1}),
        # IDX Umbraco legacy surface API (still active on some mirrors)
        ("GET", "https://www.idx.co.id/umbraco/Surface/StockData/GetSecuritiesStock", {"start": 0, "length": 9999, "code": "", "name": "", "catid": "0"}),
        # IDX new data API
        ("GET", "https://api-new.mostaccess.co.id/api/v1/issuers", {"limit": 9999, "page": 1}),
    ]

    for method, url, params in attempts:
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            body = resp.json()
            # Handle different response shapes across endpoints
            items = (
                body.get("data", {}).get("securities")
                or body.get("data", {}).get("data")
                or body.get("data")
                or body.get("result")
                or (body if isinstance(body, list) else [])
            )
            codes = []
            for item in (items or []):
                code = (
                    item.get("StockCode") or item.get("stock_code")
                    or item.get("code") or item.get("Code")
                    or item.get("kodeEmiten") or ""
                ).strip().upper()
                if code:
                    codes.append(code)
            if len(codes) > 50:
                return codes
        except Exception:
            continue

    raise ValueError("All IDX API endpoints returned no usable data")


def get_all_idx_tickers() -> List[str]:
    """Returns full IDX ticker list from cache or live API, falling back to curated pool."""
    global _cache
    now = time.time()
    if now - _cache[0] < _CACHE_TTL and _cache[1]:
        return _cache[1]

    try:
        tickers = _fetch_from_idx()
        if len(tickers) > 50:  # sanity check — IDX has 800+ stocks
            # Strip warrants (W suffix), rights (R suffix), prefer 4-char codes
            tickers = [
                t for t in tickers
                if t and not t.endswith("W") and not t.endswith("R") and len(t) <= 4
            ]
            _cache = (now, tickers)
            return tickers
    except Exception:
        pass

    # Fallback: use curated pool (cached with short TTL to retry real API later)
    _cache = (now - _CACHE_TTL + 300, _FALLBACK_POOL)  # retry in 5 min
    return _FALLBACK_POOL


def get_dynamic_gems(exclude: List[str], n: int = 25) -> List[str]:
    """
    Returns n randomly sampled IDX tickers NOT in the exclude list (e.g. LQ45).
    Each call returns a different random selection from the full IDX universe.
    """
    all_tickers = get_all_idx_tickers()
    exclude_set = set(t.upper().replace(".JK", "") for t in exclude)
    candidates = [t for t in all_tickers if t.upper() not in exclude_set]
    if not candidates:
        return _FALLBACK_POOL[:n]
    return random.sample(candidates, min(n, len(candidates)))


def get_trending(n: int = 15) -> List[str]:
    """Returns a random selection of highly active/trending stocks."""
    return random.sample(_TRENDING_POOL, min(n, len(_TRENDING_POOL)))


def cache_status() -> dict:
    """Returns cache metadata for API transparency."""
    age = int(time.time() - _cache[0]) if _cache[0] else -1
    return {
        "total_tickers_cached": len(_cache[1]),
        "cache_age_seconds": age,
        "source": "IDX API" if len(_cache[1]) > len(_FALLBACK_POOL) else "Fallback Pool",
    }
