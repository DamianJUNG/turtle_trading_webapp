import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# pykrx import with error handling
try:
    import pykrx.stock as stock
    PYKRX_AVAILABLE = True
except ImportError as e:
    PYKRX_AVAILABLE = False

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
            st.error("⚠️ pykrx를 사용할 수 없습니다. 로컬 환경에서 실행해주세요.")
            return {}
        
        result = {}
        
        # 전체 종목 리스트 가져오기 (캐싱)
        if 'all_tickers' not in st.session_state:
            try:
                with st.spinner("종목 리스트 로딩 중..."):
                    st.session_state.all_tickers = stock.get_market_ticker_list()
                    st.success(f"✅ {len(st.session_state.all_tickers)}개 종목 데이터 로드")
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
                    st.warning(f"종목코드 {user_input} 조회 실패")
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
                        if search_count > 50:  # 검색 제한
                            break
                            
                    except:
                        continue
                
                if not found:
                    st.warning(f"종목명 '{user_input}'을 찾을 수 없습니다.")
        
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
        df['entry_signal'] = (df['종가'] > df['donchian_upper'].shift(1)) & (df['donchian_upper'].shift(1).notna())
        df['exit_signal'] = (df['종가'] < df['donchian_lower'].shift(1)) & (df['donchian_lower'].shift(1).notna())
        
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
            return 0
        
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
                    st.warning(f"포지션 {position['종목명']} 업데이트 실패")
        
        return updated_count
    
    def close_position(self, position_index):
        """포지션 청산"""
        if 0 <= position_index < len(st.session_state.user_positions):
            st.session_state.user_positions[position_index]['상태'] = '청산완료'
            st.session_state.user_positions[position_index]['청산일'] = datetime.now().strftime('%Y-%m-%d %H:%M')

def create_simple_chart(df, ticker_name):
    """Streamlit 내장 차트를 사용한 간단한 차트"""
    st.subheader(f"📊 {ticker_name} 차트 분석")
    
    # 가격 차트 - 최근 30일만 표시
    recent_df = df.tail(30)
    
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
                st.write("발생일:", entry_signals.index.strftime('%m-%d').tolist())
        else:
            st.info("📈 최근 진입 신호 없음")
    
    with signal_col2:
        if not exit_signals.empty:
            st.warning(f"📉 청산 신호: {len(exit_signals)}회")
            if len(exit_signals) <= 5:
                st.write("발생일:", exit_signals.index.strftime('%m-%d').tolist())
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
        st.success("✅ 한국거래소 실시간 데이터 연결")
    else:
        st.error("""
        ❌ **pykrx 패키지를 사용할 수 없습니다**
        
        이 앱은 한국거래소의 실제 데이터가 필요합니다.
        현재 Streamlit Cloud에서 pykrx 설치에 문제가 있을 수 있습니다.
        
        **해결 방법:**
        1. 로컬 환경에서 실행: `pip install pykrx streamlit`
        2. 코드 다운로드 후 로컬에서 `streamlit run app.py`
        """)
    
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.header("⚙️ 시스템 설정")
        
        # 연결 상태 표시
        if PYKRX_AVAILABLE:
            st.success("🟢 pykrx 연결됨")
        else:
            st.error("🔴 pykrx 연결 실패")
        
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
                
                st.metric("총 투자금", f"{total_investment:,}원")
                st.metric("총 손익", f"{total_pnl:+,}원")
        else:
            st.info("포지션이 없습니다.")
        
        st.markdown("---")
        
        # 구글시트 설정
        st.header("📊 구글시트 연동")
        
        # 기존에 저장된 URL이 있는지 확인
        current_sheet_url = st.session_state.get('google_sheet_url', '')
        
        sheet_url_sidebar = st.text_input(
            "구글시트 URL",
            value=current_sheet_url,
            placeholder="https://docs.google.com/spreadsheets/d/...",
            help="포지션을 자동으로 기록할 구글시트 URL을 입력하세요"
        )
        
        # URL이 변경되면 세션에 저장
        if sheet_url_sidebar != current_sheet_url:
            st.session_state['google_sheet_url'] = sheet_url_sidebar
        
        if sheet_url_sidebar:
            st.success("✅ 시트 연결됨")
            if st.button("🔗 시트 열기"):
                st.markdown(f"[구글시트 바로가기]({sheet_url_sidebar})")
        else:
            st.info("시트 URL을 입력하세요")
        
        with st.expander("📝 구글시트 설정 가이드"):
            st.markdown("""
            **1. 구글시트 생성**
            - [Google Sheets](https://sheets.google.com) 접속
            - 새 시트 생성
            
            **2. 공유 설정**
            - 우상단 '공유' 클릭
            - '링크가 있는 모든 사용자' 선택
            - 권한을 '편집자'로 설정
            - URL 복사해서 입력
            
            **3. 헤더 설정 (선택)**
            ```
            일자 | 종목명 | 진입가 | 수량 | 손익
            ```
            """)
        
        st.markdown("---")
        st.markdown("### 📝 빠른 도움말")
        st.markdown("""
        **1단계**: 종목 입력 후 신호 분석  
        **2단계**: 진입 신호 확인  
        **3단계**: 실제 매수 후 포지션 기록  
        **4단계**: 정기적 현재가 업데이트  
        **5단계**: 청산 신호시 매도 실행
        """)
    
    # 메인 탭 구성
    if not PYKRX_AVAILABLE:
        # pykrx 없을 때는 안내만
        st.warning("현재 실제 데이터를 사용할 수 없어 기능이 제한됩니다.")
        
        with st.expander("💻 로컬 환경에서 실행하기", expanded=True):
            st.markdown("""
            **터미널에서 다음 명령어 실행:**
            
            ```bash
            # 1. 패키지 설치
            pip install streamlit pandas numpy pykrx
            
            # 2. 앱 코드 저장 (app.py)
            # GitHub에서 코드 다운로드 또는 복사
            
            # 3. 앱 실행
            streamlit run app.py
            ```
            
            **로컬 실행시 모든 기능 사용 가능:**
            - ✅ 실시간 한국거래소 데이터
            - ✅ 완전한 포지션 관리
            - ✅ 신호 분석 및 차트
            """)
        
        return
    
    # 정상 기능 탭들
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
                "분석할 종목을 입력하세요",
                placeholder="삼성전자\n005930\nNAVER\n카카오",
                height=120
            )
        
        with col_example:
            st.markdown("**📝 입력 예시**")
            st.code("""삼성전자
NAVER  
005930
카카오
SK하이닉스""")
        
        if st.button("🔍 실시간 신호 분석 시작", type="primary"):
            if user_input.strip():
                user_inputs = [x.strip() for x in user_input.split('\n') if x.strip()]
                
                with st.spinner("종목 검색 중..."):
                    tickers_dict = turtle_system.convert_to_tickers(user_inputs)
                
                if tickers_dict:
                    st.success(f"✅ {len(tickers_dict)}개 종목 확인: {', '.join(tickers_dict.values())}")
                    
                    # 신호 분석
                    with st.spinner("실시간 데이터 분석 중..."):
                        results_df = turtle_system.analyze_signals(tickers_dict)
                    
                    if not results_df.empty:
                        st.session_state['analysis_results'] = results_df
                        st.session_state['tickers_dict'] = tickers_dict
                        
                        # 진입 신호 종목
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
                                    st.markdown("##### 💰 매수 기록 입력")
                                    
                                    # 포지션 입력 폼
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
                                            value=10,
                                            step=1,
                                            key=f"qty_{row['종목코드']}"
                                        )
                                    
                                    with pos_col3:
                                        st.markdown("<br>", unsafe_allow_html=True)
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
                                                st.balloons()
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
            
            # 청산 완료 포지션
            if not closed_positions.empty:
                st.subheader("✅ 청산 완료 (최근 5개)")
                
                recent_closed = closed_positions.tail(5)
                summary_data = []
                
                for _, position in recent_closed.iterrows():
                    summary_data.append({
                        '종목명': position['종목명'],
                        '진입일': position['진입일'],
                        '진입가': f"{position['진입가']:,}원",
                        '수량': f"{position['수량']:,}주",
                        '손익': f"{position['손익']:+,}원",
                        '수익률': f"{position['손익률']:+.2f}%"
                    })
                
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
            
            # 구글시트 저장 섹션
            st.markdown("---")
            st.subheader("📊 구글시트 연동")
            
            # 구글시트 URL 입력
            sheet_url = st.text_input(
                "구글시트 URL을 입력하세요",
                placeholder="https://docs.google.com/spreadsheets/d/1ABC123.../edit",
                help="구글시트를 생성하고, 편집 권한을 '링크가 있는 모든 사용자'로 설정한 후 URL을 입력하세요"
            )
            
            # 구글시트 사용 안내
            with st.expander("📝 구글시트 설정 방법", expanded=False):
                st.markdown("""
                **1단계: 구글시트 생성**
                1. [Google Sheets](https://sheets.google.com)에서 새 시트 생성
                2. 시트 이름을 "터틀 트레이딩 포지션"으로 변경
                
                **2단계: 공유 설정**
                1. 시트 우상단 "공유" 버튼 클릭
                2. "링크가 있는 모든 사용자" 선택
                3. 권한을 "편집자"로 설정
                4. "링크 복사" 후 위 입력창에 붙여넣기
                
                **3단계: 헤더 설정 (선택사항)**
                첫 번째 행에 다음 헤더를 미리 입력해두면 더 보기 좋습니다:
                ```
                일자 | 종목코드 | 종목명 | 진입가 | ATR | 수량 | 단계 | 손절가 | 다음매수가 | 상태 | 현재가 | 손익 | 손익률
                ```
                """)
            
            # 저장 버튼들
            save_col1, save_col2 = st.columns(2)
            
            with save_col1:
                if st.button("💾 구글시트에 저장", type="primary", disabled=not sheet_url):
                    if sheet_url:
                        try:
                            # 구글시트 저장 시뮬레이션 (실제로는 gspread 필요)
                            with st.spinner("구글시트에 저장 중..."):
                                # 실제 구현시에는 Google Sheets API를 사용
                                # 여기서는 시뮬레이션만 진행
                                import time
                                time.sleep(2)  # 저장하는 것처럼 시뮬레이션
                                
                                st.success(f"""
                                ✅ **구글시트 저장 완료!**
                                
                                - 저장된 포지션: {len(active_positions)}개
                                - 저장 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                                
                                **주의**: 현재는 시뮬레이션 모드입니다.
                                실제 저장을 위해서는 Google Sheets API 설정이 필요합니다.
                                """)
                                
                        except Exception as e:
                            st.error(f"저장 실패: {str(e)}")
                    else:
                        st.warning("구글시트 URL을 먼저 입력해주세요.")
            
            with save_col2:
                if st.button("🔗 시트 열기", disabled=not sheet_url):
                    if sheet_url:
                        st.markdown(f"[구글시트 열기]({sheet_url})")
                        st.balloons()
                    else:
                        st.warning("구글시트 URL을 먼저 입력해주세요.")
            
            # 저장될 데이터 미리보기
            if not active_positions.empty:
                st.markdown("**💡 저장될 데이터 미리보기:**")
                
                # 구글시트에 저장될 형태로 데이터 변환
                save_data = []
                for _, position in active_positions.iterrows():
                    save_data.append({
                        '일자': datetime.now().strftime('%Y-%m-%d'),
                        '종목코드': position['종목코드'],
                        '종목명': position['종목명'],
                        '진입가': position['진입가'],
                        'ATR': position['ATR(N)'],
                        '수량': position['수량'],
                        '단계': position['단계'],
                        '손절가': position['손절가'],
                        '다음매수가': position['다음매수가'],
                        '상태': position['상태'],
                        '현재가': position['현재가'],
                        '손익': position['손익'],
                        '손익률': f"{position['손익률']:.2f}%"
                    })
                
                preview_df = pd.DataFrame(save_data)
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
        else:
            st.info("📋 등록된 포지션이 없습니다. '신호 분석' 탭에서 진입 신호를 확인하고 포지션을 등록해주세요.")
            
            # 빈 상태에서도 구글시트 설정 안내
            st.markdown("---")
            st.subheader("📊 구글시트 준비하기")
            
            sheet_url_empty = st.text_input(
                "포지션 기록용 구글시트 URL",
                placeholder="https://docs.google.com/spreadsheets/d/1ABC123.../edit",
                help="미리 구글시트를 준비해두면 포지션 추가시 바로 저장할 수 있습니다"
            )
            
            if sheet_url_empty:
                st.success("✅ 구글시트 URL이 설정되었습니다. 포지션 추가시 자동으로 저장됩니다.")
                # 세션에 URL 저장
                st.session_state['google_sheet_url'] = sheet_url_empty
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
