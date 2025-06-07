import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pykrx.stock as stock
import gspread
from google.oauth2.service_account import Credentials
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

class TurtleTradingSystem:
    """터틀 트레이딩 시스템 메인 클래스"""
    
    def __init__(self):
        self.donchian_period = 20
        self.exit_period = 10
        self.atr_period = 20
        self.risk_per_trade = 0.02  # 2%
        self.max_pyramid_levels = 4  # 최대 4단계 추가매수
        
    def convert_to_tickers(self, user_inputs):
        """
        사용자 입력을 종목코드로 변환
        Args:
            user_inputs (list): 종목명 또는 종목코드 리스트
        Returns:
            dict: {종목코드: 종목명} 형태
        """
        result = {}
        
        # 전체 종목 리스트 가져오기 (캐싱 최적화)
        if 'all_tickers' not in st.session_state:
            st.session_state.all_tickers = stock.get_market_ticker_list()
            
        all_tickers = st.session_state.all_tickers
        
        for user_input in user_inputs:
            user_input = user_input.strip()
            
            # 6자리 숫자면 종목코드로 간주
            if user_input.isdigit() and len(user_input) == 6:
                try:
                    name = stock.get_market_ticker_name(user_input)
                    if name:
                        result[user_input] = name
                except:
                    st.warning(f"종목코드 {user_input}를 찾을 수 없습니다.")
            else:
                # 종목명으로 검색
                found = False
                for ticker in all_tickers:
                    try:
                        name = stock.get_market_ticker_name(ticker)
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
        """
        시장 데이터 수집 및 기술적 지표 계산
        Args:
            ticker (str): 종목코드
            days (int): 조회할 일수
        Returns:
            pd.DataFrame: OHLCV + 기술적 지표
        """
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
            
            # OHLCV 데이터 수집
            df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
            
            if df.empty:
                return None
                
            # 기술적 지표 계산
            df = self.calculate_technical_indicators(df)
            
            return df.tail(days)
            
        except Exception as e:
            st.error(f"{ticker} 데이터 수집 실패: {str(e)}")
            return None
    
    def calculate_technical_indicators(self, df):
        """
        기술적 지표 계산
        Args:
            df (pd.DataFrame): OHLCV 데이터
        Returns:
            pd.DataFrame: 기술적 지표 추가된 데이터
        """
        # True Range 계산
        df['prev_close'] = df['종가'].shift(1)
        df['tr1'] = df['고가'] - df['저가']
        df['tr2'] = abs(df['고가'] - df['prev_close'])
        df['tr3'] = abs(df['저가'] - df['prev_close'])
        df['TR'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR (Average True Range) 계산
        df['ATR'] = df['TR'].rolling(window=self.atr_period).mean()
        df['N'] = df['ATR']  # 터틀 시스템에서 N = ATR
        
        # Donchian Channels 계산
        df['donchian_upper'] = df['고가'].rolling(window=self.donchian_period).max()
        df['donchian_lower'] = df['저가'].rolling(window=self.exit_period).min()
        
        # 진입/청산 신호
        df['entry_signal'] = (df['종가'] > df['donchian_upper'].shift(1)) & \
                            (df['donchian_upper'].shift(1).notna())
        df['exit_signal'] = (df['종가'] < df['donchian_lower'].shift(1)) & \
                           (df['donchian_lower'].shift(1).notna())
        
        # 거래량 기반 필터 (선택적)
        df['volume_ma5'] = df['거래량'].rolling(5).mean()
        df['volume_surge'] = df['거래량'] > (df['volume_ma5'] * 1.5)
        
        return df
    
    def analyze_signals(self, tickers_dict):
        """
        전체 종목에 대한 신호 분석
        Args:
            tickers_dict (dict): {종목코드: 종목명}
        Returns:
            pd.DataFrame: 분석 결과
        """
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
                    '현재가': latest['종가'],
                    'ATR(N)': round(latest['N'], 2) if pd.notna(latest['N']) else 0,
                    'Donchian상단': round(latest['donchian_upper'], 0) if pd.notna(latest['donchian_upper']) else 0,
                    'Donchian하단': round(latest['donchian_lower'], 0) if pd.notna(latest['donchian_lower']) else 0,
                    '진입신호': latest['entry_signal'] if pd.notna(latest['entry_signal']) else False,
                    '청산신호': latest['exit_signal'] if pd.notna(latest['exit_signal']) else False,
                    '거래량급증': latest['volume_surge'] if pd.notna(latest['volume_surge']) else False,
                    '손절가': round(latest['종가'] - 2 * latest['N'], 0) if pd.notna(latest['N']) else 0,
                    '추가매수1': round(latest['종가'] + 0.5 * latest['N'], 0) if pd.notna(latest['N']) else 0,
                    '추가매수2': round(latest['종가'] + 1.0 * latest['N'], 0) if pd.notna(latest['N']) else 0,
                }
                
                results.append(result)
            
            progress_bar.progress((i + 1) / len(tickers_dict))
        
        progress_bar.empty()
        status_text.empty()
        
        return pd.DataFrame(results)

class PositionManager:
    """포지션 관리 클래스"""
    
    def __init__(self):
        self.position_columns = [
            '포지션ID', '종목코드', '종목명', '진입일', '진입가', 'ATR(N)', 
            '수량', '단계', '손절가', '다음매수가', '상태', '현재가', '손익', '손익률'
        ]
        
        # 세션 상태 초기화
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
            '손절가': round(entry_price - 2 * atr, 0),
            '다음매수가': round(entry_price + 0.5 * atr, 0) if stage < 4 else 0,
            '상태': '보유중',
            '현재가': entry_price,
            '손익': 0,
            '손익률': 0.0
        }
        
        st.session_state.user_positions.append(new_position)
        return new_position
    
    def update_position_prices(self, turtle_system):
        """보유 포지션 현재가 업데이트"""
        if not st.session_state.user_positions:
            return
            
        for i, position in enumerate(st.session_state.user_positions):
            if position['상태'] == '보유중':
                # 현재가 조회
                df = turtle_system.get_market_data(position['종목코드'], days=5)
                
                if df is not None and not df.empty:
                    current_price = df.iloc[-1]['종가']
                    
                    # 손익 계산
                    profit_loss = (current_price - position['진입가']) * position['수량']
                    profit_rate = ((current_price - position['진입가']) / position['진입가']) * 100
                    
                    # 청산 신호 체크
                    latest_data = df.iloc[-1]
                    if self.check_exit_signal(position, latest_data):
                        st.session_state.user_positions[i]['상태'] = '청산신호'
                    
                    # 현재가 업데이트
                    st.session_state.user_positions[i]['현재가'] = current_price
                    st.session_state.user_positions[i]['손익'] = profit_loss
                    st.session_state.user_positions[i]['손익률'] = profit_rate
    
    def check_exit_signal(self, position, latest_data):
        """청산 신호 확인"""
        current_price = latest_data['종가']
        stop_loss = position['손절가']
        donchian_lower = latest_data.get('donchian_lower', 0)
        
        # 손절 조건
        if current_price <= stop_loss:
            return True
            
        # Donchian 하단 하회 (익절)
        if donchian_lower > 0 and current_price <= donchian_lower:
            return True
            
        return False
    
    def close_position(self, position_index):
        """포지션 청산"""
        if 0 <= position_index < len(st.session_state.user_positions):
            st.session_state.user_positions[position_index]['상태'] = '청산완료'

class GoogleSheetsManager:
    """구글 시트 연동 관리 클래스"""
    
    def __init__(self):
        self.client = None
        
    def save_positions_to_sheets(self, sheet_url):
        """포지션을 구글시트에 저장"""
        try:
            # 실제 구현에서는 서비스 계정 인증 필요
            st.info("구글시트 연동 기능은 서비스 계정 설정 후 사용 가능합니다.")
            return True
        except Exception as e:
            st.error(f"구글시트 저장 실패: {str(e)}")
            return False

def create_chart(df, ticker_name):
    """터틀 트레이딩 차트 생성"""
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
    
    # 진입/청산 신호
    entry_signals = df[df['entry_signal']]
    if not entry_signals.empty:
        fig.add_trace(
            go.Scatter(
                x=entry_signals.index,
                y=entry_signals['종가'],
                mode='markers',
                name='진입신호',
                marker=dict(symbol='triangle-up', size=10, color='green')
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
                marker=dict(symbol='triangle-down', size=10, color='red')
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

def render_signal_analysis_tab():
    """신호 분석 탭"""
    st.header("📈 신호 분석")
    
    # 종목 입력
    user_input = st.text_area(
        "분석할 종목을 입력하세요 (종목명 또는 종목코드, 줄바꿈으로 구분)",
        placeholder="삼성전자\n005930\nNAVER\n카카오",
        height=100
    )
    
    if st.button("🔍 신호 분석 시작", type="primary"):
        if user_input.strip():
            # 입력 처리
            user_inputs = [x.strip() for x in user_input.split('\n') if x.strip()]
            
            with st.spinner("종목 코드 변환 중..."):
                turtle_system = st.session_state.get('turtle_system', TurtleTradingSystem())
                tickers_dict = turtle_system.convert_to_tickers(user_inputs)
            
            if tickers_dict:
                st.success(f"{len(tickers_dict)}개 종목 변환 완료")
                
                # 신호 분석
                with st.spinner("터틀 트레이딩 신호 분석 중..."):
                    results_df = turtle_system.analyze_signals(tickers_dict)
                
                if not results_df.empty:
                    # 결과 저장
                    st.session_state['analysis_results'] = results_df
                    st.session_state['tickers_dict'] = tickers_dict
                    st.session_state['turtle_system'] = turtle_system
                    
                    # 진입 신호 종목 먼저 표시
                    entry_signals = results_df[results_df['진입신호'] == True]
                    if not entry_signals.empty:
                        st.success(f"🟢 진입 신호 발생: {len(entry_signals)}개 종목")
                        
                        # 진입 신호 종목 상세 표시
                        for idx, row in entry_signals.iterrows():
                            with st.expander(f"🎯 {row['종목명']} ({row['종목코드']}) - 진입 신호", expanded=True):
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("현재가", f"{row['현재가']:,}원")
                                with col2:
                                    st.metric("ATR(N)", f"{row['ATR(N)']:.2f}")
                                with col3:
                                    st.metric("손절가", f"{row['손절가']:,}원")
                                with col4:
                                    st.metric("추가매수가", f"{row['추가매수1']:,}원")
                                
                                # 빠른 포지션 입력 폼
                                st.markdown("##### 💰 매수 기록 입력")
                                pos_col1, pos_col2, pos_col3 = st.columns([2, 2, 1])
                                
                                with pos_col1:
                                    actual_price = st.number_input(
                                        "실제 매수가",
                                        value=float(row['현재가']),
                                        step=100,
                                        key=f"price_{row['종목코드']}"
                                    )
                                
                                with pos_col2:
                                    quantity = st.number_input(
                                        "매수 수량",
                                        min_value=1,
                                        step=1,
                                        key=f"qty_{row['종목코드']}"
                                    )
                                
                                with pos_col3:
                                    st.markdown("<br>", unsafe_allow_html=True)
                                    if st.button(f"➕ 포지션 추가", key=f"add_{row['종목코드']}", type="primary"):
                                        if actual_price > 0 and quantity > 0:
                                            position_manager = st.session_state.get('position_manager', PositionManager())
                                            
                                            new_position = position_manager.add_position(
                                                row['종목코드'],
                                                row['종목명'],
                                                actual_price,
                                                quantity,
                                                row['ATR(N)']
                                            )
                                            
                                            st.session_state['position_manager'] = position_manager
                                            st.success(f"✅ {row['종목명']} 포지션이 추가되었습니다!")
                                            st.rerun()
                    else:
                        st.info("현재 진입 신호가 발생한 종목이 없습니다.")
                    
                    # 전체 결과 테이블
                    st.subheader("📊 전체 분석 결과")
                    
                    # 컬럼 선택 및 표시
                    display_columns = ['종목명', '현재가', 'ATR(N)', '진입신호', '청산신호', '손절가', '추가매수1']
                    st.dataframe(
                        results_df[display_columns].style.format({
                            '현재가': '{:,.0f}',
                            'ATR(N)': '{:.2f}',
                            '손절가': '{:,.0f}',
                            '추가매수1': '{:,.0f}'
                        }).applymap(
                            lambda x: 'background-color: #d4edda' if x == True else '',
                            subset=['진입신호']
                        ).applymap(
                            lambda x: 'background-color: #f8d7da' if x == True else '',
                            subset=['청산신호']
                        ),
                        use_container_width=True
                    )
                    
                else:
                    st.error("분석 결과가 없습니다.")
            else:
                st.error("유효한 종목을 찾을 수 없습니다.")
        else:
            st.warning("분석할 종목을 입력해주세요.")

def render_position_management_tab():
    """포지션 관리 탭"""
    st.header("💼 포지션 관리")
    
    # 포지션 매니저 초기화
    if 'position_manager' not in st.session_state:
        st.session_state['position_manager'] = PositionManager()
    
    position_manager = st.session_state['position_manager']
    
    # 상단 통계
    if st.session_state.user_positions:
        positions_df = pd.DataFrame(st.session_state.user_positions)
        active_positions = positions_df[positions_df['상태'] == '보유중']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("총 포지션", f"{len(positions_df)}개")
        with col2:
            st.metric("보유중", f"{len(active_positions)}개")
        with col3:
            total_investment = (active_positions['진입가'] * active_positions['수량']).sum() if not active_positions.empty else 0
            st.metric("총 투자금", f"{total_investment:,.0f}원")
        with col4:
            total_pnl = active_positions['손익'].sum() if not active_positions.empty else 0
            st.metric("총 손익", f"{total_pnl:,.0f}원")
    
    # 포지션 업데이트 버튼
    col_a, col_b, col_c = st.columns([1, 1, 2])
    
    with col_a:
        if st.button("🔄 현재가 업데이트"):
            if 'turtle_system' in st.session_state:
                with st.spinner("현재가 업데이트 중..."):
                    position_manager.update_position_prices(st.session_state['turtle_system'])
                    st.success("업데이트 완료!")
                    st.rerun()
            else:
                st.warning("먼저 신호 분석을 실행해주세요.")
    
    with col_b:
        if st.button("💾 구글시트 저장"):
            sheets_manager = GoogleSheetsManager()
            sheets_manager.save_positions_to_sheets("")
    
    # 보유 포지션 목록
    if st.session_state.user_positions:
        st.subheader("📋 보유 포지션")
        
        positions_df = pd.DataFrame(st.session_state.user_positions)
        
        # 포지션 상태별 분류
        active_df = positions_df[positions_df['상태'] == '보유중']
        signal_df = positions_df[positions_df['상태'] == '청산신호']
        closed_df = positions_df[positions_df['상태'] == '청산완료']
        
        # 보유중 포지션
        if not active_df.empty:
            st.markdown("##### 🟢 보유중")
            for idx, position in active_df.iterrows():
                with st.expander(f"{position['종목명']} - {position['수량']}주", expanded=True):
                    pos_col1, pos_col2, pos_col3, pos_col4 = st.columns(4)
                    
                    with pos_col1:
                        st.metric("진입가", f"{position['진입가']:,}원")
                        st.metric("현재가", f"{position['현재가']:,}원")
                    
                    with pos_col2:
                        st.metric("수량", f"{position['수량']}주")
                        st.metric("손절가", f"{position['손절가']:,}원")
                    
                    with pos_col3:
                        profit_color = "normal" if position['손익'] >= 0 else "inverse"
                        st.metric("손익", f"{position['손익']:,.0f}원", delta=f"{position['손익률']:.2f}%")
                        st.metric("다음매수가", f"{position['다음매수가']:,}원" if position['다음매수가'] > 0 else "최종단계")
                    
                    with pos_col4:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button(f"❌ 청산", key=f"close_{idx}"):
                            position_manager.close_position(idx)
                            st.success("포지션이 청산 처리되었습니다.")
                            st.rerun()
        
        # 청산 신호 포지션
        if not signal_df.empty:
            st.markdown("##### 🚨 청산 신호")
            for idx, position in signal_df.iterrows():
                with st.container():
                    st.error(f"🚨 {position['종목명']} - 청산 신호 발생! 현재가: {position['현재가']:,}원")
        
        # 청산 완료 포지션 (최근 5개만 표시)
        if not closed_df.empty:
            st.markdown("##### ✅ 청산 완료 (최근 5개)")
            recent_closed = closed_df.tail(5)
            st.dataframe(
                recent_closed[['종목명', '진입일', '진입가', '수량', '손익', '손익률']],
                use_container_width=True
            )
    else:
        st.info("📋 아직 등록된 포지션이 없습니다. 신호 분석 탭에서 진입 신호를 확인하고 포지션을 추가해주세요.")

def render_chart_analysis_tab():
    """차트 분석 탭"""
    st.header("📊 차트 분석")
    
    # 분석 결과가 있는 경우에만 표시
    if 'analysis_results' in st.session_state and 'tickers_dict' in st.session_state:
        results_df = st.session_state['analysis_results']
        tickers_dict = st.session_state['tickers_dict']
        turtle_system = st.session_state.get('turtle_system', TurtleTradingSystem())
        
        # 종목 선택
        selected_ticker = st.selectbox(
            "차트를 볼 종목 선택",
            options=list(tickers_dict.keys()),
            format_func=lambda x: f"{tickers_dict[x]} ({x})"
        )
        
        if selected_ticker:
            col_chart, col_info = st.columns([3, 1])
            
            with col_chart:
                with st.spinner("차트 생성 중..."):
                    df = turtle_system.get_market_data(selected_ticker)
                    
                    if df is not None and not df.empty:
                        chart = create_chart(df, tickers_dict[selected_ticker])
                        st.plotly_chart(chart, use_container_width=True)
            
            with col_info:
                # 종목 정보 표시
                ticker_data = results_df[results_df['종목코드'] == selected_ticker].iloc[0]
                
                st.metric("현재가", f"{ticker_data['현재가']:,}원")
                st.metric("ATR(N)", f"{ticker_data['ATR(N)']:.2f}")
                
                # 신호 상태
                if ticker_data['진입신호']:
                    st.success("🟢 진입 신호")
                elif ticker_data['청산신호']:
                    st.error("🔴 청산 신호")
                else:
                    st.info("⚪ 신호 없음")
                
                # 주요 가격대
                st.markdown("##### 📊 주요 가격대")
                st.write(f"**손절가**: {ticker_data['손절가']:,}원")
                st.write(f"**추가매수1**: {ticker_data['추가매수1']:,}원")
                st.write(f"**추가매수2**: {ticker_data['추가매수2']:,}원")
                st.write(f"**Donchian상단**: {ticker_data['Donchian상단']:,}원")
                st.write(f"**Donchian하단**: {ticker_data['Donchian하단']:,}원")
                
                # 거래량 정보
                if ticker_data['거래량급증']:
                    st.warning("⚡ 거래량 급증 감지")
    else:
        st.info("먼저 신호 분석을 실행해주세요.")

def render_strategy_guide_tab():
    """전략 가이드 탭"""
    st.header("📚 터틀 트레이딩 가이드")
    
    # 전략 개요
    st.markdown("""
    ## 🐢 터틀 트레이딩 시스템이란?
    
    터틀 트레이딩은 1980년대 리처드 데니스가 개발한 **추세추종 전략**으로, 
    체계적인 규칙에 따라 감정을 배제하고 거래하는 시스템입니다.
    """)
    
    # 핵심 규칙
    col_rule1, col_rule2 = st.columns(2)
    
    with col_rule1:
        st.markdown("""
        ### 📈 진입 규칙
        
        **1️⃣ Donchian 상단 돌파**
        - 종가가 20일 최고가 돌파시 진입
        - 추세의 시작을 포착
        
        **2️⃣ ATR 기반 포지션 사이징**
        - 변동성에 따른 과학적 수량 결정
        - 리스크 = 계좌의 2%로 제한
        
        **3️⃣ 피라미딩 (추가매수)**
        - 1단계: 진입가 + 0.5N
        - 2단계: 진입가 + 1.0N  
        - 3단계: 진입가 + 1.5N
        - 최대 4단계까지 확대
        """)
    
    with col_rule2:
        st.markdown("""
        ### 📉 청산 규칙
        
        **1️⃣ 손절 (Stop Loss)**
        - 진입가 - 2N에서 무조건 손절
        - 감정 개입 완전 차단
        
        **2️⃣ 익절 (Profit Taking)**
        - 10일 최저가 하회시 전량 매도
        - 추세 반전 신호 감지
        
        **3️⃣ 청산 우선순위**
        - 손절 > 익절 > 추가매수
        - 리스크 관리가 최우선
        """)
    
    # 실제 사용법
    st.markdown("""
    ## 🎯 웹앱 사용 단계
    
    ### 1단계: 신호 분석
    1. **신호 분석** 탭에서 관심 종목 입력
    2. 🔍 **신호 분석 시작** 버튼 클릭
    3. 진입 신호 발생 종목 확인
    
    ### 2단계: 실제 매수 & 기록
    1. 증권사 앱에서 **실제 매수** 실행
    2. 웹앱에서 **매수 기록 입력**:
       - 실제 체결가 입력
       - 매수 수량 입력
       - ➕ **포지션 추가** 클릭
    
    ### 3단계: 지속적 모니터링
    1. **포지션 관리** 탭에서 보유 현황 확인
    2. 🔄 **현재가 업데이트**로 손익 추적
    3. 청산 신호 발생시 실제 매도 실행
    
    ### 4단계: 기록 관리
    1. 💾 **구글시트 저장**으로 백업
    2. 📊 **차트 분석**으로 패턴 학습
    3. 지속적인 전략 개선
    """)
    
    # 주의사항
    st.markdown("""
    ## ⚠️ 중요한 주의사항
    
    ### 🚫 하지 말아야 할 것들
    - **감정적 판단**으로 손절가 변경
    - **신호 없는** 임의 매수
    - **과도한 레버리지** 사용
    - **포지션 기록** 누락
    
    ### ✅ 반드시 지켜야 할 것들
    - **2% 룰** 철저히 준수
    - **손절 신호** 즉시 실행
    - **매일 포지션** 업데이트
    - **체계적 기록** 유지
    
    ### 💡 성공의 비결
    - **일관성**: 규칙을 꾸준히 따르기
    - **인내심**: 큰 추세를 기다리기  
    - **기록**: 모든 거래를 문서화
    - **학습**: 지속적인 전략 개선
    """)

def main():
    """메인 Streamlit 앱"""
    st.set_page_config(
        page_title="터틀 트레이딩 시스템",
        page_icon="🐢",
        layout="wide"
    )
    
    # 메인 헤더
    st.title("🐢 터틀 트레이딩 시스템")
    st.markdown("**한국 주식시장을 위한 체계적 추세추종 전략**")
    st.markdown("---")
    
    # 사이드바 - 시스템 설정
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
        
        # 설정 적용
        turtle_system.donchian_period = donchian_period
        turtle_system.atr_period = atr_period
        turtle_system.risk_per_trade = risk_per_trade
        
        st.markdown("---")
        
        # 포트폴리오 요약 (사이드바)
        st.header("💼 포트폴리오 요약")
        
        if st.session_state.get('user_positions'):
            positions_df = pd.DataFrame(st.session_state.user_positions)
            active_positions = positions_df[positions_df['상태'] == '보유중']
            
            if not active_positions.empty:
                total_value = (active_positions['현재가'] * active_positions['수량']).sum()
                total_cost = (active_positions['진입가'] * active_positions['수량']).sum()
                total_pnl = total_value - total_cost
                
                st.metric("활성 포지션", f"{len(active_positions)}개")
                st.metric("총 투자금", f"{total_cost:,.0f}원")
                st.metric("총 평가액", f"{total_value:,.0f}원")
                st.metric("총 손익", f"{total_pnl:,.0f}원", 
                         delta=f"{(total_pnl/total_cost)*100:.1f}%" if total_cost > 0 else "0%")
            else:
                st.info("활성 포지션이 없습니다.")
        else:
            st.info("포지션을 추가해주세요.")
        
        st.markdown("---")
        
        # 구글 시트 설정
        st.header("📊 구글 시트 연동")
        sheet_url = st.text_input("구글 시트 URL", 
                                 placeholder="https://docs.google.com/spreadsheets/d/...")
        
        if sheet_url:
            st.success("✅ 시트 URL 설정됨")
        else:
            st.info("포지션 백업용 구글시트 URL을 입력하세요.")
    
    # 메인 탭 구성
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 신호 분석", 
        "💼 포지션 관리", 
        "📊 차트 분석", 
        "📚 전략 가이드"
    ])
    
    with tab1:
        render_signal_analysis_tab()
    
    with tab2:
        render_position_management_tab()
    
    with tab3:
        render_chart_analysis_tab()
    
    with tab4:
        render_strategy_guide_tab()
    
    # 하단 정보
    st.markdown("---")
    
    # 빠른 액션 버튼들
    st.markdown("### 🚀 빠른 액션")
    
    action_col1, action_col2, action_col3, action_col4 = st.columns(4)
    
    with action_col1:
        if st.button("🔍 신호 재분석", help="최신 데이터로 신호 재분석"):
            if 'tickers_dict' in st.session_state:
                # 기존 종목으로 재분석
                st.switch_page("신호 분석")
            else:
                st.info("먼저 종목을 입력하고 분석해주세요.")
    
    with action_col2:
        if st.button("💾 전체 백업", help="모든 포지션을 구글시트에 저장"):
            if sheet_url and st.session_state.get('user_positions'):
                sheets_manager = GoogleSheetsManager()
                if sheets_manager.save_positions_to_sheets(sheet_url):
                    st.success("백업 완료!")
            else:
                st.warning("구글시트 URL과 포지션 데이터가 필요합니다.")
    
    with action_col3:
        if st.button("🔄 전체 업데이트", help="모든 포지션 현재가 업데이트"):
            if 'position_manager' in st.session_state and 'turtle_system' in st.session_state:
                with st.spinner("전체 포지션 업데이트 중..."):
                    st.session_state['position_manager'].update_position_prices(
                        st.session_state['turtle_system']
                    )
                    st.success("전체 업데이트 완료!")
                    st.rerun()
            else:
                st.warning("업데이트할 포지션이 없습니다.")
    
    with action_col4:
        if st.button("🆘 긴급 청산", help="모든 포지션 청산 처리"):
            if st.session_state.get('user_positions'):
                if st.checkbox("⚠️ 정말 모든 포지션을 청산하시겠습니까?"):
                    # 모든 포지션 청산 처리
                    for i in range(len(st.session_state.user_positions)):
                        if st.session_state.user_positions[i]['상태'] == '보유중':
                            st.session_state.user_positions[i]['상태'] = '청산완료'
                    st.error("🚨 전체 포지션이 청산 처리되었습니다!")
                    st.rerun()
            else:
                st.info("청산할 포지션이 없습니다.")
    
    # 면책조항
    st.markdown("---")
    st.markdown("""
    <div style='background-color: #fff3cd; padding: 15px; border-radius: 5px; border-left: 4px solid #ffc107;'>
    <strong>⚠️ 면책조항</strong><br>
    이 웹앱은 <strong>교육 및 연구 목적</strong>으로 제작되었습니다. 
    실제 투자에 따른 손실에 대해 책임지지 않으며, 모든 투자 결정은 신중히 하시기 바랍니다.
    과거 수익률이 미래 수익을 보장하지 않습니다.
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
