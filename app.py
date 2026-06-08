import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

# ==========================================
# 0. 앱 기본 설정 및 예외 처리
# ==========================================
st.set_page_config(
    page_title="공공데이터 분석 대시보드",
    page_icon="📊",
    layout="wide"
)

DB_FILE = "project1.db"

if not os.path.exists(DB_FILE):
    st.error("데이터베이스 파일(project1.db)을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
    st.stop()

# 헬퍼 함수: DB 내 실제 존재하는 테이블 리스트 반환
def get_db_tables():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()

# 헬퍼 함수: 테이블명 오타 보정 매칭
def find_matching_table(target_name):
    available_tables = get_db_tables()
    if target_name in available_tables:
        return target_name
    target_stripped = target_name.replace(" ", "")
    for t in available_tables:
        if t.replace(" ", "") == target_stripped:
            return t
    return None

# 헬퍼 함수: 안전한 데이터 로딩 (Fallback 내장)
def load_table_safely(table_name, fallback_data_func):
    matched_table = find_matching_table(table_name)
    if not matched_table:
        return fallback_data_func(), True
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(f"SELECT * FROM `{matched_table}`", conn)
        return df, False
    except Exception:
        return fallback_data_func(), True
    finally:
        conn.close()

# 헬퍼 함수: 컬럼명 매칭
def find_col(columns, search_terms):
    for term in search_terms:
        for col in columns:
            clean_col = str(col).replace(" ", "").replace("·", "").replace("_", "").lower()
            clean_term = str(term).replace(" ", "").replace("·", "").replace("_", "").lower()
            if clean_term in clean_col:
                return col
    return None

# 동적 엔진: 행정구역(지역)이 포함된 컬럼 자동 검출
def detect_region_col(df):
    name_match = find_col(df.columns, ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명", "구분"])
    if name_match:
        return name_match
    obj_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]

# [정밀 텍스트 파서] 지명 추출기
def extract_city_core(text):
    text_str = str(text).strip()
    special_mapping = {"한산": "서천", "서천": "서천", "탐라": "제주", "제주": "제주", "보령": "보령", "춘천": "춘천", "천안": "천안"}
    for key, val in special_mapping.items():
        if key in text_str: return val
    keywords = ["춘천", "정선", "임실", "고령", "천안", "순창", "남원", "강릉", "울릉", "여수", "경주", "안동", "보령", "목포", "김제", "문경", "영주", "김해", "밀양", "광양", "서귀포", "공주", "논산", "원주"]
    for city in keywords:
        if city in text_str: return city
    words = text_str.split()
    if words:
        target_word = words[-1]
        return target_word.replace("시", "").replace("군", "").replace("구", "").strip()
    return text_str[:2]

get_short_region = extract_city_core

# 가로 형태 데이터를 세로 형태로 변환
def melt_quarters(df, value_name):
    if df.empty: return pd.DataFrame(), None
    region_col = detect_region_col(df)
    quarter_cols = [c for c in df.columns if c != region_col and (any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or any(str(yr) in str(c) for yr in range(2015, 2027)))]
    df_melted = df.melt(id_vars=[region_col], value_vars=quarter_cols, var_name="분기", value_name=value_name)
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col

# 세로형 축제 테이블 피벗
def pivot_festival_data(df_fest):
    if df_fest.empty or len(df_fest.columns) < 5: return pd.DataFrame()
    fest_name_col, period_col, year_col, indicator_col, value_col = df_fest.columns[:5]
    df_filtered = df_fest[df_fest[period_col].astype(str).str.contains("축제기간|축제", na=False)].copy()
    if df_filtered.empty: df_filtered = df_fest.copy()
    try:
        return df_filtered.pivot_table(index=[fest_name_col, year_col], columns=indicator_col, values=value_col, aggfunc="mean").reset_index()
    except: return pd.DataFrame()

# ==========================================
# Fallback 시뮬레이션용 예비 데이터 생성기
# ==========================================
def get_fallback_festival():
    return pd.DataFrame({
        "축제명": ["순창장류축제", "한산모시문화제", "임실N치즈축제", "고령대가야축제", "천안흥타령축제", "탐라문화제", "정선아리랑제", "춘천마임축제"],
        "외부방문자 유입": [0.83, 0.99, 0.85, 0.89, 0.79, 0.70, 0.51, 0.40],
        "관광소비": [0.52, 0.48, 0.89, 0.85, 0.70, 0.80, 0.61, 0.52]
    })

def get_fallback_consume():
    return pd.DataFrame({"연도": [2021, 2022, 2023], "쇼핑업 소비액": [15e6, 18e6, 21e6], "숙박업 소비액": [5e6, 4e6, 4e6]})

def get_fallback_property_vacancy():
    return pd.DataFrame({"상권명": ["춘천명동", "보령문화의전당", "원주중앙/일산"], "2022_1Q": [12.1, 14.5, 8.5], "2024_2Q": [15.0, 17.5, 9.0]})

def get_fallback_property_rent():
    return pd.DataFrame({"상권명": ["춘천명동", "보령문화의전당", "원주중앙/일산"], "2022_1Q": [3.2, 2.5, 5.1], "2024_2Q": [3.1, 2.4, 5.2]})

def get_fallback_cost():
    return pd.DataFrame({"자치단체": ["강원도 춘천시", "충청남도 서천군"], "총비용": [12e8, 8e8], "순원가": [9e8, 7e8]})

def get_fallback_extinction():
    return pd.DataFrame({"구분": ["지방소멸 심각성", "대응 효과성"], "평균": [4.42, 2.23], "표준편차": [0.83, 1.01]})

# ==========================================
# 1. 페이지 1: 축제 현황 분석
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 관광 유형 및 소비 패턴 분석")
    df_raw, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_consume, is_c_mock = load_table_safely("업종별소비액", get_fallback_consume)
    
    if not is_f_mock: df_fest = pivot_festival_data(df_raw)
    else: df_fest = df_raw.copy()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📍 관광유형 사분면 모델")
        fig1 = px.scatter(df_fest, x=df_fest.columns[2], y=df_fest.columns[1], text=df_fest.columns[0], template="plotly_white")
        st.plotly_chart(fig1, use_container_width=True)
    with col2:
        st.subheader("📈 연도별 업종 소비 흐름")
        df_melt = df_consume.melt(id_vars=[df_consume.columns[0]])
        fig2 = px.line(df_melt, x=df_consume.columns[0], y="value", color="variable", markers=True, template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (수정완료)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 상권(실험군)과 일반 상권(대조군)의 격차를 정적 분산 구조와 시계열 트렌드로 비교 분석합니다.")

    # 1. 데이터 로드
    df_vac, _ = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, _ = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest_raw, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_budget_raw, _ = load_table_safely("지방자치단체세출예산", lambda: pd.DataFrame())

    # 2. 상권 매핑 정의
    exp_districts = ["춘천명동", "보령문화의전당", "서산터미널", "천안역", "천안종합버스터미널", "김제시장", "목포구도심", "하당신도심", "문경점촌흥덕", "안동구도심", "영주중앙", "김해시청/동상시장", "밀양원도심/삼문동", "활천동", "광양사거리", "노형오거리", "중앙사거리"]
    ctrl_districts = ["원주중앙/일산", "강경젓갈시장", "공주대", "공주웅진동", "논산시외버스터미널", "서귀포도심"]

    # 3. 데이터 전처리 (오류 수정 로직)
    def get_diff_safe(df, col_name, start_q="2022_1", end_q="2024_2"):
        s_col = [c for c in df.columns if start_q in str(c).replace(".", "_").replace("/", "_")]
        e_col = [c for c in df.columns if end_q in str(c).replace(".", "_").replace("/", "_")]
        if s_col and e_col:
            res = df.copy()
            res[col_name] = pd.to_numeric(res[e_col[0]], errors='coerce') - pd.to_numeric(res[s_col[0]], errors='coerce')
            return res[[detect_region_col(df), col_name]]
        return pd.DataFrame()

    df_vac_diff = get_diff_safe(df_vac, "공실률변화량")
    df_rent_diff = get_diff_safe(df_rent, "임대료변화량")
    
    if df_vac_diff.empty or df_rent_diff.empty:
        st.error("데이터에서 2022년 1분기 또는 2024년 2분기 컬럼을 찾을 수 없습니다.")
        return

    df_merge = pd.merge(df_vac_diff, df_rent_diff, on=detect_region_col(df_vac), how="inner")
    df_merge.rename(columns={detect_region_col(df_vac): "상권명"}, inplace=True)

    # 유연한 이름 매칭 로직 (nan 해결 핵심)
    def classify_district(name):
        clean_name = str(name).replace(" ", "")
        if any(exp.replace(" ", "") in clean_name for exp in exp_districts): return "축제 상권 (실험군)"
        if any(ctrl.replace(" ", "") in clean_name for ctrl in ctrl_districts): return "일반 상권 (대조군)"
        return None

    df_merge["상권 유형"] = df_merge["상권명"].apply(classify_district)
    df_analysis = df_merge.dropna(subset=["상권 유형"]).copy()

    if df_analysis.empty:
        st.warning("⚠️ 매칭된 상권 데이터가 없습니다. DB의 상권명과 코드의 상권명을 대조해보세요.")
        with st.expander("DB 상권명 목록"): st.write(df_merge["상권명"].unique())
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
    df_analysis["예산규모_억원"] = 500.0
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

    # 시각화 출력
    exp_df = df_analysis[df_analysis["상권 유형"] == "축제 상권 (실험군)"]
    st.subheader("📍 축제 상권(실험군) 상권 변화 요약")
    c1, c2 = st.columns(2)
    c1.metric("공실률 변화량(평균)", f"{exp_df['공실률변화량'].mean():+.2f} %p", delta_color="inverse")
    c2.metric("임대료 변화량(평균)", f"{exp_df['임대료변화량'].mean():+.3f} 천원/㎡")

    st.subheader("📊 차트 1. 축제 개최 여부 및 외부방문자 유입에 따른 상권 변화 (2022 Q1 -> 2024 Q2)")
    st.caption("2024년 축제기간 기준 · 점 크기 = 축제지 집중률")
    fig1 = px.scatter(df_analysis, x="공실률변화량", y="임대료변화량", size="점크기", color="상권 유형", text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, labels={"공실률변화량": "공실률 변화 (%p)", "임대료변화량": "임대료 변화 (천원/㎡)"}, template="plotly_white", height=600)
    fig1.add_vline(x=df_analysis["공실률변화량"].median(), line_dash="dash", line_color="gray")
    fig1.add_hline(y=df_analysis["임대료변화량"].median(), line_dash="dash", line_color="gray")
    fig1.update_traces(textposition='top center')
    st.plotly_chart(fig1, use_container_width=True)

    st.write("---")
    st.subheader("🪐 차트 2. 지자체 예산 통제 시 축제 개최 여부에 따른 상권 변화 검증")
    st.caption("점 색상 = 상권 유형 (주황: 축제 상권, 초록: 일반 상권)")
    fig2 = px.scatter_3d(df_analysis, x="예산규모_억원", y="공실률변화량", z="임대료변화량", size="점크기", color="상권 유형", text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, labels={"예산규모_억원": "예산 규모 (억원)", "공실률변화량": "공실률 변화 (%p)", "임대료변화량": "임대료 변화 (천원/㎡)"}, template="plotly_white", height=700)
    st.plotly_chart(fig2, use_container_width=True)

    # 차트 3: 시계열 추이 (기존 유지)
    st.write("---")
    st.subheader("📈 차트 3: 축제 유무에 따른 분기별 임대료 및 공실률 실시간 추이")
    m_vac_full, _ = melt_quarters(df_vac, "공실률")
    m_rent_full, _ = melt_quarters(df_rent, "임대료")
    m_vac_full["상권구분"] = m_vac_full[detect_region_col(m_vac_full)].apply(classify_district)
    m_rent_full["상권구분"] = m_rent_full[detect_region_col(m_rent_full)].apply(classify_district)
    m_vac_full = m_vac_full.dropna(subset=["상권구분"])
    m_rent_full = m_rent_full.dropna(subset=["상권구분"])
    
    t1, t2 = st.tabs(["💰 평균 임대료 흐름", "🏚️ 평균 공실률 흐름"])
    with t1:
        df_r_trend = m_rent_full.groupby(["상권구분", "분기"])["임대료"].mean().reset_index().sort_values("분기")
        st.plotly_chart(px.line(df_r_trend, x="분기", y="임대료", color="상권구분", markers=True, color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, template="plotly_white"), use_container_width=True)
    with t2:
        df_v_trend = m_vac_full.groupby(["상권구분", "분기"])["공실률"].mean().reset_index().sort_values("분기")
        st.plotly_chart(px.line(df_v_trend, x="분기", y="공실률", color="상권구분", markers=True, color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, template="plotly_white"), use_container_width=True)

    # 차트 4: 지방소멸 설문 (기존 유지)
    st.write("---")
    st.subheader("⚠️ 지방소멸 대응 준비 수준 및 지자체 인식 진단")
    df_ext, _ = load_table_safely("지방소멸설문", get_fallback_extinction)
    if not df_ext.empty:
        df_ext = df_ext.sort_values(by="평균", ascending=True)
        fig4 = px.bar(df_ext, y="구분", x="평균", error_x="표준편차", color="평균", color_continuous_scale="Tealgrn", orientation="h", template="plotly_white")
        st.plotly_chart(fig4, use_container_width=True)

# ==========================================
# 3. 페이지 3: 세금 효율성 분석
# ==========================================
def render_page3():
    st.title("💸 정부 예산 세금 ROI 가치 진단")
    df_cost, _ = load_table_safely("행사원가회계정보", get_fallback_cost)
    df_fest_raw, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_fest = pivot_festival_data(df_fest_raw)
    
    org_list = sorted(list(df_cost[df_cost.columns[0]].dropna().unique()))
    selected_org = st.selectbox("자치단체를 선택하세요", org_list)
    df_sub = df_cost[df_cost[df_cost.columns[0]] == selected_org].copy()
    
    st.subheader(f"📊 [{selected_org}] 예산 지출 분석")
    fig = px.bar(df_sub, x=df_sub.columns[1], y=df_sub.columns[4], template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 4. 메인 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    page = st.sidebar.selectbox("페이지 선택", ["1. 축제 현황 분석", "2. 젠트리피케이션 분석", "3. 세금 효율성 분석"])
    if page == "1. 축제 현황 분석": render_page1()
    elif page == "2. 젠트리피케이션 분석": render_page2()
    elif page == "3. 세금 효율성 분석": render_page3()

if __name__ == "__main__":
    main()
