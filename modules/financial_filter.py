# modules/financial_filter.py

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pykrx.stock import (
    get_market_fundamental_by_date,
    get_market_ticker_name
)

def get_latest_roa(symbol: str, ref_date: Optional[str] = None) -> Optional[float]:
    """
    종목(symbol)의 최신 ROA 값을 반환한다.
    ref_date: 'YYYYMMDD' 형식. None이면 오늘 날짜 기준.
    """
    if ref_date is None:
        ref_date = datetime.today().strftime("%Y%m%d")
    try:
        # 해당 일자 재무지표(ROA 등) 조회
        df = get_market_fundamental_by_date(ref_date, ref_date, symbol)
    except Exception:
        return None

    # 결과 DataFrame에 ROA 컬럼이 없다면 None 반환
    if df.empty or 'ROA' not in df.columns:
        return None

    # 마지막(해당일) 행의 ROA 값 추출
    roa = df['ROA'].iloc[-1]
    try:
        return float(roa)
    except Exception:
        return None

def filter_by_roa(
    tickers: List[str],
    threshold: float
) -> Dict[str, str]:
    """
    종목 리스트(tickers)에서 ROA >= threshold인 종목만 필터링하여
    {ticker: 종목명} 형태의 dict로 반환한다.
    """
    passed: Dict[str, str] = {}
    for t in tickers:
        # 종목명 조회
        try:
            name = get_market_ticker_name(t)
        except Exception:
            continue

        # ROA 조회
        roa = get_latest_roa(t)
        if roa is not None and roa >= threshold:
            passed[t] = name
    return passed
