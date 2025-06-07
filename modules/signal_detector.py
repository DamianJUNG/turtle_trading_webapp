# modules/signal_detector.py

import pandas as pd
from pykrx.stock import get_market_ohlcv_by_date
from config import DONCHIAN_PERIOD, VOLUME_PERIOD, VOLUME_MULTIPLIER

def detect_entry_signals(tickers: list, start_date: str, end_date: str) -> dict:
    """
    tickers: ['005930', ...]
    start_date, end_date in 'YYYYMMDD'
    반환: {code: {"name":name, "price":..., "donchian":..., "volume_ratio":...}, ...}
    """
    signals = {}
    for code, name in tickers.items():
        df = get_market_ohlcv_by_date(start_date, end_date, code)
        if df is None or len(df) < DONCHIAN_PERIOD + 2:
            continue

        # Donchian 상단 (전일까지)
        df['donchian_high'] = df['고가'].rolling(DONCHIAN_PERIOD).max().shift(1)
        # 거래량 비율
        df['avg_volume'] = df['거래량'].rolling(VOLUME_PERIOD).mean().shift(1)
        df['volume_ratio'] = df['거래량'] / df['avg_volume']

        latest = df.iloc[-1]
        cond_price  = latest['종가'] > latest['donchian_high']
        cond_volume = latest['volume_ratio'] >= VOLUME_MULTIPLIER

        if cond_price and cond_volume:
            signals[code] = {
                "name": name,
                "price":  latest['종가'],
                "donchian": round(latest['donchian_high'], 0),
                "volume_ratio": round(latest['volume_ratio'], 2)
            }
    return signals
