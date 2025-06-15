 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/app.py b/app.py
index 96c54385429f2eb804ac46b985f61ebe7af0c856..05f7f641155d9a9143654a2e9a11c13fe1b39cc1 100644
--- a/app.py
+++ b/app.py
@@ -536,27 +536,481 @@ LG화학""")
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
-                            
-                            for idx, row in entry_signals
+
+                            for idx, row in entry_signals.iterrows():
+                                with st.expander(f"🟢 {row['종목명']} - 진입 신호!", expanded=True):
+                                    # 종목 정보
+                                    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
+
+                                    with info_col1:
+                                        st.metric("현재가", f"{row['현재가']:,}원")
+                                    with info_col2:
+                                        st.metric("ATR(N)", f"{row['ATR(N)']:.1f}")
+                                    with info_col3:
+                                        st.metric("손절가", f"{row['손절가']:,}원")
+                                    with info_col4:
+                                        st.metric("거래량", f"{row['거래량']:,}")
+
+                                    st.markdown("---")
+                                    st.markdown("##### 💰 터틀 트레이딩 포지션 계산")
+
+                                    # 총 투자금액 확인
+                                    total_capital = st.session_state.get('total_capital', 10000000)
+
+                                    # 포지션 사이징 계산
+                                    position_calc = turtle_system.calculate_position_size(
+                                        total_capital,
+                                        row['현재가'],
+                                        row['ATR(N)']
+                                    )
+
+                                    if position_calc:
+                                        # 추천 포지션 정보 표시
+                                        calc_col1, calc_col2 = st.columns(2)
+
+                                        with calc_col1:
+                                            st.info(f"""
+                                            **🎯 추천 포지션 (2% 룰)**
+                                            - 수량: {position_calc['shares']:,}주
+                                            - 투자금액: {position_calc['investment_amount']:,}원
+                                            - 최대손실: {position_calc['max_loss']:,}원
+                                            """)
+
+                                        with calc_col2:
+                                            st.info(f"""
+                                            **📊 리스크 분석**
+                                            - 리스크 비율: {position_calc['risk_percentage']:.2f}%
+                                            - 손절가: {position_calc['stop_loss']:,}원
+                                            - 1차추가: {position_calc['add_buy_1']:,}원
+                                            """)
+
+                                        # 사용자 입력 (추천값으로 미리 설정)
+                                        pos_col1, pos_col2, pos_col3 = st.columns([2, 2, 1])
+
+                                        with pos_col1:
+                                            actual_price = st.number_input(
+                                                "실제 매수가",
+                                                value=int(row['현재가']),
+                                                step=100,
+                                                key=f"price_{row['종목코드']}"
+                                            )
+
+                                        with pos_col2:
+                                            quantity = st.number_input(
+                                                "매수 수량",
+                                                min_value=1,
+                                                value=position_calc['shares'] if position_calc['shares'] > 0 else 10,
+                                                step=1,
+                                                key=f"qty_{row['종목코드']}",
+                                                help=f"추천 수량: {position_calc['shares']}주"
+                                            )
+
+                                        with pos_col3:
+                                            st.markdown("<br>", unsafe_allow_html=True)
+                                            if st.button(f"➕ 포지션 추가", key=f"add_{row['종목코드']}", type="primary"):
+                                                if actual_price > 0 and quantity > 0:
+                                                    # 실제 투자금액 계산
+                                                    actual_investment = actual_price * quantity
+
+                                                    # 남은 투자금 확인
+                                                    used_capital = 0
+                                                    if st.session_state.get('user_positions'):
+                                                        active_pos = pd.DataFrame(st.session_state.user_positions)
+                                                        active_pos = active_pos[active_pos['상태'] == '보유중']
+                                                        if not active_pos.empty:
+                                                            used_capital = active_pos['투자금액'].sum()
+
+                                                    remaining_capital = total_capital - used_capital
+
+                                                    if actual_investment > remaining_capital:
+                                                        st.error(f"""
+                                                        ❌ **투자금 부족!**
+                                                        - 필요금액: {actual_investment:,}원
+                                                        - 남은금액: {remaining_capital:,}원
+                                                        - 부족금액: {actual_investment - remaining_capital:,}원
+                                                        """)
+                                                    else:
+                                                        if 'position_manager' not in st.session_state:
+                                                            st.session_state['position_manager'] = PositionManager()
+
+                                                        position_manager = st.session_state['position_manager']
+                                                        position_manager.add_position(
+                                                            row['종목코드'],
+                                                            row['종목명'],
+                                                            actual_price,
+                                                            quantity,
+                                                            row['ATR(N)']
+                                                        )
+
+                                                        st.success(f"✅ {row['종목명']} 포지션 추가!")
+                                                        st.balloons()
+                                                        st.rerun()
+
+                                        # 투자 비교 분석
+                                        if actual_price > 0 and quantity > 0:
+                                            actual_investment = actual_price * quantity
+                                            actual_max_loss = quantity * (actual_price - position_calc['stop_loss'])
+                                            actual_risk_pct = (actual_max_loss / total_capital) * 100
+
+                                            if actual_risk_pct > 2.5:
+                                                st.error(f"⚠️ 리스크가 {actual_risk_pct:.2f}%로 권장치(2%)를 초과합니다!")
+                                            elif actual_risk_pct > 2.0:
+                                                st.warning(f"⚠️ 리스크가 {actual_risk_pct:.2f}%입니다.")
+                                            else:
+                                                st.success(f"✅ 리스크 {actual_risk_pct:.2f}% - 적절한 포지션입니다.")
+                                    else:
+                                        st.error("포지션 계산에 실패했습니다.")
+                        else:
+                            st.info("🔍 현재 진입 신호가 없습니다.")
+
+                        # 전체 결과 표시
+                        st.markdown("---")
+                        st.subheader("📊 전체 분석 결과")
+
+                        # 요약 통계
+                        entry_count = results_df['진입신호'].sum()
+                        exit_count = results_df['청산신호'].sum()
+                        volume_surge_count = results_df['거래량급증'].sum()
+
+                        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
+                        with summary_col1:
+                            st.metric("분석 종목", len(results_df))
+                        with summary_col2:
+                            st.metric("진입 신호", entry_count)
+                        with summary_col3:
+                            st.metric("청산 신호", exit_count)
+                        with summary_col4:
+                            st.metric("거래량 급증", volume_surge_count)
+
+                        # 결과 테이블
+                        display_df = results_df[['종목명', '현재가', 'ATR(N)', '진입신호', '청산신호', '손절가']].copy()
+
+                        st.dataframe(
+                            display_df,
+                            column_config={
+                                '현재가': st.column_config.NumberColumn('현재가', format='%d원'),
+                                'ATR(N)': st.column_config.NumberColumn('ATR(N)', format='%.2f'),
+                                '손절가': st.column_config.NumberColumn('손절가', format='%d원'),
+                                '진입신호': st.column_config.CheckboxColumn('진입신호'),
+                                '청산신호': st.column_config.CheckboxColumn('청산신호')
+                            },
+                            use_container_width=True
+                        )
+                    else:
+                        st.error("분석 결과를 생성할 수 없습니다.")
+                else:
+                    st.error("입력하신 종목을 찾을 수 없습니다.")
+            else:
+                st.warning("분석할 종목을 입력해주세요.")
+
+    with tab2:
+        st.header("💼 포지션 관리")
+
+        # 관리 도구
+        if st.session_state.get('user_positions'):
+            tool_col1, tool_col2, tool_col3 = st.columns(3)
+
+            with tool_col1:
+                if st.button("🔄 현재가 업데이트"):
+                    if 'position_manager' not in st.session_state:
+                        st.session_state['position_manager'] = PositionManager()
+
+                    with st.spinner("현재가 업데이트 중..."):
+                        updated_count = st.session_state['position_manager'].update_positions(turtle_system)
+                        st.success(f"✅ {updated_count}개 포지션 업데이트!")
+                        st.rerun()
+
+            with tool_col2:
+                if st.button("💾 백업 저장"):
+                    positions_df = pd.DataFrame(st.session_state.user_positions)
+                    csv_data = positions_df.to_csv(index=False, encoding='utf-8-sig')
+                    st.download_button(
+                        label="📄 CSV 다운로드",
+                        data=csv_data,
+                        file_name=f"turtle_positions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
+                        mime="text/csv"
+                    )
+
+            with tool_col3:
+                if st.button("🗑️ 전체 초기화"):
+                    if st.checkbox("정말 모든 데이터를 삭제하시겠습니까?"):
+                        st.session_state.user_positions = []
+                        st.success("모든 포지션이 삭제되었습니다.")
+                        st.rerun()
+
+        # 포지션 목록
+        if st.session_state.get('user_positions'):
+            positions_df = pd.DataFrame(st.session_state.user_positions)
+
+            # 상태별 분류
+            active_positions = positions_df[positions_df['상태'] == '보유중']
+            signal_positions = positions_df[positions_df['상태'].str.contains('청산신호', na=False)]
+            closed_positions = positions_df[positions_df['상태'] == '청산완료']
+
+            # 보유중 포지션
+            if not active_positions.empty:
+                st.subheader("🟢 보유중 포지션")
+
+                for original_idx in active_positions.index:
+                    position = active_positions.loc[original_idx]
+
+                    profit_emoji = "🟢" if position['손익'] >= 0 else "🔴"
+                    profit_text = f"{position['손익']:+,}원 ({position['손익률']:+.2f}%)"
+
+                    with st.expander(f"{profit_emoji} {position['종목명']} | {position['수량']}주 | {profit_text}"):
+                        # 상세 정보
+                        detail_col1, detail_col2, detail_col3 = st.columns(3)
+
+                        with detail_col1:
+                            st.write(f"**진입일**: {position['진입일']}")
+                            st.write(f"**진입가**: {position['진입가']:,}원")
+                            st.write(f"**현재가**: {position['현재가']:,}원")
+
+                        with detail_col2:
+                            st.write(f"**수량**: {position['수량']:,}주")
+                            st.write(f"**투자금액**: {position['투자금액']:,}원")
+                            st.write(f"**ATR(N)**: {position['ATR(N)']}")
+
+                        with detail_col3:
+                            st.write(f"**손절가**: {position['손절가']:,}원")
+                            if position['다음매수가'] > 0:
+                                st.write(f"**다음매수가**: {position['다음매수가']:,}원")
+                            else:
+                                st.write("**최종단계**: 추가매수 없음")
+
+                        # 청산 버튼
+                        if st.button(f"❌ 청산", key=f"close_{original_idx}"):
+                            if 'position_manager' not in st.session_state:
+                                st.session_state['position_manager'] = PositionManager()
+
+                            # 해당 포지션의 실제 인덱스 찾기
+                            for i, p in enumerate(st.session_state.user_positions):
+                                if p['포지션ID'] == position['포지션ID']:
+                                    st.session_state['position_manager'].close_position(i)
+                                    break
+
+                            st.success(f"{position['종목명']} 포지션 청산 완료!")
+                            st.rerun()
+
+            # 청산 신호 포지션
+            if not signal_positions.empty:
+                st.subheader("🚨 청산 신호 발생")
+
+                for original_idx in signal_positions.index:
+                    position = signal_positions.loc[original_idx]
+                    signal_type = "손절" if "손절" in position['상태'] else "익절"
+
+                    st.error(f"""
+                    🚨 **{position['종목명']} - {signal_type} 신호!**
+                    - 현재가: {position['현재가']:,}원
+                    - 손익: {position['손익']:+,}원 ({position['손익률']:+.2f}%)
+                    - **즉시 매도를 고려하세요!**
+                    """)
+        else:
+            st.info("📋 등록된 포지션이 없습니다. '신호 분석' 탭에서 진입 신호를 확인하고 포지션을 등록해주세요.")
+
+    with tab3:
+        st.header("📊 차트 분석")
+
+        if 'analysis_results' in st.session_state and 'tickers_dict' in st.session_state:
+            results_df = st.session_state['analysis_results']
+            tickers_dict = st.session_state['tickers_dict']
+
+            # 종목 선택
+            selected_ticker = st.selectbox(
+                "차트를 분석할 종목 선택",
+                options=list(tickers_dict.keys()),
+                format_func=lambda x: f"{tickers_dict[x]} ({x})"
+            )
+
+            if selected_ticker:
+                col_chart, col_info = st.columns([3, 1])
+
+                with col_chart:
+                    with st.spinner("차트 데이터 로딩 중..."):
+                        df = turtle_system.get_market_data(selected_ticker, days=60)
+
+                        if df is not None and not df.empty:
+                            create_simple_chart(df, tickers_dict[selected_ticker])
+                        else:
+                            st.error("차트 데이터를 불러올 수 없습니다.")
+
+                with col_info:
+                    # 종목 정보
+                    ticker_data = results_df[results_df['종목코드'] == selected_ticker]
+
+                    if not ticker_data.empty:
+                        ticker_info = ticker_data.iloc[0]
+
+                        st.markdown(f"### {ticker_info['종목명']}")
+                        st.markdown(f"**코드**: {ticker_info['종목코드']}")
+
+                        # 신호 상태
+                        if ticker_info['진입신호']:
+                            st.success("🟢 진입 신호")
+                        elif ticker_info['청산신호']:
+                            st.error("🔴 청산 신호")
+                        else:
+                            st.info("⚪ 신호 없음")
+
+                        # 주요 지표
+                        st.metric("현재가", f"{ticker_info['현재가']:,}원")
+                        st.metric("ATR(N)", f"{ticker_info['ATR(N)']:.2f}")
+
+                        st.markdown("**주요 가격대**")
+                        st.write(f"• 손절가: {ticker_info['손절가']:,}원")
+                        st.write(f"• 추가매수가: {ticker_info['추가매수1']:,}원")
+                        st.write(f"• Donchian상단: {ticker_info['Donchian상단']:,}원")
+                        st.write(f"• Donchian하단: {ticker_info['Donchian하단']:,}원")
+
+                        # 거래량 정보
+                        if ticker_info['거래량급증']:
+                            st.warning("⚡ 거래량 급증")
+                        else:
+                            st.info("📊 정상 거래량")
+        else:
+            st.info("먼저 '신호 분석' 탭에서 종목 분석을 실행해주세요.")
+
+    with tab4:
+        st.header("📚 터틀 트레이딩 전략 가이드")
+
+        # 전략 개요
+        st.markdown("""
+        ## 🐢 터틀 트레이딩이란?
+
+        터틀 트레이딩은 1980년대 리처드 데니스가 개발한 **추세추종 전략**입니다.
+        감정을 배제하고 체계적인 규칙에 따라 거래하는 것이 핵심입니다.
+        """)
+
+        # 핵심 규칙
+        rule_col1, rule_col2 = st.columns(2)
+
+        with rule_col1:
+            st.markdown("""
+            ### 📈 진입 규칙
+
+            **1️⃣ Donchian 상단 돌파**
+            - 종가가 20일 최고가 돌파시 진입
+            - 새로운 상승 추세의 시작 포착
+
+            **2️⃣ ATR 기반 포지션 사이징**
+            - ATR(Average True Range)로 변동성 측정
+            - 거래당 리스크를 계좌의 2%로 제한
+
+            **3️⃣ 피라미딩 (추가매수)**
+            - 수익 시 포지션 확대
+            - 최대 4단계까지 추가매수
+            """)
+
+        with rule_col2:
+            st.markdown("""
+            ### 📉 청산 규칙
+
+            **1️⃣ 손절 (Stop Loss)**
+            - 진입가 - 2N(ATR) 하락시 무조건 손절
+            - 감정 개입 완전 차단
+
+            **2️⃣ 익절 (Profit Taking)**
+            - 10일 최저가 하회시 전량 매도
+            - 추세 반전 신호 조기 감지
+
+            **3️⃣ 청산 우선순위**
+            - 손절 > 익절 > 추가매수
+            - 리스크 관리가 최우선
+            """)
+
+        # 사용법 가이드
+        st.markdown("---")
+        st.markdown("## 🎯 웹앱 사용 가이드")
+
+        st.markdown("""
+        ### 📝 단계별 사용법
+
+        **1단계: 투자금 설정**
+        1. 사이드바에서 총 투자금액 입력
+        2. 리스크 매개변수 설정 (Donchian, ATR 기간)
+
+        **2단계: 신호 분석**
+        1. '신호 분석' 탭에서 관심 종목 입력
+        2. '🔍 실시간 신호 분석 시작' 클릭
+        3. 진입 신호 발생 종목 확인
+
+        **3단계: 포지션 계산 & 매수**
+        1. 🎯 추천 포지션 (2% 룰) 확인
+        2. 증권사 앱에서 **실제 매수** 실행
+        3. 웹앱에서 실제 체결가와 수량 입력
+        4. '➕ 포지션 추가'로 기록
+
+        **4단계: 지속적 모니터링**
+        1. '포지션 관리' 탭에서 보유 현황 확인
+        2. '🔄 현재가 업데이트'로 손익 추적
+        3. 청산 신호 발생시 즉시 매도
+
+        **5단계: 기록 관리**
+        1. '💾 백업 저장'으로 거래 기록 보관
+        2. '📊 차트 분석'으로 패턴 학습
+        3. 지속적인 전략 개선
+        """)
+
+        # 주의사항
+        st.markdown("---")
+        st.markdown("## ⚠️ 중요한 주의사항")
+
+        warning_col1, warning_col2 = st.columns(2)
+
+        with warning_col1:
+            st.markdown("""
+            ### 🚫 하지 말아야 할 것들
+            - 감정적 판단으로 손절가 변경
+            - 신호 없는 임의 매수
+            - 과도한 레버리지 사용
+            - 포지션 기록 누락
+            - 2% 룰 무시
+            """)
+
+        with warning_col2:
+            st.markdown("""
+            ### ✅ 반드시 지켜야 할 것들
+            - **2% 룰** 철저히 준수
+            - **손절 신호** 즉시 실행
+            - **매일 포지션** 업데이트
+            - **체계적 기록** 유지
+            - **자금 관리** 엄격히 준수
+            """)
+
+        # 면책조항
+        st.markdown("---")
+        st.warning("""
+        **⚠️ 면책조항**
+
+        이 웹앱은 교육 및 연구 목적으로 제작되었습니다.
+        - 실제 투자 손실에 대해 책임지지 않습니다
+        - 과거 수익률이 미래 수익을 보장하지 않습니다
+        - 모든 투자 결정은 신중히 하시기 바랍니다
+        - 충분한 백테스팅과 검증을 권장합니다
+        """)
+
+if __name__ == "__main__":
+    main()
 
EOF
)
