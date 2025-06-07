# app.py

import streamlit as st
import pandas as pd
from datetime import datetime
from modules.symbol_utils import convert_to_tickers
from modules.financial_filter import filter_by_roa
from modules.signal_detector import detect_entry_signals
from modules.risk_manager import calculate_position_params
from modules.google_sheet_writer import connect_sheet_by_url, append_position
from config import ROA_THRESHOLD

st.set_page_config(page_title="Turtle Trading WebApp", layout="wide")
st.title("🐢 Turtle Trading Strategy WebApp")

# 1) 사용자 입력: 종목 리스트
user_input = st.text_input("종목명 또는 코드 입력 (쉼표 구분)", "삼성전자, 005930")
user_list = [s.strip() for s in user_input.split(",") if s.strip()]

# 2) 코드 변환
tickers = convert_to_tickers(user_list)

st.sidebar.header("필터 설정")
roa_thresh = st.sidebar.number_input("ROA 최소 조건 (%)", value=ROA_THRESHOLD, step=0.1)
sheet_url = st.sidebar.text_input("Google Sheet URL", "")

if st.button("신호 분석 실행"):
    if not tickers:
        st.error("유효한 종목 코드가 없습니다.")
        st.stop()

    # 3) 재무 필터
    filtered = filter_by_roa(tickers, roa_thresh)
    st.write("## 🔍 ROA 필터 통과 종목", pd.DataFrame.from_dict(filtered, orient="index"))

    if not filtered:
        st.warning("ROA 조건에 해당하는 종목이 없습니다.")
        st.stop()

    # 4) 시그널 감지
    today = datetime.today().strftime("%Y%m%d")
    signals = detect_entry_signals(filtered, (datetime.today()-pd.Timedelta(days=60)).strftime("%Y%m%d"), today)
    st.write("## 📈 Entry Signals", pd.DataFrame.from_dict(signals, orient="index"))

    if not signals:
        st.warning("진입 신호가 없습니다.")
        st.stop()

    # 5) 포지션 및 리스크 설정
    records = []
    for code, info in signals.items():
        entry_price = info["price"]
        params = calculate_position_params(code, entry_price, today)
        record = {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "code": code,
            "name": info["name"],
            "entry_price": entry_price,
            "quantity": 0,  # 여기에 전략에 따른 수량 계산 로직 추가 가능
            "atr": params["atr"],
            "stop_loss": params["stop_loss"],
            "next_add_on": params["add_on_prices"][0]
        }
        records.append(record)
    df_records = pd.DataFrame(records)
    st.write("## 📋 Position Parameters", df_records)

    # 6) Google Sheet 기록
    if sheet_url:
        try:
            ws = connect_sheet_by_url(sheet_url)
            for rec in records:
                append_position(ws, rec)
            st.success("✅ 포지션 기록 완료!")
        except Exception as e:
            st.error(f"구글시트 기록 오류: {e}")
    else:
        st.info("⚠️ Google Sheet URL을 입력해야 기록됩니다.")
