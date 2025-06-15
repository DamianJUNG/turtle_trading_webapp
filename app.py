import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# pykrx import with enhanced error handling
try:
    import pykrx.stock as stock
    PYKRX_AVAILABLE = True
    st.sidebar.success("✅ pykrx 연결 성공")
except ImportError as e:
    PYKRX_AVAILABLE = False
    st.sidebar.error("❌ pykrx 연결 실패")
    st.sidebar.write(f"오류: {str(e)}")
except Exception as e:
    PYKRX_AVAILABLE = False
    st.sidebar.error("❌ pykrx 초기화 실패")
    st.sidebar.write(f"오류: {str(e)}")

class TurtleTradingSystem:
    """터틀 트레이딩 시스템 메인 클래스"""
    
    def __init__(self):
        self.donchian_period = 20
        self.exit_period = 10
        self.atr_period = 20
        self.risk_per_trade = 0.02
        self.max_pyramid_levels = 4
        
    def convert_to_tickers(self, user_inputs):
        """사용자 입력을 종목코드로 변환"""
        if not PYKRX_AVAILABLE:
            st.error("⚠️ pykrx를 사용할 수 없습니다.")
            return {}
        
        result = {}
        
        # 전체 종목 리스트 가져오기 (캐싱 최적화)
        if 'all_tickers' not in st.session_state:
            try:
                with st.spinner("📊 KRX 종목 리스트 로딩 중... (최초 1회)"):
                    st.session_state.all_tickers = stock.get_market_ticker_list()
                    st.success(f"✅ {len(st.session_state.all_tickers)}개 종목 로드 완료")
            except Exception as e:
                st.error(f"종목 리스트 로딩 실패: {str(e)}")
                return {}
                
        all_tickers = st.session_state.all_tickers
        
        for user_input in user_inputs:
            user_input = user_input.strip()
            
            # 6자리 숫자면 종목코드로 간주
            if user_input.isdigit() and len(user_input) == 6:
                try:
                    name = stock.get_market_ticker_name(user_input)
                    if name and name.strip():
                        result[user_input] = name
                    else:
                        st.warning(f"⚠️ 종목코드 {user_input}에 해당하는 종목을 찾을 수 없습니다.")
                except Exception as e:
                    st.warning(f"⚠️ 종목코드 {user_input} 조회 중 오류 발생")
            else:
                # 종목명으로 검색
                found = False
                search_count = 0
                
                for ticker in all_tickers:
                    try:
                        name = stock.get_market_ticker_name(ticker)
                        if name and user_input in name:
                            result[ticker] = name
                            found = True
                            break
                        
                        search_count += 1
                        if search_count > 100:  # 검색 제한을 늘림
                            break
                            
                    except:
                        continue
                
                if not found:
                    st.warning(f"⚠️ 종목명 '{user_input}'을 찾을 수 없습니다. 정확한 종목명이나 6자리 종목코드를 입력해주세요.")
        
        return result
    
    def get_market_data(self, ticker, days=60):
        """실제 시장 데이터 수집 (pykrx 사용)"""
        if not PYKRX_AVAILABLE:
            st.error("pykrx가 사용 불가능합니다.")
            return None
            
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
            
            # pykrx로 OHLCV 데이터 수집
            df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
            
            if df.empty:
                st.warning(f"종목 {ticker}의 데이터가 없습니다.")
                return None
                
            # 기술적 지표 계산
            df = self.calculate_technical_indicators(df)
            
            return df.tail(days)
            
        except Exception as e:
            st.error(f"종목 {ticker} 데이터 수집 실패: {str(e)}")
            return None
    
    def calculate_technical_indicators(self, df):
        """기술적 지표 계산"""
        # True Range 계산
        df['prev_close'] = df['종가'].shift(1)
        df['tr1'] = df['고가'] - df['저가']
        df['tr2'] = abs(df['고가'] - df['prev_close'])
        df['tr3'] = abs(df['저가'] - df['prev_close'])
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR (Average True Range) 계산
        df['ATR'] = df['TR'].rolling(window=self.atr_period, min_periods=1).mean()
        df['N'] = df['ATR']  # 터틀 시스템에서 N = ATR
        
        # Donchian Channels 계산
        df['donchian_upper'] = df['고가'].rolling(window=self.donchian_period, min_periods=1).max()
        df['donchian_lower'] = df['저가'].rolling(window=self.exit_period, min_periods=1).min()
        
        # 진입/청산 신호
        df['entry_signal'] = (df['종가'] > df['donchian_upper'].shift(1)) & (df['donchian_upper'].shift(1).notna())
        df['exit_signal'] = (df['종가'] < df['donchian_lower'].shift(1)) & (df['donchian_lower'].shift(1).notna())
        
        # 거래량 기반 필터
        df['volume_ma5'] = df['거래량'].rolling(5, min_periods=1).mean()
        df['volume_surge'] = df['거래량'] > (df['volume_ma5'] * 1.5)
        
        return df
    
    def analyze_signals(self, tickers_dict):
        """전체 종목에 대한 신호 분석"""
        if not PYKRX_AVAILABLE:
            st.error("pykrx가 필요합니다.")
            return pd.DataFrame()
            
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (ticker, name) in enumerate(tickers_dict.items()):
            status_text.text(f'📊 분석 중: {name} ({ticker}) - {i+1}/{len(tickers_dict)}')
            
            df = self.get_market_data(ticker)
            
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                
                # 안전한 값 추출
                current_price = float(latest['종가'])
                atr_value = float(latest['N']) if pd.notna(latest['N']) and latest['N'] > 0 else current_price * 0.02
                
                result = {
                    '종목코드': ticker,
                    '종목명': name,
                    '현재가': int(current_price),
                    'ATR(N)': round(atr_value, 2),
                    'Donchian상단': int(latest['donchian_upper']) if pd.notna(latest['donchian_upper']) else int(current_price),
                    'Donchian하단': int(latest['donchian_lower']) if pd.notna(latest['donchian_lower']) else int(current_price),
                    '진입신호': bool(latest['entry_signal']) if pd.notna(latest['entry_signal']) else False,
                    '청산신호': bool(latest['exit_signal']) if pd.notna(latest['exit_signal']) else False,
                    '거래량급증': bool(latest['volume_surge']) if pd.notna(latest['volume_surge']) else False,
                    '손절가': int(current_price - 2 * atr_value),
                    '추가매수1': int(current_price + 0.5 * atr_value),
                    '추가매수2': int(current_price + 1.0 * atr_value),
                    '거래량': int(latest['거래량']) if latest['거래량'] > 0 else 0,
                    '분석일시': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                results.append(result)
            
            progress_bar.progress((i + 1) / len(tickers_dict))
        
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(results)
    
    def calculate_position_size(self, total_capital, current_price, atr, risk_per_trade=0.02):
        """터틀 트레이딩 포지션 사이징 (N 기반)"""
        if atr <= 0 or current_price <= 0 or total_capital <= 0:
            return None
            
        # 거래당 리스크 금액 = 총 자본 × 2%
        risk_amount = total_capital * risk_per_trade
        
        # 1N당 손실 금액 = ATR × 주가
        dollar_volatility = atr * current_price
        
        # Unit 수 = 리스크 금액 / 1N당 손실 금액
        units = risk_amount / dollar_volatility
        
        # 주식 수량 = Unit 수 (정수로 변환)
        shares = max(int(units), 1)  # 최소 1주
        
        # 실제 투자금액
        investment_amount = shares * current_price
        
        # 손절가 (진입가 - 2N)
        stop_loss = current_price - (2 * atr)
        
        # 추가매수가 계산
        add_buy_1 = current_price + (0.5 * atr)
        add_buy_2 = current_price + (1.0 * atr) 
        add_buy_3 = current_price + (1.5 * atr)
        
        # 최대 손실 금액 (손절시)
        max_loss = shares * (current_price - stop_loss)
        
        return {
            'shares': shares,
            'investment_amount': int(investment_amount),
            'stop_loss': round(stop_loss, 0),
            'add_buy_1': round(add_buy_1, 0),
            'add_buy_2': round(add_buy_2, 0),
            'add_buy_3': round(add_buy_3, 0),
            'max_loss': int(max_loss),
            'risk_percentage': (max_loss / total_capital) * 100
        }

class PositionManager:
    """포지션 관리 클래스"""
    
    def __init__(self):
        if 'user_positions' not in st.session_state:
            st.session_state.user_positions = []
    
    def add_position(self, ticker, name, entry_price, quantity, atr, stage=1):
        """새 포지션 추가"""
        position_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        new_position = {
            '포지션ID': position_id,
            '종목코드': ticker,
            '종목명': name,
            '진입일': datetime.now().strftime('%Y-%m-%d %H:%M'),
            '진입가': int(entry_price),
            'ATR(N)': round(float(atr), 2),
            '수량': int(quantity),
            '단계': stage,
            '손절가': int(entry_price - 2 * atr),
            '다음매수가': int(entry_price + 0.5 * atr) if stage < 4 else 0,
            '상태': '보유중',
            '현재가': int(entry_price),
            '손익': 0,
            '손익률': 0.0,
            '투자금액': int(entry_price * quantity)
        }
        
        st.session_state.user_positions.append(new_position)
        return new_position
    
    def update_positions(self, turtle_system):
        """포지션 현재가 업데이트 (실제 pykrx 데이터 사용)"""
        if not st.session_state.user_positions or not PYKRX_AVAILABLE:
            return 0
        
        updated_count = 0
        
        for i, position in enumerate(st.session_state.user_positions):
            if position['상태'] == '보유중':
                try:
                    # 실제 현재가 조회
                    df = turtle_system.get_market_data(position['종목코드'], days=3)
                    
                    if df is not None and not df.empty:
                        current_price = int(df.iloc[-1]['종가'])
                        
                        # 손익 계산
                        profit_loss = (current_price - position['진입가']) * position['수량']
                        profit_rate = ((current_price - position['진입가']) / position['진입가']) * 100
                        
                        # 청산 신호 체크
                        latest_data = df.iloc[-1]
                        
                        # 손절 조건 확인
                        if current_price <= position['손절가']:
                            st.session_state.user_positions[i]['상태'] = '청산신호(손절)'
                        
                        # Donchian 하단 하회 확인 (익절)
                        elif pd.notna(latest_data['donchian_lower']) and current_price <= latest_data['donchian_lower']:
                            st.session_state.user_positions[i]['상태'] = '청산신호(익절)'
                        
                        # 포지션 정보 업데이트
                        st.session_state.user_positions[i]['현재가'] = current_price
                        st.session_state.user_positions[i]['손익'] = int(profit_loss)
                        st.session_state.user_positions[i]['손익률'] = round(profit_rate, 2)
                        
                        updated_count += 1
                        
                except Exception as e:
                    st.warning(f"포지션 {position['종목명']} 업데이트 실패: {str(e)}")
        
        return updated_count
    
    def close_position(self, position_index):
        """포지션 청산"""
        if 0 <= position_index < len(st.session_state.user_positions):
            st.session_state.user_positions[position_index]['상태'] = '청산완료'
            st.session_state.user_positions[position_index]['청산일'] = datetime.now().strftime('%Y-%m-%d %H:%M')

def create_simple_chart(df, ticker_name):
    """Streamlit 내장 차트를 사용한 차트"""
    st.subheader(f"📊 {ticker_name} 차트 분석")
    
    # 최근 30일 데이터
    recent_df = df.tail(30)
    
    # 가격 차트
    chart_data = pd.DataFrame({
        '종가': recent_df['종가'],
        'Donchian상단': recent_df['donchian_upper'],
        'Donchian하단': recent_df['donchian_lower']
    })
    
    st.line_chart(chart_data)
    
    # 거래량 차트
    st.subheader("📊 거래량")
    st.bar_chart(recent_df['거래량'])
    
    # 신호 정보
    entry_signals = recent_df[recent_df['entry_signal']]
    exit_signals = recent_df[recent_df['exit_signal']]
    
    signal_col1, signal_col2 = st.columns(2)
    
    with signal_col1:
        if not entry_signals.empty:
            st.success(f"📈 진입 신호: {len(entry_signals)}회")
            if len(entry_signals) <= 5:
                dates = entry_signals.index.strftime('%m-%d').tolist()
                st.write("발생일:", ', '.join(dates))
        else:
            st.info("📈 최근 진입 신호 없음")
    
    with signal_col2:
        if not exit_signals.empty:
            st.warning(f"📉 청산 신호: {len(exit_signals)}회")
            if len(exit_signals) <= 5:
                dates = exit_signals.index.strftime('%m-%d').tolist()
                st.write("발생일:", ', '.join(dates))
        else:
            st.info("📉 최근 청산 신호 없음")

def main():
    """메인 Streamlit 앱"""
    st.set_page_config(
        page_title="터틀 트레이딩 시스템",
        page_icon="🐢",
        layout="wide"
    )
    
    # 헤더
    st.title("🐢 터틀 트레이딩 시스템")
    st.markdown("**한국 주식시장을 위한 체계적 추세추종 전략**")
    
    # pykrx 상태 확인
    if PYKRX_AVAILABLE:
        st.success("✅ 한국거래소(KRX) 실시간 데이터 연결 성공")
    else:
        st.error("""
        ❌ **pykrx 패키지 연결 실패**
        
        다음과 같은 이유로 발생할 수 있습니다:
        1. 패키지 설치 중 오류
        2. 네트워크 연결 문제
        3. 임시적인 서비스 장애
        
        **해결 방법:**
        - 페이지를 새로고침해보세요
        - 잠시 후 다시 시도해보세요
        - 문제가 계속되면 로컬 환경에서 실행해보세요
        """)
        
        # pykrx 없이도 UI는 보여주기
        st.warning("현재 데모 모드로 실행됩니다. 실제 데이터는 사용할 수 없습니다.")
    
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        # 터틀 시스템 초기화
        if 'turtle_system' not in st.session_state:
            st.session_state['turtle_system'] = TurtleTradingSystem()
        
        turtle_system = st.session_state['turtle_system']
        
        # 매개변수 설정
        st.subheader("📊 터틀 트레이딩 설정")
        donchian_period = st.slider("Donchian 기간", 10, 30, 20, help="진입 신호용 최고가 기간")
        atr_period = st.slider("ATR 기간", 10, 30, 20, help="변동성 계산 기간")
        risk_per_trade = st.slider("거래당 리스크 (%)", 1, 5, 2, help="총 자본 대비 거래당 리스크") / 100
        
        turtle_system.donchian_period = donchian_period
        turtle_system.atr_period = atr_period
        turtle_system.risk_per_trade = risk_per_trade
        
        st.markdown("---")
        
        # 투자 설정
        st.header("💰 투자 자금 관리")
        
        # 총 투자 가능 금액 입력
        total_capital = st.number_input(
            "총 투자금액 (원)",
            min_value=1000000,
            max_value=50000000000,
            value=st.session_state.get('total_capital', 10000000),
            step=1000000,
            help="터틀 트레이딩을 위한 총 투자 가능 금액"
        )
        
        # 세션에 저장
        st.session_state['total_capital'] = total_capital
        
        # 투자 현황 표시
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)
            active_positions = positions_df[positions_df['상태'] == '보유중']
            
            if not active_positions.empty:
                used_capital = active_positions['투자금액'].sum()
                remaining_capital = total_capital - used_capital
                usage_rate = (used_capital / total_capital) * 100
                
                st.metric("🔴 사용중인 자금", f"{used_capital:,}원")
                st.metric("🟢 남은 투자금", f"{remaining_capital:,}원")
                st.metric("📊 자금 사용률", f"{usage_rate:.1f}%")
                
                # 자금 사용률 경고
                if usage_rate > 80:
                    st.error("⚠️ 자금 사용률 80% 초과!")
                elif usage_rate > 60:
                    st.warning("⚠️ 자금 사용률 60% 초과")
                else:
                    st.success("✅ 적정 자금 사용률")
            else:
                st.metric("💰 총 투자금", f"{total_capital:,}원")
        else:
            st.metric("💰 총 투자금", f"{total_capital:,}원")
        
        st.markdown("---")
        
        # 빠른 도움말
        st.header("📖 빠른 가이드")
        with st.expander("🔍 사용법"):
            st.markdown("""
            **1단계**: 종목 입력 후 신호 분석
            **2단계**: 진입 신호 확인 및 포지션 계산
            **3단계**: 실제 매수 후 포지션 기록
            **4단계**: 정기적 현재가 업데이트
            **5단계**: 청산 신호시 매도 실행
            """)
        
        with st.expander("⚠️ 주의사항"):
            st.markdown("""
            - **2% 룰** 철저히 준수
            - **손절 신호** 즉시 실행  
            - **감정 배제** 체계적 거래
            - **매일 업데이트** 필수
            """)
    
    # pykrx 없으면 기능 제한
    if not PYKRX_AVAILABLE:
        st.info("🔧 pykrx 연결 후 모든 기능을 사용할 수 있습니다.")
        return
    
    # 메인 탭
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 신호 분석", 
        "💼 포지션 관리", 
        "📊 차트 분석",
        "📚 전략 가이드"
    ])
    
    with tab1:
        st.header("📈 실시간 신호 분석")
        
        # 종목 입력
        col_input, col_example = st.columns([3, 1])
        
        with col_input:
            user_input = st.text_area(
                "분석할 종목을 입력하세요 (종목명 또는 6자리 종목코드)",
                placeholder="삼성전자\n005930\nNAVER\n카카오\nSK하이닉스",
                height=120,
                help="한 줄에 하나씩 입력하세요. 종목명(예:삼성전자) 또는 종목코드(예:005930) 모두 가능합니다."
            )
        
        with col_example:
            st.markdown("**📝 입력 예시**")
            st.code("""삼성전자
NAVER  
005930
카카오
SK하이닉스
LG화학""")
            
            st.info("💡 **팁**: 정확한 종목명이나 6자리 종목코드를 사용하세요.")
        
        if st.button("🔍 실시간 신호 분석 시작", type="primary", help="KRX에서 실시간 데이터를 가져와 터틀 트레이딩 신호를 분석합니다"):
            if user_input.strip():
                user_inputs = [x.strip() for x in user_input.split('\n') if x.strip()]
                
                with st.spinner("🔍 종목 검색 및 검증 중..."):
                    tickers_dict = turtle_system.convert_to_tickers(user_inputs)
                
                if tickers_dict:
                    st.success(f"✅ {len(tickers_dict)}개 종목 확인 완료")
                    
                    # 확인된 종목 표시
                    confirmed_stocks = ", ".join([f"{name}({code})" for code, name in tickers_dict.items()])
                    st.info(f"📋 **분석 대상**: {confirmed_stocks}")
                    
                    # 신호 분석 실행
                    with st.spinner("📊 실시간 데이터 분석 중... (최대 1분 소요)"):
                        results_df = turtle_system.analyze_signals(tickers_dict)
                    
                    if not results_df.empty:
                        # 결과 저장
                        st.session_state['analysis_results'] = results_df
                        st.session_state['tickers_dict'] = tickers_dict
                        
                        # 결과 요약
                        entry_count = results_df['진입신호'].sum()
                        exit_count = results_df['청산신호'].sum()
                        volume_surge_count = results_df['거래량급증'].sum()
                        
                        # 요약 메트릭
                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        with summary_col1:
                            st.metric("📊 분석 종목", len(results_df))
                        with summary_col2:
                            st.metric("🟢 진입 신호", entry_count, delta="매수 기회")
                        with summary_col3:
                            st.metric("🔴 청산 신호", exit_count, delta="매도 고려")
                        with summary_col4:
                            st.metric("⚡ 거래량 급증", volume_surge_count, delta="관심 종목")
                        
                        # 진입 신호 종목 상세 표시
                        entry_signals = results_df[results_df['진입신호'] == True]
                        
                        if not entry_signals.empty:
                            st.success(f"🎯 **진입 신호 발생: {len(entry_signals)}개 종목**")

                            for idx, row in entry_signals.iterrows():
                                with st.expander(f"🟢 {row['종목명']} - 진입 신호!", expanded=True):
                                    # 종목 정보
                                    info_col1, info_col2, info_col3, info_col4 = st.columns(4)

                                    with info_col1:
                                        st.metric("현재가", f"{row['현재가']:,}원")
                                    with info_col2:
                                        st.metric("ATR(N)", f"{row['ATR(N)']:.1f}")
                                    with info_col3:
                                        st.metric("손절가", f"{row['손절가']:,}원")
                                    with info_col4:
                                        st.metric("거래량", f"{row['거래량']:,}")

                                    st.markdown("---")
                                    st.markdown("##### 💰 터틀 트레이딩 포지션 계산")

                                    # 총 투자금액 확인
                                    total_capital = st.session_state.get('total_capital', 10000000)

                                    # 포지션 사이징 계산
                                    position_calc = turtle_system.calculate_position_size(
                                        total_capital,
                                        row['현재가'],
                                        row['ATR(N)']
                                    )

                                    if position_calc:
                                        # 추천 포지션 정보 표시
                                        calc_col1, calc_col2 = st.columns(2)

                                        with calc_col1:
                                            st.info(f"""
                                            **🎯 추천 포지션 (2% 룰)**
                                            - 수량: {position_calc['shares']:,}주
                                            - 투자금액: {position_calc['investment_amount']:,}원
                                            - 최대손실: {position_calc['max_loss']:,}원
                                            """)

                                        with calc_col2:
                                            st.info(f"""
                                            **📊 리스크 분석**
                                            - 리스크 비율: {position_calc['risk_percentage']:.2f}%
                                            - 손절가: {position_calc['stop_loss']:,}원
                                            - 1차추가: {position_calc['add_buy_1']:,}원
                                            """)

                                        # 사용자 입력 (추천값으로 미리 설정)
                                        pos_col1, pos_col2, pos_col3 = st.columns([2, 2, 1])

                                        with pos_col1:
                                            actual_price = st.number_input(
                                                "실제 매수가",
                                                value=int(row['현재가']),
                                                step=100,
                                                key=f"price_{row['종목코드']}"
                                            )

                                        with pos_col2:
                                            quantity = st.number_input(
                                                "매수 수량",
                                                min_value=1,
                                                value=position_calc['shares'] if position_calc['shares'] > 0 else 10,
                                                step=1,
                                                key=f"qty_{row['종목코드']}",
                                                help=f"추천 수량: {position_calc['shares']}주"
                                            )

                                        with pos_col3:
                                            st.markdown("<br>", unsafe_allow_html=True)
                                            if st.button(f"➕ 포지션 추가", key=f"add_{row['종목코드']}", type="primary"):
                                                if actual_price > 0 and quantity > 0:
                                                    # 실제 투자금액 계산
                                                    actual_investment = actual_price * quantity

                                                    # 남은 투자금 확인
                                                    used_capital = 0
                                                    if st.session_state.get('user_positions'):
                                                        active_pos = pd.DataFrame(st.session_state.user_positions)
                                                        active_pos = active_pos[active_pos['상태'] == '보유중']
                                                        if not active_pos.empty:
                                                            used_capital = active_pos['투자금액'].sum()

                                                    remaining_capital = total_capital - used_capital

                                                    if actual_investment > remaining_capital:
                                                        st.error(f"""
                                                        ❌ **투자금 부족!**
                                                        - 필요금액: {actual_investment:,}원
                                                        - 남은금액: {remaining_capital:,}원
                                                        - 부족금액: {actual_investment - remaining_capital:,}원
                                                        """)
                                                    else:
                                                        if 'position_manager' not in st.session_state:
                                                            st.session_state['position_manager'] = PositionManager()

                                                        position_manager = st.session_state['position_manager']
                                                        position_manager.add_position(
                                                            row['종목코드'],
                                                            row['종목명'],
                                                            actual_price,
                                                            quantity,
                                                            row['ATR(N)']
                                                        )

                                                        st.success(f"✅ {row['종목명']} 포지션 추가!")
                                                        st.balloons()
                                                        st.rerun()

                                        # 투자 비교 분석
                                        if actual_price > 0 and quantity > 0:
                                            actual_investment = actual_price * quantity
                                            actual_max_loss = quantity * (actual_price - position_calc['stop_loss'])
                                            actual_risk_pct = (actual_max_loss / total_capital) * 100

                                            if actual_risk_pct > 2.5:
                                                st.error(f"⚠️ 리스크가 {actual_risk_pct:.2f}%로 권장치(2%)를 초과합니다!")
                                            elif actual_risk_pct > 2.0:
                                                st.warning(f"⚠️ 리스크가 {actual_risk_pct:.2f}%입니다.")
                                            else:
                                                st.success(f"✅ 리스크 {actual_risk_pct:.2f}% - 적절한 포지션입니다.")
                                    else:
                                        st.error("포지션 계산에 실패했습니다.")
                        else:
                            st.info("🔍 현재 진입 신호가 없습니다.")

                        # 전체 결과 표시
                        st.markdown("---")
                        st.subheader("📊 전체 분석 결과")

                        # 요약 통계
                        entry_count = results_df['진입신호'].sum()
                        exit_count = results_df['청산신호'].sum()
                        volume_surge_count = results_df['거래량급증'].sum()

                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
                        with summary_col1:
                            st.metric("분석 종목", len(results_df))
                        with summary_col2:
                            st.metric("진입 신호", entry_count)
                        with summary_col3:
                            st.metric("청산 신호", exit_count)
                        with summary_col4:
                            st.metric("거래량 급증", volume_surge_count)

                        # 결과 테이블
                        display_df = results_df[['종목명', '현재가', 'ATR(N)', '진입신호', '청산신호', '손절가']].copy()

                        st.dataframe(
                            display_df,
                            column_config={
                                '현재가': st.column_config.NumberColumn('현재가', format='%d원'),
                                'ATR(N)': st.column_config.NumberColumn('ATR(N)', format='%.2f'),
                                '손절가': st.column_config.NumberColumn('손절가', format='%d원'),
                                '진입신호': st.column_config.CheckboxColumn('진입신호'),
                                '청산신호': st.column_config.CheckboxColumn('청산신호')
                            },
                            use_container_width=True
                        )
                    else:
                        st.error("분석 결과를 생성할 수 없습니다.")
                else:
                    st.error("입력하신 종목을 찾을 수 없습니다.")
            else:
                st.warning("분석할 종목을 입력해주세요.")

    with tab2:
        st.header("💼 포지션 관리")

        # 관리 도구
        if st.session_state.get('user_positions'):
            tool_col1, tool_col2, tool_col3 = st.columns(3)

            with tool_col1:
                if st.button("🔄 현재가 업데이트"):
                    if 'position_manager' not in st.session_state:
                        st.session_state['position_manager'] = PositionManager()

                    with st.spinner("현재가 업데이트 중..."):
                        updated_count = st.session_state['position_manager'].update_positions(turtle_system)
                        st.success(f"✅ {updated_count}개 포지션 업데이트!")
                        st.rerun()

            with tool_col2:
                if st.button("💾 백업 저장"):
                    positions_df = pd.DataFrame(st.session_state.user_positions)
                    csv_data = positions_df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📄 CSV 다운로드",
                        data=csv_data,
                        file_name=f"turtle_positions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )

            with tool_col3:
                if st.button("🗑️ 전체 초기화"):
                    if st.checkbox("정말 모든 데이터를 삭제하시겠습니까?"):
                        st.session_state.user_positions = []
                        st.success("모든 포지션이 삭제되었습니다.")
                        st.rerun()

        # 포지션 목록
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)

            # 상태별 분류
            active_positions = positions_df[positions_df['상태'] == '보유중']
            signal_positions = positions_df[positions_df['상태'].str.contains('청산신호', na=False)]
            closed_positions = positions_df[positions_df['상태'] == '청산완료']

            # 보유중 포지션
            if not active_positions.empty:
                st.subheader("🟢 보유중 포지션")

                for original_idx in active_positions.index:
                    position = active_positions.loc[original_idx]

                    profit_emoji = "🟢" if position['손익'] >= 0 else "🔴"
                    profit_text = f"{position['손익']:+,}원 ({position['손익률']:+.2f}%)"

                    with st.expander(f"{profit_emoji} {position['종목명']} | {position['수량']}주 | {profit_text}"):
                        # 상세 정보
                        detail_col1, detail_col2, detail_col3 = st.columns(3)

                        with detail_col1:
                            st.write(f"**진입일**: {position['진입일']}")
                            st.write(f"**진입가**: {position['진입가']:,}원")
                            st.write(f"**현재가**: {position['현재가']:,}원")

                        with detail_col2:
                            st.write(f"**수량**: {position['수량']:,}주")
                            st.write(f"**투자금액**: {position['투자금액']:,}원")
                            st.write(f"**ATR(N)**: {position['ATR(N)']}")

                        with detail_col3:
                            st.write(f"**손절가**: {position['손절가']:,}원")
                            if position['다음매수가'] > 0:
                                st.write(f"**다음매수가**: {position['다음매수가']:,}원")
                            else:
                                st.write("**최종단계**: 추가매수 없음")

                        # 청산 버튼
                        if st.button(f"❌ 청산", key=f"close_{original_idx}"):
                            if 'position_manager' not in st.session_state:
                                st.session_state['position_manager'] = PositionManager()

                            # 해당 포지션의 실제 인덱스 찾기
                            for i, p in enumerate(st.session_state.user_positions):
                                if p['포지션ID'] == position['포지션ID']:
                                    st.session_state['position_manager'].close_position(i)
                                    break

                            st.success(f"{position['종목명']} 포지션 청산 완료!")
                            st.rerun()

            # 청산 신호 포지션
            if not signal_positions.empty:
                st.subheader("🚨 청산 신호 발생")

                for original_idx in signal_positions.index:
                    position = signal_positions.loc[original_idx]
                    signal_type = "손절" if "손절" in position['상태'] else "익절"

                    st.error(f"""
                    🚨 **{position['종목명']} - {signal_type} 신호!**
                    - 현재가: {position['현재가']:,}원
                    - 손익: {position['손익']:+,}원 ({position['손익률']:+.2f}%)
                    - **즉시 매도를 고려하세요!**
                    """)
        else:
            st.info("📋 등록된 포지션이 없습니다. '신호 분석' 탭에서 진입 신호를 확인하고 포지션을 등록해주세요.")

    with tab3:
        st.header("📊 차트 분석")

        if 'analysis_results' in st.session_state and 'tickers_dict' in st.session_state:
            results_df = st.session_state['analysis_results']
            tickers_dict = st.session_state['tickers_dict']

            # 종목 선택
            selected_ticker = st.selectbox(
                "차트를 분석할 종목 선택",
                options=list(tickers_dict.keys()),
                format_func=lambda x: f"{tickers_dict[x]} ({x})"
            )

            if selected_ticker:
                col_chart, col_info = st.columns([3, 1])

                with col_chart:
                    with st.spinner("차트 데이터 로딩 중..."):
                        df = turtle_system.get_market_data(selected_ticker, days=60)

                        if df is not None and not df.empty:
                            create_simple_chart(df, tickers_dict[selected_ticker])
                        else:
                            st.error("차트 데이터를 불러올 수 없습니다.")

                with col_info:
                    # 종목 정보
                    ticker_data = results_df[results_df['종목코드'] == selected_ticker]

                    if not ticker_data.empty:
                        ticker_info = ticker_data.iloc[0]

                        st.markdown(f"### {ticker_info['종목명']}")
                        st.markdown(f"**코드**: {ticker_info['종목코드']}")

                        # 신호 상태
                        if ticker_info['진입신호']:
                            st.success("🟢 진입 신호")
                        elif ticker_info['청산신호']:
                            st.error("🔴 청산 신호")
                        else:
                            st.info("⚪ 신호 없음")

                        # 주요 지표
                        st.metric("현재가", f"{ticker_info['현재가']:,}원")
                        st.metric("ATR(N)", f"{ticker_info['ATR(N)']:.2f}")

                        st.markdown("**주요 가격대**")
                        st.write(f"• 손절가: {ticker_info['손절가']:,}원")
                        st.write(f"• 추가매수가: {ticker_info['추가매수1']:,}원")
                        st.write(f"• Donchian상단: {ticker_info['Donchian상단']:,}원")
                        st.write(f"• Donchian하단: {ticker_info['Donchian하단']:,}원")

                        # 거래량 정보
                        if ticker_info['거래량급증']:
                            st.warning("⚡ 거래량 급증")
                        else:
                            st.info("📊 정상 거래량")
        else:
            st.info("먼저 '신호 분석' 탭에서 종목 분석을 실행해주세요.")

    with tab4:
        st.header("📚 터틀 트레이딩 전략 가이드")

        # 전략 개요
        st.markdown("""
        ## 🐢 터틀 트레이딩이란?

        터틀 트레이딩은 1980년대 리처드 데니스가 개발한 **추세추종 전략**입니다.
        감정을 배제하고 체계적인 규칙에 따라 거래하는 것이 핵심입니다.
        """)

        # 핵심 규칙
        rule_col1, rule_col2 = st.columns(2)

        with rule_col1:
            st.markdown("""
            ### 📈 진입 규칙

            **1️⃣ Donchian 상단 돌파**
            - 종가가 20일 최고가 돌파시 진입
            - 새로운 상승 추세의 시작 포착

            **2️⃣ ATR 기반 포지션 사이징**
            - ATR(Average True Range)로 변동성 측정
            - 거래당 리스크를 계좌의 2%로 제한

            **3️⃣ 피라미딩 (추가매수)**
            - 수익 시 포지션 확대
            - 최대 4단계까지 추가매수
            """)

        with rule_col2:
            st.markdown("""
            ### 📉 청산 규칙

            **1️⃣ 손절 (Stop Loss)**
            - 진입가 - 2N(ATR) 하락시 무조건 손절
            - 감정 개입 완전 차단

            **2️⃣ 익절 (Profit Taking)**
            - 10일 최저가 하회시 전량 매도
            - 추세 반전 신호 조기 감지

            **3️⃣ 청산 우선순위**
            - 손절 > 익절 > 추가매수
            - 리스크 관리가 최우선
            """)

        # 사용법 가이드
        st.markdown("---")
        st.markdown("## 🎯 웹앱 사용 가이드")

        st.markdown("""
        ### 📝 단계별 사용법

        **1단계: 투자금 설정**
        1. 사이드바에서 총 투자금액 입력
        2. 리스크 매개변수 설정 (Donchian, ATR 기간)

        **2단계: 신호 분석**
        1. '신호 분석' 탭에서 관심 종목 입력
        2. '🔍 실시간 신호 분석 시작' 클릭
        3. 진입 신호 발생 종목 확인

        **3단계: 포지션 계산 & 매수**
        1. 🎯 추천 포지션 (2% 룰) 확인
        2. 증권사 앱에서 **실제 매수** 실행
        3. 웹앱에서 실제 체결가와 수량 입력
        4. '➕ 포지션 추가'로 기록

        **4단계: 지속적 모니터링**
        1. '포지션 관리' 탭에서 보유 현황 확인
        2. '🔄 현재가 업데이트'로 손익 추적
        3. 청산 신호 발생시 즉시 매도

        **5단계: 기록 관리**
        1. '💾 백업 저장'으로 거래 기록 보관
        2. '📊 차트 분석'으로 패턴 학습
        3. 지속적인 전략 개선
        """)

        # 주의사항
        st.markdown("---")
        st.markdown("## ⚠️ 중요한 주의사항")

        warning_col1, warning_col2 = st.columns(2)

        with warning_col1:
            st.markdown("""
            ### 🚫 하지 말아야 할 것들
            - 감정적 판단으로 손절가 변경
            - 신호 없는 임의 매수
            - 과도한 레버리지 사용
            - 포지션 기록 누락
            - 2% 룰 무시
            """)

        with warning_col2:
            st.markdown("""
            ### ✅ 반드시 지켜야 할 것들
            - **2% 룰** 철저히 준수
            - **손절 신호** 즉시 실행
            - **매일 포지션** 업데이트
            - **체계적 기록** 유지
            - **자금 관리** 엄격히 준수
            """)

        # 면책조항
        st.markdown("---")
        st.warning("""
        **⚠️ 면책조항**

        이 웹앱은 교육 및 연구 목적으로 제작되었습니다.
        - 실제 투자 손실에 대해 책임지지 않습니다
        - 과거 수익률이 미래 수익을 보장하지 않습니다
        - 모든 투자 결정은 신중히 하시기 바랍니다
        - 충분한 백테스팅과 검증을 권장합니다
        """)

if __name__ == "__main__":
    main()
