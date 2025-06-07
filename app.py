import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# pykrx import with proper error handling
try:
    import pykrx.stock as stock
    PYKRX_AVAILABLE = True
    st.sidebar.success("✅ 실제 데이터 모드")
except ImportError as e:
    PYKRX_AVAILABLE = False
    st.sidebar.error("❌ pykrx 설치 실패")
    st.sidebar.write(f"Error: {str(e)}")

# plotly import
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

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
            st.error("⚠️ pykrx가 설치되지 않아 실제 데이터를 사용할 수 없습니다.")
            return {}
        
        result = {}
        
        # 전체 종목 리스트 가져오기 (캐싱)
        if 'all_tickers' not in st.session_state:
            try:
                with st.spinner("종목 리스트 로딩 중..."):
                    st.session_state.all_tickers = stock.get_market_ticker_list()
                    st.sidebar.info(f"총 {len(st.session_state.all_tickers)}개 종목 로드됨")
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
                    if name:
                        result[user_input] = name
                    else:
                        st.warning(f"종목코드 {user_input}에 해당하는 종목을 찾을 수 없습니다.")
                except Exception as e:
                    st.warning(f"종목코드 {user_input} 조회 실패: {str(e)}")
            else:
                # 종목명으로 검색
                found = False
                search_count = 0
                
                for ticker in all_tickers:
                    try:
                        name = stock.get_market_ticker_name(ticker)
                        if user_input in name:
                            result[ticker] = name
                            found = True
                            break
                        
                        search_count += 1
                        if search_count > 100:  # 너무 많이 검색하지 않도록 제한
                            break
                            
                    except:
                        continue
                
                if not found:
                    st.warning(f"종목명 '{user_input}'을 찾을 수 없습니다. 정확한 종목명이나 종목코드를 입력해주세요.")
        
        return result
    
    def get_market_data(self, ticker, days=60):
        """실제 시장 데이터 수집"""
        if not PYKRX_AVAILABLE:
            st.error("실제 데이터를 사용할 수 없습니다.")
            return None
            
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
            
            # pykrx로 실제 데이터 가져오기
            df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
            
            if df.empty:
                st.warning(f"종목 {ticker}의 데이터를 가져올 수 없습니다.")
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
        df['entry_signal'] = (df['종가'] > df['donchian_upper'].shift(1)) & \
                            (df['donchian_upper'].shift(1).notna())
        df['exit_signal'] = (df['종가'] < df['donchian_lower'].shift(1)) & \
                           (df['donchian_lower'].shift(1).notna())
        
        # 거래량 기반 필터 (선택적)
        df['volume_ma5'] = df['거래량'].rolling(5, min_periods=1).mean()
        df['volume_surge'] = df['거래량'] > (df['volume_ma5'] * 1.5)
        
        return df
    
    def analyze_signals(self, tickers_dict):
        """전체 종목에 대한 신호 분석"""
        if not PYKRX_AVAILABLE:
            st.error("실제 데이터 분석을 위해서는 pykrx가 필요합니다.")
            return pd.DataFrame()
            
        results = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (ticker, name) in enumerate(tickers_dict.items()):
            status_text.text(f'분석 중: {name} ({ticker}) - {i+1}/{len(tickers_dict)}')
            
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
                    '거래량': int(latest['거래량']),
                    '분석일시': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
                
                results.append(result)
            else:
                # 데이터 가져오기 실패한 종목 기록
                st.warning(f"⚠️ {name}({ticker}) 데이터 수집 실패")
            
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
        """포지션 현재가 업데이트 (실제 데이터 사용)"""
        if not st.session_state.user_positions or not PYKRX_AVAILABLE:
            return
        
        updated_count = 0
        
        for i, position in enumerate(st.session_state.user_positions):
            if position['상태'] == '보유중':
                try:
                    # 실제 현재가 조회
                    df = turtle_system.get_market_data(position['종목코드'], days=5)
                    
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

def create_chart(df, ticker_name):
    """Plotly 차트 생성"""
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly가 설치되지 않아 간단한 차트를 표시합니다.")
        # Streamlit 내장 차트 사용
        chart_data = pd.DataFrame({
            '종가': df['종가'],
            'Donchian 상단': df['donchian_upper'],
            'Donchian 하단': df['donchian_lower']
        })
        st.line_chart(chart_data)
        st.bar_chart(df['거래량'])
        return
    
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
            line=dict(color='red', width=2, dash='dash')
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df['donchian_lower'],
            mode='lines',
            name='Donchian Lower (10)',
            line=dict(color='blue', width=2, dash='dash')
        ),
        row=1, col=1
    )
    
    # 진입/청산 신호
    entry_signals = df[df['entry_signal']]
    if not entry_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=entry_signals.index,
                y=entry_signals['종가'],
                mode='markers',
                name='진입신호',
                marker=dict(symbol='triangle-up', size=12, color='green')
            ),
            row=1, col=1
        )
    
    exit_signals = df[df['exit_signal']]
    if not exit_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=exit_signals.index,
                y=exit_signals['종가'],
                mode='markers',
                name='청산신호',
                marker=dict(symbol='triangle-down', size=12, color='red')
            ),
            row=1, col=1
        )
    
    # 거래량
    colors = ['red' if vol > df['volume_ma5'].iloc[i] * 1.5 else 'lightblue' 
              for i, vol in enumerate(df['거래량'])]
    
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['거래량'],
            name='거래량',
            marker_color=colors
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=f'{ticker_name} 터틀 트레이딩 분석',
        xaxis_rangeslider_visible=False,
        height=700,
        showlegend=True
    )
    
    return fig

def main():
    """메인 Streamlit 앱"""
    st.set_page_config(
        page_title="터틀 트레이딩 시스템",
        page_icon="🐢",
        layout="wide"
    )
    
    # 헤더
    st.title("🐢 터틀 트레이딩 시스템")
    st.markdown("**한국 주식시장을 위한 체계적 추세추종 전략 (실제 데이터 사용)**")
    
    # pykrx 상태 확인
    if not PYKRX_AVAILABLE:
        st.error("""
        ⚠️ **pykrx 패키지를 사용할 수 없습니다**
        
        이 앱은 한국거래소의 실제 데이터가 필요합니다. 
        로컬에서 실행하려면 다음 명령어로 pykrx를 설치해주세요:
        
        ```bash
        pip install pykrx
        ```
        """)
        st.stop()
    
    st.success("✅ 한국거래소 실제 데이터 연결됨")
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        # 터틀 시스템 초기화
        if 'turtle_system' not in st.session_state:
            st.session_state['turtle_system'] = TurtleTradingSystem()
        
        turtle_system = st.session_state['turtle_system']
        
        # 매개변수 설정
        donchian_period = st.slider("Donchian 기간", 10, 30, 20)
        atr_period = st.slider("ATR 기간", 10, 30, 20)
        risk_per_trade = st.slider("거래당 리스크 (%)", 1, 5, 2) / 100
        
        turtle_system.donchian_period = donchian_period
        turtle_system.atr_period = atr_period
        turtle_system.risk_per_trade = risk_per_trade
        
        st.markdown("---")
        
        # 포트폴리오 요약
        st.header("💼 포트폴리오 현황")
        
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)
            active_positions = positions_df[positions_df['상태'] == '보유중']
            signal_positions = positions_df[positions_df['상태'].str.contains('청산신호', na=False)]
            
            st.metric("전체 포지션", len(positions_df))
            st.metric("보유중", len(active_positions))
            st.metric("청산신호", len(signal_positions))
            
            if not active_positions.empty:
                total_investment = active_positions['투자금액'].sum()
                total_pnl = active_positions['손익'].sum()
                total_return = (total_pnl / total_investment * 100) if total_investment > 0 else 0
                
                st.metric("총 투자금", f"{total_investment:,}원")
                st.metric("총 손익", f"{total_pnl:+,}원")
                st.metric("수익률", f"{total_return:+.2f}%")
        else:
            st.info("포지션이 없습니다.")
        
        st.markdown("---")
        
        # 빠른 도움말
        with st.expander("📖 사용법"):
            st.markdown("""
            **1단계**: 종목 입력 후 신호 분석
            **2단계**: 진입 신호 확인
            **3단계**: 실제 매수 후 포지션 기록
            **4단계**: 정기적 현재가 업데이트
            **5단계**: 청산 신호시 매도 실행
            """)
    
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
                "분석할 종목을 입력하세요 (종목명 또는 종목코드)",
                placeholder="삼성전자\n005930\nNAVER\n카카오\nSK하이닉스",
                height=120,
                help="종목명(예: 삼성전자) 또는 종목코드(예: 005930)를 줄바꿈으로 구분하여 입력"
            )
        
        with col_example:
            st.markdown("**📝 입력 예시**")
            st.code("""삼성전자
NAVER
005930
카카오
LG화학""")
        
        if st.button("🔍 실시간 신호 분석 시작", type="primary", use_container_width=True):
            if user_input.strip():
                user_inputs = [x.strip() for x in user_input.split('\n') if x.strip()]
                
                with st.spinner("종목 검색 중..."):
                    tickers_dict = turtle_system.convert_to_tickers(user_inputs)
                
                if tickers_dict:
                    st.success(f"✅ {len(tickers_dict)}개 종목 확인됨: {', '.join(tickers_dict.values())}")
                    
                    # 신호 분석 실행
                    with st.spinner("실시간 데이터 분석 중..."):
                        results_df = turtle_system.analyze_signals(tickers_dict)
                    
                    if not results_df.empty:
                        # 분석 결과 저장
                        st.session_state['analysis_results'] = results_df
                        st.session_state['tickers_dict'] = tickers_dict
                        
                        # 진입 신호 종목 우선 표시
                        entry_signals = results_df[results_df['진입신호'] == True]
                        
                        if not entry_signals.empty:
                            st.success(f"🎯 **진입 신호 발생: {len(entry_signals)}개 종목**")
                            
                            for idx, row in entry_signals.iterrows():
                                with st.expander(
                                    f"🟢 {row['종목명']} ({row['종목코드']}) - 진입 신호 발생!", 
                                    expanded=True
                                ):
                                    # 종목 정보 표시
                                    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
                                    
                                    with info_col1:
                                        st.metric("현재가", f"{row['현재가']:,}원")
                                    with info_col2:
                                        st.metric("ATR(N)", f"{row['ATR(N)']:.1f}")
                                    with info_col3:
                                        st.metric("손절가", f"{row['손절가']:,}원")
                                    with info_col4:
                                        st.metric("거래량", f"{row['거래량']:,}")
                                    
                                    # 추가 정보
                                    col_add1, col_add2 = st.columns(2)
                                    with col_add1:
                                        st.info(f"**다음 매수가**: {row['추가매수1']:,}원 (+0.5N)")
                                    with col_add2:
                                        volume_surge_text = "🔥 급증" if row['거래량급증'] else "📊 정상"
                                        st.info(f"**거래량 상태**: {volume_surge_text}")
                                    
                                    st.markdown("---")
                                    st.markdown("##### 💰 실제 매수 후 포지션 기록")
                                    
                                    # 포지션 입력 폼
                                    pos_col1, pos_col2, pos_col3 = st.columns([2, 2, 1])
                                    
                                    with pos_col1:
                                        actual_price = st.number_input(
                                            "실제 매수가 (원)",
                                            value=int(row['현재가']),
                                            step=100,
                                            key=f"price_{row['종목코드']}",
                                            help="증권사에서 실제 체결된 가격을 입력하세요"
                                        )
                                    
                                    with pos_col2:
                                        quantity = st.number_input(
                                            "매수 수량 (주)",
                                            min_value=1,
                                            value=10,
                                            step=1,
                                            key=f"qty_{row['종목코드']}",
                                            help="실제 매수한 주식 수량을 입력하세요"
                                        )
                                    
                                    with pos_col3:
                                        st.markdown("<br>", unsafe_allow_html=True)
                                        if st.button(
                                            "➕ 포지션 추가", 
                                            key=f"add_{row['종목코드']}", 
                                            type="primary",
                                            help="실제 매수 완료 후 클릭하세요"
                                        ):
                                            if actual_price > 0 and quantity > 0:
                                                if 'position_manager' not in st.session_state:
                                                    st.session_state['position_manager'] = PositionManager()
                                                
                                                position_manager = st.session_state['position_manager']
                                                new_position = position_manager.add_position(
                                                    row['종목코드'],
                                                    row['종목명'],
                                                    actual_price,
                                                    quantity,
                                                    row['ATR(N)']
                                                )
                                                
                                                st.success(f"✅ {row['종목명']} 포지션이 성공적으로 추가되었습니다!")
                                                st.balloons()
                                                st.rerun()
                                            else:
                                                st.error("올바른 매수가와 수량을 입력해주세요.")
                                    
                                    # 투자 정보
