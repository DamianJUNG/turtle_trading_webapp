# modules/financial_filter.py

from pykrx.stock import get_financial_statement_by_date
from datetime import datetime

def get_latest_roa(ticker: str) -> float:
    """
    최근 분기 재무제표에서 ROA(당기순이익/자산총계*100)를 계산하여 반환.
    실패 시 None 반환.
    """
    try:
        today = datetime.today()
        # 연초부터 상반기·하반기 구분 없이 최근까지 조회
        start_date = f"{today.year}0101"
        end_date   = f"{today.year}{today.month:02d}{today.day:02d}"
        fs = get_financial_statement_by_date(start_date, end_date, ticker)

        net_income   = fs.loc["당기순이익"].dropna().iloc[-1]
        total_assets = fs.loc["자산총계"].dropna().iloc[-1]

        roa = (net_income / total_assets) * 100
        return round(roa, 2)
    except Exception:
        return None

def filter_by_roa(ticker_dict: dict, threshold: float) -> dict:
    """
    ticker_dict: {code: name, ...}
    threshold: ROA 최소 기준(%)
    반환: ROA >= threshold인 종목만 {"code": {"name":..., "roa":...}, ...}
    """
    passed = {}
    for code, name in ticker_dict.items():
        roa = get_latest_roa(code)
        if roa is not None and roa >= threshold:
            passed[code] = {"name": name, "roa": roa}
    return passed
