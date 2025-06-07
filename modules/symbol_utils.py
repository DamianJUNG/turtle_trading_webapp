# modules/symbol_utils.py

from pykrx.stock import get_market_ticker_list, get_market_ticker_name
from datetime import datetime

def convert_to_tickers(inputs: list) -> dict:
    """
    사용자 입력(종목명 또는 6자리 코드) 리스트를 받아
    실제 유효 종목코드 딕셔너리로 반환.
    { code: name, ... }
    """
    today = datetime.now().strftime("%Y%m%d")
    # 코스피+코스닥 전체 티커 리스트
    kospi = get_market_ticker_list(today, market="KOSPI")
    kosdaq = get_market_ticker_list(today, market="KOSDAQ")
    all_tickers = kospi + kosdaq

    result = {}
    for item in inputs:
        s = item.strip()
        if s.isdigit() and s in all_tickers:
            # 6자리 코드 입력
            result[s] = get_market_ticker_name(s)
        else:
            # 종목명으로 검색 (부분 매칭)
            matches = [
                t for t in all_tickers
                if s.lower() in get_market_ticker_name(t).lower()
            ]
            for code in matches:
                result[code] = get_market_ticker_name(code)
    return result
