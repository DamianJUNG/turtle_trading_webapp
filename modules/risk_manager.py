# modules/risk_manager.py

import pandas as pd
from pykrx.stock import get_market_ohlcv_by_date
from config import ATR_PERIOD

def calculate_atr(df: pd.DataFrame) -> pd.Series:
    """
    df: OHLCV 데이터프레임, 컬럼 ['시가','고가','저가','종가','거래량']
    반환: ATR 시리즈 (rolling ATR_PERIOD)
    """
    high_low = df['고가'] - df['저가']
    high_prev_close = (df['고가'] - df['종가'].shift(1)).abs()
    low_prev_close = (df['저가'] - df['종가'].shift(1)).abs()
    tr = pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)
    atr = tr.rolling(ATR_PERIOD).mean()
    return atr

def calculate_position_params(code: str, entry_price: float, date: str) -> dict:
    """
    단일 종목 entry 시점 손절가, 추가매수 가격, ATR 값 계산
    date: 'YYYYMMDD' 기준 데이터 수집 끝일
    """
    df = get_market_ohlcv_by_date(date, date, code)
    df_full = get_market_ohlcv_by_date((int(date[:4])-1)*10000+1, date, code)
    atr_series = calculate_atr(df_full)
    atr = atr_series.iloc[-1]

    stop_loss = entry_price - 2 * atr
    add_on_prices = [entry_price + i * 0.5 * atr for i in range(1, 4)]

    return {
        "atr": round(atr, 2),
        "stop_loss": round(stop_loss, 0),
        "add_on_prices": [round(p, 0) for p in add_on_prices]
    }
