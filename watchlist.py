"""Simple JSON file-backed watchlist for IDX Bot."""

import json
from pathlib import Path
from typing import List

_FILE = Path("watchlist.json")


def load() -> List[dict]:
    return json.loads(_FILE.read_text(encoding="utf-8")) if _FILE.exists() else []


def add(ticker: str, company_name: str = "") -> List[dict]:
    wl = load()
    t = ticker.upper().replace(".JK", "")
    if not any(w["ticker"] == t for w in wl):
        wl.append({"ticker": t, "company_name": company_name})
        _FILE.write_text(json.dumps(wl, indent=2, ensure_ascii=False), encoding="utf-8")
    return wl


def remove(ticker: str) -> List[dict]:
    t = ticker.upper().replace(".JK", "")
    wl = [w for w in load() if w["ticker"] != t]
    _FILE.write_text(json.dumps(wl, indent=2, ensure_ascii=False), encoding="utf-8")
    return wl


def tickers() -> List[str]:
    return [w["ticker"] for w in load()]
