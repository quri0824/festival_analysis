# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (오류 수정본)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 상권(실험군)과 일반 상권(대조군)의 격차를 분석합니다.")

    # 1. 데이터 로드
    df_vac, _ = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, _ = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest_raw, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_budget_raw, _ = load_table_safely("지방자치단체세출예산", lambda: pd.DataFrame())

    # 2. 상권 매핑 정의
    exp_districts = ["춘천명동", "보령문화의전당", "서산터미널", "천안역", "천안종합버스터미널", "김제시장", "목포구도심", "하당신도심", "문경점촌흥덕", "안동구도심", "영주중앙", "김해시청/동상시장", "밀양원도심/삼문동", "활천동", "광양사거리", "노형오거리", "중앙사거리"]
    ctrl_districts = ["원주중앙/일산", "강경젓갈시장", "공주대", "공주웅진동", "논산시외버스터미널", "서귀포도심"]

    # 3. 데이터 전처리 (차분 계산 및 유연한 이름 매칭)
    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)

    def get_diff_safe(df, col_name, start_q="2022_1", end_q="2024_2"):
        # 컬럼명에서 해당 분기를 포함하는 것 찾기 (예: 2022_1Q, 2022.1/4 등 대응)
        s_col = [c for c in df.columns if start_q in str(c).replace(".", "_").replace("/", "_")]
        e_col = [c for c in df.columns if end_q in str(c).replace(".", "_").replace("/", "_")]
        
        if s_col and e_col:
            res = df.copy()
            res[col_name] = pd.to_numeric(res[e_col[0]], errors='coerce') - pd.to_numeric(res[s_col[0]], errors='coerce')
            return res[[detect_region_col(df), col_name]]
        return pd.DataFrame(columns=[detect_region_col(df), col_name])

    df_vac_diff = get_diff_safe(df_vac, "공실률변화량")
    df_rent_diff = get_diff_safe(df_rent, "임대료변화량")
    
    df_merge = pd.merge(df_vac_diff, df_rent_diff, on=detect_region_col(df_vac), how="inner")
    df_merge.rename(columns={detect_region_col(df_vac): "상권명"}, inplace=True)

    # [핵심 수정] 유연한 이름 매칭 로직
    def classify_district(name):
        clean_name = str(name).replace(" ", "")
        if any(exp.replace(" ", "") in clean_name for exp in exp_districts):
            return "축제 상권 (실험군)"
        if any(ctrl.replace(" ", "") in clean_name for ctrl in ctrl_districts):
            return "일반 상권 (대조군)"
        return None

    df_merge["상권 유형"] = df_merge["상권명"].apply(classify_district)
    df_analysis = df_merge.dropna(subset=["상권 유형"]).copy()

    # 데이터가 아예 없을 경우를 위한 안전장치
    if df_analysis.empty:
        st.error("⚠️ 선택된 23개 상권 데이터를 DB에서 찾을 수 없습니다. 상권명을 확인해주세요.")
        if not df_merge.empty:
            with st.expander("DB에 존재하는 상권명 목록 보기"):
                st.write(df_merge["상권명"].unique())
        return

    # 4. 외부방문자 및 예산 데이터 매칭
    df_fest = pivot_festival_data(df_fest_raw) if not df_fest_raw.empty else get_fallback_festival()
    foreign_col = find_col(df_fest.columns, ["외부방문자"]) or df_fest.columns[1]
    df_analysis["매칭키"] = df_analysis["상권명"].apply(extract_city_core)
    df_fest["매칭키"] = df_fest[df_fest.columns[0]].apply(extract_city_core)
    df_f_grp = df_fest.groupby("매칭키")[foreign_col].mean().reset_index()
    
    df_analysis = pd.merge(df_analysis, df_f_grp, on="매칭키", how="left")
    df_analysis[foreign_col] = df_analysis[foreign_col].fillna(0.1)
    df_analysis["점크기"] = df_analysis[foreign_col] * 50 + 10

    # 예산 데이터 처리
    df_analysis["예산규모_억원"] = 500 # 기본값
    if not df_budget_raw.empty:
        sec_col = find_col(df_budget_raw.columns, ["분야", "항목"])
        val_col = find_col(df_budget_raw.columns, ["세출", "예산", "금액"])
        if sec_col and val_col:
            df_b_filtered = df_budget_raw[df_budget_raw[sec_col].str.contains("국토|문화|관광", na=False)].copy()
            df_b_filtered["매칭키"] = df_b_filtered[detect_region_col(df_b_filtered)].apply(extract_city_core)
            df_b_grp = df_b_filtered.groupby("매칭키")[val_col].mean().reset_index()
            df_b_grp.columns = ["매칭키", "예산_val"]
            df_analysis = pd.merge(df_analysis, df_b_grp, on="매칭키", how="left")
            df_analysis["예산규모_억원"] = df_analysis["예산_val"].fillna(0) / 100000000

    # ------------------------------------------
    # 시각화 출력
    # ------------------------------------------
    exp_df = df_analysis[df_analysis["상권 유형"] == "축제 상권 (실험군)"]
    
    st.subheader("📍 축제 상권(실험군) 상권 변화 요약")
    c1, c2 = st.columns(2)
    # nan 방지를 위해 .mean() 호출 전 데이터 확인
    if not exp_df.empty:
        c1.metric("공실률 변화량(평균)", f"{exp_df['공실률변화량'].mean():+.2f} %p", delta_color="inverse")
        c2.metric("임대료 변화량(평균)", f"{exp_df['임대료변화량'].mean():+.3f} 천원/㎡")
    else:
        c1.metric("공실률 변화량(평균)", "데이터 없음")
        c2.metric("임대료 변화량(평균)", "데이터 없음")

    st.subheader("📊 차트 1. 축제 개최 여부 및 외부방문자 유입에 따른 상권 변화")
    fig1 = px.scatter(
        df_analysis, x="공실률변화량", y="임대료변화량", size="점크기", color="상권 유형",
        text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
        labels={"공실률변화량": "공실률 변화 (%p)", "임대료변화량": "임대료 변화 (천원/㎡)"},
        template="plotly_white", height=600
    )
    fig1.update_traces(textposition='top center')
    st.plotly_chart(fig1, use_container_width=True)

    st.write("---")
    st.subheader("🪐 차트 2. 지자체 예산 통제 시 상권 변화 검증")
    fig2 = px.scatter_3d(
        df_analysis, x="예산규모_억원", y="공실률변화량", z="임대료변화량", size="점크기",
        color="상권 유형", text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
        template="plotly_white", height=700
    )
    st.plotly_chart(fig2, use_container_width=True)
