import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

# pykrx import with error handling
try:
    import pykrx.stock as stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    st.error("pykrx 패키지를 설치할 수 없습니다. 데모 모드로 실행됩니다.")

class TurtleTradingSystem:
    """터틀 트레이딩 시스템 메인 클래스"""
    
    def __init__(self):
        self.donchian_period = 20
        self.exit_period = 10
        self.atr_period = 20
        self.risk_per_trade = 0.02  # 2%
        self.max_pyramid_levels = 4  # 최대 4단계 추가매수
        
    def convert_to_tickers(self, user_inputs):
        """사용자 입력을 종목코드로 변환 (데모용)"""
        # 데모 데이터
        demo_tickers = {
            '005930': '삼성전자',
            '035420': 'NAVER',
            '035720': '카카오',
            '000660': 'SK하이닉스',
            '051910': 'LG화학',
            '006400': '삼성SDI',
            '207940': '삼성바이오로직스',
            '068270': '셀트리온',
            '323410': '카카오뱅크',
            '377300': '카카오페이'
        }
        
        result = {}
        
        if not PYKRX_AVAILABLE:
            # 데모 모드: 입력된 종목들을 데모 데이터에서 매칭
            for user_input in user_inputs:
                user_input = user_input.strip()
                
                # 종목코드 직접 입력
                if user_input in demo_tickers:
                    result[user_input] = demo_tickers[user_input]
                else:
                    # 종목명으로 검색
                    for code, name in demo_tickers.items():
                        if user_input in name:
                            result[code] = name
                            break
            return result
        
        # 실제 pykrx 사용 (원래 로직)
        if 'all_tickers' not in st.session_state:
            try:
                st.session_state.all_tickers = stock.get_market_ticker_list()
            except:
                st.session_state.all_tickers = list(demo_tickers.keys())
                
        all_tickers = st.session_state.all_tickers
        
        for user_input in user_inputs:
            user_input = user_input.strip()
            
            if user_input.isdigit() and len(user_input) == 6:
                try:
                    if PYKRX_AVAILABLE:
                        name = stock.get_market_ticker_name(user_input)
                    else:
                        name = demo_tickers.get(user_input, f"종목{user_input}")
                    if name:
                        result[user_input] = name
                except:
                    st.warning(f"종목코드 {user_input}를 찾을 수 없습니다.")
            else:
                found = False
                for ticker in all_tickers:
                    try:
                        if PYKRX_AVAILABLE:
                            name = stock.get_market_ticker_name(ticker)
                        else:
                            name = demo_tickers.get(ticker, f"종목{ticker}")
                        if user_input in name:
                            result[ticker] = name
                            found = True
                            break
                    except:
                        continue
                
                if not found:
                    st.warning(f"종목명 '{user_input}'을 찾을 수 없습니다.")
        
        return result
    
    def get_market_data(self, ticker, days=60):
        """시장 데이터 수집 (데모 데이터 포함)"""
        if not PYKRX_AVAILABLE:
            # 데모 데이터 생성
            return self.generate_demo_data(ticker, days)
        
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
            
            df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
            
            if df.empty:
                return self.generate_demo_data(ticker, days)
                
            df = self.calculate_technical_indicators(df)
            return df.tail(days)
            
        except Exception as e:
            st.warning(f"{ticker} 실제 데이터 수집 실패, 데모 데이터를 사용합니다.")
            return self.generate_demo_data(ticker, days)
    
    def generate_demo_data(self, ticker, days):
        """데모용 가상 데이터 생성"""
        np.random.seed(hash(ticker) % 2**32)  # 종목별 고정 시드
        
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        
        # 기본 가격 설정 (종목별 다른 가격대)
        base_prices = {
            '005930': 70000,   # 삼성전자
            '035420': 200000,  # NAVER
            '035720': 60000,   # 카카오
            '000660': 130000,  # SK하이닉스
            '051910': 400000,  # LG화학
        }
        
        base_price = base_prices.get(ticker, 50000)
        
        # 랜덤워크로 가격 생성
        returns = np.random.normal(0.001, 0.02, days)  # 일평균 0.1% 수익, 2% 변동성
        prices = base_price * np.exp(np.cumsum(returns))
        
        # OHLCV 데이터 생성
        high_mult = 1 + np.abs(np.random.normal(0, 0.01, days))
        low_mult = 1 - np.abs(np.random.normal(0, 0.01, days))
        
        df = pd.DataFrame({
            '시가': prices * np.random.uniform(0.99, 1.01, days),
            '고가': prices * high_mult,
            '저가': prices * low_mult,
            '종가': prices,
            '거래량': np.random.randint(100000, 1000000, days)
        }, index=dates)
        
        # 기술적 지표 계산
        df = self.calculate_technical_indicators(df)
        
        return df
    
    def calculate_technical_indicators(self, df):
        """기술적 지표 계산"""
        # True Range 계산
        df['prev_close'] = df['종가'].shift(1)
        df['tr1'] = df['고가'] - df['저가']
        df['tr2'] = abs(df['고가'] - df['prev_close'])
        df['tr3'] = abs(df['저가'] - df['prev_close'])
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR 계산
        df['ATR'] = df['TR'].rolling(window=self.atr_period).mean()
        df['N'] = df['ATR']
        
        # Donchian Channels 계산
        df['donchian_upper'] = df['고가'].rolling(window=self.donchian_period).max()
        df['donchian_lower'] = df['저가'].rolling(window=self.exit_period).min()
        
        # 진입/청산 신호
        df['entry_signal'] = (df['종가'] > df['donchian_upper'].shift(1)) & \
                            (df['donchian_upper'].shift(1).notna())
        df['exit_signal'] = (df['종가'] < df['donchian_lower'].shift(1)) & \
                           (df['donchian_lower'].shift(1).notna())
        
        # 거래량 기반 필터
        df['volume_ma5'] = df['거래량'].rolling(5).mean()
        df['volume_surge'] = df['거래량'] > (df['volume_ma5'] * 1.5)
        
        return df
    
    def analyze_signals(self, tickers_dict):
        """신호 분석"""
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (ticker, name) in enumerate(tickers_dict.items()):
            status_text.text(f'분석 중: {name} ({ticker})')
            
            df = self.get_market_data(ticker)
            
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                
                result = {
                    '종목코드': ticker,
                    '종목명': name,
                    '현재가': int(latest['종가']),
                    'ATR(N)': round(latest['N'], 2) if pd.notna(latest['N']) else 0,
                    'Donchian상단': int(latest['donchian_upper']) if pd.notna(latest['donchian_upper']) else 0,
                    'Donchian하단': int(latest['donchian_lower']) if pd.notna(latest['donchian_lower']) else 0,
                    '진입신호': latest['entry_signal'] if pd.notna(latest['entry_signal']) else False,
                    '청산신호': latest['exit_signal'] if pd.notna(latest['exit_signal']) else False,
                    '거래량급증': latest['volume_surge'] if pd.notna(latest['volume_surge']) else False,
                    '손절가': int(latest['종가'] - 2 * latest['N']) if pd.notna(latest['N']) else 0,
                    '추가매수1': int(latest['종가'] + 0.5 * latest['N']) if pd.notna(latest['N']) else 0,
                    '추가매수2': int(latest['종가'] + 1.0 * latest['N']) if pd.notna(latest['N']) else 0,
                }
                
                results.append(result)
            
            progress_bar.progress((i + 1) / len(tickers_dict))
        
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(results)

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
            '진입가': entry_price,
            'ATR(N)': atr,
            '수량': quantity,
            '단계': stage,
            '손절가': int(entry_price - 2 * atr),
            '다음매수가': int(entry_price + 0.5 * atr) if stage < 4 else 0,
            '상태': '보유중',
            '현재가': entry_price,
            '손익': 0,
            '손익률': 0.0
        }
        
        st.session_state.user_positions.append(new_position)
        return new_position
    
    def close_position(self, position_index):
        """포지션 청산"""
        if 0 <= position_index < len(st.session_state.user_positions):
            st.session_state.user_positions[position_index]['상태'] = '청산완료'

def create_chart(df, ticker_name):
    """차트 생성"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=[f'{ticker_name} - 터틀 트레이딩 신호', '거래량'],
        row_heights=[0.7, 0.3]
    )
    
    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['시가'],
            high=df['고가'],
            low=df['저가'],
            close=df['종가'],
            name='Price'
        ),
        row=1, col=1
    )
    
    # Donchian Channels
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['donchian_upper'],
            mode='lines',
            name='Donchian Upper (20)',
            line=dict(color='red', width=1)
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['donchian_lower'],
            mode='lines',
            name='Donchian Lower (10)',
            line=dict(color='blue', width=1)
        ),
        row=1, col=1
    )
    
    # 거래량
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['거래량'],
            name='거래량',
            marker_color='lightblue'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=f'{ticker_name} 터틀 트레이딩 분석',
        xaxis_rangeslider_visible=False,
        height=600
    )
    
    return fig

def main():
    """메인 앱"""
    st.set_page_config(
        page_title="터틀 트레이딩 시스템",
        page_icon="🐢",
        layout="wide"
    )
    
    # 헤더
    st.title("🐢 터틀 트레이딩 시스템")
    st.markdown("**한국 주식시장을 위한 체계적 추세추종 전략**")
    
    if not PYKRX_AVAILABLE:
        st.warning("⚠️ 현재 데모 모드로 실행 중입니다. 실제 데이터 대신 가상 데이터를 사용합니다.")
    
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        if 'turtle_system' not in st.session_state:
            st.session_state['turtle_system'] = TurtleTradingSystem()
        
        turtle_system = st.session_state['turtle_system']
        
        donchian_period = st.slider("Donchian 기간", 10, 30, 20)
        atr_period = st.slider("ATR 기간", 10, 30, 20)
        risk_per_trade = st.slider("거래당 리스크 (%)", 1, 5, 2) / 100
        
        turtle_system.donchian_period = donchian_period
        turtle_system.atr_period = atr_period
        turtle_system.risk_per_trade = risk_per_trade
        
        st.markdown("---")
        st.header("💼 포트폴리오 요약")
        
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)
            active_positions = positions_df[positions_df['상태'] == '보유중']
            
            if not active_positions.empty:
                st.metric("활성 포지션", f"{len(active_positions)}개")
            else:
                st.info("활성 포지션이 없습니다.")
        else:
            st.info("포지션을 추가해주세요.")
    
    # 메인 탭
    tab1, tab2, tab3 = st.tabs(["📈 신호 분석", "💼 포지션 관리", "📊 차트 분석"])
    
    with tab1:
        st.header("📈 신호 분석")
        
        user_input = st.text_area(
            "분석할 종목을 입력하세요",
            placeholder="삼성전자\n005930\nNAVER\n카카오",
            height=100
        )
        
        if st.button("🔍 신호 분석 시작", type="primary"):
            if user_input.strip():
                user_inputs = [x.strip() for x in user_input.split('\n') if x.strip()]
                
                with st.spinner("분석 중..."):
                    tickers_dict = turtle_system.convert_to_tickers(user_inputs)
                
                if tickers_dict:
                    results_df = turtle_system.analyze_signals(tickers_dict)
                    
                    if not results_df.empty:
                        st.session_state['analysis_results'] = results_df
                        st.session_state['tickers_dict'] = tickers_dict
                        
                        # 진입 신호 표시
                        entry_signals = results_df[results_df['진입신호'] == True]
                        if not entry_signals.empty:
                            st.success(f"🟢 진입 신호: {len(entry_signals)}개 종목")
                            
                            for idx, row in entry_signals.iterrows():
                                with st.expander(f"🎯 {row['종목명']} - 진입 신호", expanded=True):
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        actual_price = st.number_input(
                                            "실제 매수가",
                                            value=int(row['현재가']),
                                            step=100,
                                            key=f"price_{row['종목코드']}"
                                        )
                                    
                                    with col2:
                                        quantity = st.number_input(
                                            "매수 수량",
                                            min_value=1,
                                            step=1,
                                            key=f"qty_{row['종목코드']}"
                                        )
                                    
                                    with col3:
                                        if st.button(f"➕ 포지션 추가", key=f"add_{row['종목코드']}", type="primary"):
                                            if actual_price > 0 and quantity > 0:
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
                                                st.rerun()
                        else:
                            st.info("현재 진입 신호가 없습니다.")
                        
                        # 전체 결과
                        st.dataframe(results_df[['종목명', '현재가', 'ATR(N)', '진입신호', '손절가']])
    
    with tab2:
        st.header("💼 포지션 관리")
        
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)
            
            st.dataframe(
                positions_df[['종목명', '진입일', '진입가', '수량', '손절가', '상태']],
                use_container_width=True
            )
        else:
            st.info("등록된 포지션이 없습니다.")
    
    with tab3:
        st.header("📊 차트 분석")
        
        if 'analysis_results' in st.session_state and 'tickers_dict' in st.session_state:
            tickers_dict = st.session_state['tickers_dict']
            
            selected_ticker = st.selectbox(
                "종목 선택",
                options=list(tickers_dict.keys()),
                format_func=lambda x: f"{tickers_dict[x]} ({x})"
            )
            
            if selected_ticker:
                df = turtle_system.get_market_data(selected_ticker)
                if df is not None:
                    chart = create_chart(df, tickers_dict[selected_ticker])
                    st.plotly_chart(chart, use_container_width=True)
        else:
            st.info("먼저 신호 분석을 실행해주세요.")

if __name__ == "__main__":
    main()
