"""Live data fetcher using yfinance for IDX Bot Engine."""

import yfinance as yf
from analyzer import CompanyProfile, FinancialData, PortfolioContext

def fetch_live_profile(ticker: str, available_cash: float = 100_000_000.0) -> CompanyProfile:
    """Fetches real-time data from Yahoo Finance and maps it to CompanyProfile."""
    if not ticker.endswith(".JK"):
        ticker += ".JK"
        
    stock = yf.Ticker(ticker)
    info = stock.info
    
    # Extract fundamentals safely
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
    if current_price == 0:
        raise ValueError(f"Ticker {ticker} tidak ditemukan atau tidak ada data harga.")
        
    market_cap = info.get("marketCap", 0.0)
    avg_vol = info.get("averageVolume", 0.0)
    turnover = avg_vol * current_price
    
    # Financial metrics
    pe = info.get("trailingPE")
    pbv = info.get("priceToBook")
    roe = (info.get("returnOnEquity") or 0) * 100
    roa = (info.get("returnOnAssets") or 0) * 100
    der = info.get("debtToEquity")
    if der is not None:
        der = der / 100.0  # yfinance returns DER in % sometimes, normalise to ratio
        
    npm = (info.get("profitMargins") or 0) * 100
    rev_growth = (info.get("revenueGrowth") or 0) * 100
    net_growth = (info.get("earningsGrowth") or 0) * 100
    
    eps = info.get("trailingEps")
    bvps = info.get("bookValue")
    
    fcf = info.get("freeCashflow", 1)  # Default assume positive if missing in yf
    fcf_positive = fcf > 0
    
    fin_data = FinancialData(
        pe_ratio=pe,
        pbv_ratio=pbv,
        roe_percentage=roe,
        roa_percentage=roa,
        der_ratio=der,
        npm_percentage=npm,
        revenue_yoy_growth=rev_growth,
        net_income_yoy_growth=net_growth,
        fcf_positive=fcf_positive,
        eps=eps,
        bvps=bvps
    )
    
    sector = info.get("sector", "Unknown")
    
    return CompanyProfile(
        ticker=ticker,
        company_name=info.get("longName", ticker),
        sector=sector,
        current_price=current_price,
        market_cap_idr=market_cap,
        average_daily_turnover_idr=turnover,
        financials=fin_data,
        portfolio_context=PortfolioContext(available_cash_idr=available_cash)
    )
