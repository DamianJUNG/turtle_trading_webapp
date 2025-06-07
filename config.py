# config.py

# ────────── 재무 필터 ──────────
# filter_by_roa 의 기본 임계값 (%)
ROA_THRESHOLD = 5.0

# ────────── 터틀 지표 기간 ──────────
# Donchian Channel 계산을 위한 기간 (일)
DONCHIAN_PERIOD    = 20

# VWAP 계산을 위한 기간 (일)
VWAP_PERIOD        = 20

# ATR 계산을 위한 기간 (일)
ATR_PERIOD         = 20

# 거래량 증가 필터 기간 (일)
VOLUME_PERIOD      = 20

# 거래량 증가 비율 (평균 대비 몇 배)
VOLUME_MULTIPLIER  = 1.3

# ────────── 터틀 리스크 매니저 기본값 ──────────
# (필요하다면 여기에도 총자본이나 리스크 비율 기본값을 정의할 수 있습니다)
# TOTAL_CAPITAL_DEFAULT = 10_000_000
# RISK_PERCENT_DEFAULT  = 1.0
