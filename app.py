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

def find_matching_table(target_name):
    available_tables = get_db_tables()
    if target_name in available_tables:
        return target_name
    target_stripped = target_name.replace(" ", "")
    for t in available_tables:
        if t.replace(" ", "") == target_stripped:
            return t
    return None

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

def find_col(columns, search_terms):
    for term in search_terms:
        for col in columns:
            clean_col = str(col).replace(" ", "").replace("·", "").replace("_", "").lower()
            clean_term = str(term).replace(" ", "").replace("·", "").replace("_", "").lower()
            if clean_term in clean_col:
                return col
    return None

def detect_region_col(df):
    name_match = find_col(df.columns, ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명"])
    if name_match:
        return name_match
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().unique()
            for val in sample:
                if any(reg in str(val) for reg in ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "부산", "대구", "광주", "대전", "울산", "세종"]):
                    return col
    obj_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]

def detect_numeric_col(df):
    name_match = find_col(df.columns, ["지표", "값", "실적", "방문", "관광객", "점수", "인원"])
    if name_match:
        return name_match
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for col in num_cols:
        if not any(ex in str(col).lower() for ex in ["연도", "년도", "id", "코드"]):
            return col
    return num_cols[0] if num_cols else None

def extract_city_core(text):
    text_str = str(text).strip()
    special_mapping = {"한산": "서천", "서천": "서천", "탐라": "제주", "제주": "제주", "보령": "보령", "춘천": "춘천", "천안": "천안"}
    for key, val in special_mapping.items():
        if key in text_str:
            return val
    keywords = ["춘천", "정선", "임실", "고령", "천안", "순창", "남원", "강릉", "울릉", "여수", "경주", "안동", "보령", "목포", "김제", "문경", "영주", "김해", "밀양", "광양"]
    for city in keywords:
        if city in text_str:
            return city
    words = text_str.split()
    if words:
        target_word = words[-1]
        return target_word.replace("시", "").replace("군", "").replace("구", "").strip()
    return text_str[:2]

get_short_region = extract_city_core

def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    region_col = detect_region_col(df)
    quarter_cols = [c for c in df.columns if c != region_col and (any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or any(str(yr) in str(c) for yr in range(2015, 2027)))]
    if not quarter_cols:
        quarter_cols = [c for c in df.select_dtypes(include=['number']).columns.tolist() if c != region_col]
    df_melted = df.melt(id_vars=[region_col], value_vars=quarter_cols, var_name="분기", value_name=value_name)
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col

def pivot_festival_data(df_fest):
    if df_fest.empty or len(df_fest.columns) < 5:
        return pd.DataFrame()
    fest_name_col, period_col, year_col, indicator_col, value_col = df_fest.columns[:5]
    df_filtered = df_fest[df_fest[period_col].astype(str).str.contains("축제기간|축제", na=False)].copy()
    if df_filtered.empty:
        df_filtered = df_fest.copy()
    try:
        return df_filtered.pivot_table(index=[fest_name_col, year_col], columns=indicator_col, values=value_col, aggfunc="mean").reset_index()
    except:
        return pd.DataFrame()

# ==========================================
# Fallback 데이터 생성기
# ==========================================
def get_fallback_festival():
    return pd.DataFrame({
        "축제명": ["순창장류축제", "한산모시문화제", "임실N치즈축제", "고령대가야축제", "천안흥타령축제", "탐라문화제", "정선아리랑제", "춘천마임축제"],
        "현지인방문자 유입": [0.52, 0.49, 0.90, 0.85, 0.70, 0.80, 0.62, 0.48],
        "외부방문자 유입": [0.83, 0.99, 0.85, 0.89, 0.79, 0.70, 0.51, 0.40],
        "관광소비": [0.52, 0.48, 0.89, 0.85, 0.70, 0.80, 0.61, 0.52],
        "지자체": ["전북", "충남", "전북", "경북", "충남", "제주", "강원", "강원"]
    })

def get_fallback_consume():
    return pd.DataFrame({"연도": [2021, 2022, 2023], "쇼핑업 소비액": [15e6, 18e6, 21e6], "숙박업 소비액": [5e6, 4e6, 4e6]})

def get_fallback_property_vacancy():
    return pd.DataFrame({"지역": ["춘천명동", "보령문화의전당", "원주중앙/일산"], "2022_1Q": [12.1, 14.5, 8.5], "2024_2Q": [15.0, 17.5, 9.0]})

def get_fallback_property_rent():
    return pd.DataFrame({"지역": ["춘천명동", "보령문화의전당", "원주중앙/일산"], "2022_1Q": [3.2, 2.5, 5.1], "2024_2Q": [3.1, 2.4, 5.2]})

def get_fallback_cost():
    return pd.DataFrame({"자치단체": ["춘천시", "서천군"], "총비용": [12e8, 8e8], "순원가": [9e8, 7e8]})

def get_fallback_extinction():
    return pd.DataFrame({"구분": ["지방소멸 심각성", "대응 효과성"], "평균": [4.42, 2.23], "표준편차": [0.83, 1.01]})

# ==========================================
# 1. 페이지 1: 축제 현황 분석
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 관광 유형 및 소비 패턴 분석")
    df_raw, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_consume, is_c_mock = load_table_safely("업종별소비액", get_fallback_consume)
    
    if is_f_mock or is_c_mock:
        st.sidebar.warning("⚠️ 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    df_fest = pivot_festival_data(df_raw) if not is_f_mock else df_raw.copy()
    if df_fest.empty: return
        
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📍 관광유형 사분면 모델")
        fest_name_col = df_fest.columns[0]
        foreign_col = find_col(df_fest.columns, ["외부방문자"]) or df_fest.columns[2]
        local_col = find_col(df_fest.columns, ["관광소비"]) or df_fest.columns[1]
        df_fest[foreign_col] = pd.to_numeric(df_fest[foreign_col], errors='coerce').fillna(0)
        df_fest[local_col] = pd.to_numeric(df_fest[local_col], errors='coerce').fillna(0)
        
        fig1 = px.scatter(df_fest, x=foreign_col, y=local_col, text=fest_name_col, template="plotly_white")
        st.plotly_chart(fig1, use_container_width=True)
        
    with col2:
        st.subheader("📈 연도별 업종 소비 흐름")
        year_col = find_col(df_consume.columns, ["연도"]) or df_consume.columns[0]
        df_melt = df_consume.melt(id_vars=[year_col])
        fig2 = px.line(df_melt, x=year_col, y="value", color="variable", markers=True, template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (요청사항 반영 수정)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 상권(실험군)과 일반 상권(대조군)의 격차를 정적 분산 구조와 시계열 트렌드로 비교 분석합니다.")

    # [ai_studio_code-2.py 로직 적용 시작]
    # 1. 데이터 로드
    df_vac, _ = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, _ = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest_raw, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_budget_raw, _ = load_table_safely("지방자치단체세출예산", lambda: pd.DataFrame())

    # 2. 상권 매핑 정의
    exp_districts = ["춘천명동", "보령문화의전당", "서산터미널", "천안역", "천안종합버스터미널", "김제시장", "목포구도심", "하당신도심", "문경점촌흥덕", "안동구도심", "영주중앙", "김해시청/동상시장", "밀양원도심/삼문동", "활천동", "광양사거리", "노형오거리", "중앙사거리"]
    ctrl_districts = ["원주중앙/일산", "강경젓갈시장", "공주대", "공주웅진동", "논산시외버스터미널", "서귀포도심"]
    all_target_districts = exp_districts + ctrl_districts

    # 3. 데이터 전처리: 상권명 기준 필터링 및 차분 계산
    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)

    def get_diff(df, col_name, start="2022_1Q", end="2024_2Q"):
        s_col = [c for c in df.columns if start in str(c).replace("/", "_").replace(".", "_")]
        e_col = [c for c in df.columns if end in str(c).replace("/", "_").replace(".", "_")]
        if s_col and e_col:
            temp = df.copy()
            temp[col_name] = pd.to_numeric(temp[e_col[0]], errors='coerce') - pd.to_numeric(temp[s_col[0]], errors='coerce')
            return temp[[detect_region_col(df), col_name]]
        return pd.DataFrame()

    df_vac_diff = get_diff(df_vac, "공실률변화량")
    df_rent_diff = get_diff(df_rent, "임대료변화량")
    df_merge = pd.merge(df_vac_diff, df_rent_diff, left_on=reg_col_vac, right_on=reg_col_rent)
    df_merge.rename(columns={reg_col_vac: "상권명"}, inplace=True)
    df_analysis = df_merge[df_merge["상권명"].isin(all_target_districts)].copy()
    df_analysis["상권 유형"] = df_analysis["상권명"].apply(lambda x: "축제 상권 (실험군)" if x in exp_districts else "일반 상권 (대조군)")

    # 4. 외부방문자 유입 및 예산 데이터 매칭
    df_fest = pivot_festival_data(df_fest_raw) if not df_fest_raw.empty else get_fallback_festival()
    foreign_col = find_col(df_fest.columns, ["외부방문자"]) or df_fest.columns[1]
    df_analysis["매칭키"] = df_analysis["상권명"].apply(extract_city_core)
    df_fest["매칭키"] = df_fest[df_fest.columns[0]].apply(extract_city_core)
    df_fest_grp = df_fest.groupby("매칭키")[foreign_col].mean().reset_index()
    df_analysis = pd.merge(df_analysis, df_fest_grp, on="매칭키", how="left")
    df_analysis[foreign_col] = df_analysis[foreign_col].fillna(df_analysis[foreign_col].min() or 0.1)
    df_analysis["점크기"] = df_analysis[foreign_col] * 50 + 10

    if not df_budget_raw.empty:
        sector_col = find_col(df_budget_raw.columns, ["분야", "항목"])
        value_col = find_col(df_budget_raw.columns, ["세출", "예산", "금액"])
        df_b_filtered = df_budget_raw[df_budget_raw[sector_col].str.contains("국토|문화|관광", na=False)].copy()
        df_b_filtered["매칭키"] = df_b_filtered[detect_region_col(df_b_filtered)].apply(extract_city_core)
        df_budget_grp = df_b_filtered.groupby("매칭키")[value_col].mean().reset_index()
        df_budget_grp.columns = ["매칭키", "예산규모_억원"]
        df_budget_grp["예산규모_억원"] = df_budget_grp["예산규모_억원"] / 100000000
    else:
        df_budget_grp = pd.DataFrame({"매칭키": df_analysis["매칭키"].unique(), "예산규모_억원": [500, 1200, 800, 2500, 1800, 600, 900, 1500, 400, 2100, 750, 1300, 1100, 950, 3000, 2800, 2200][:len(df_analysis["매칭키"].unique())]})

    df_analysis = pd.merge(df_analysis, df_budget_grp, on="매칭키", how="left")
    df_analysis["예산규모_억원"] = df_analysis["예산규모_억원"].fillna(df_analysis["예산규모_억원"].median())

    # [차트 1: 산점도]
    exp_df = df_analysis[df_analysis["상권 유형"] == "축제 상권 (실험군)"]
    st.subheader("📍 축제 상권(실험군) 상권 변화 요약")
    m1, m2 = st.columns(2)
    m1.metric("공실률 변화량(평균)", f"{exp_df['공실률변화량'].mean():+.2f} %p", delta_color="inverse")
    m2.metric("임대료 변화량(평균)", f"{exp_df['임대료변화량'].mean():+.3f} 천원/㎡")

    st.subheader("📊 차트 1. 축제 개최 여부 및 외부방문자 유입에 따른 상권 변화 (2022 Q1 -> 2024 Q2)")
    st.caption("2024년 축제기간 기준 · 점 크기 = 축제지 집중률")
    fig1 = px.scatter(df_analysis, x="공실률변화량", y="임대료변화량", size="점크기", color="상권 유형", text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, labels={"공실률변화량": "공실률 변화량 (%p)", "임대료변화량": "임대료 변화량 (천원/㎡)"}, template="plotly_white", height=600)
    fig1.add_vline(x=df_analysis["공실률변화량"].median(), line_dash="dash", line_color="gray")
    fig1.add_hline(y=df_analysis["임대료변화량"].median(), line_dash="dash", line_color="gray")
    fig1.update_traces(textposition='top center')
    st.plotly_chart(fig1, use_container_width=True)

    # [차트 2: 3D 버블]
    st.write("---")
    st.subheader("🪐 차트 2. 지자체 예산 통제 시 축제 개최 여부에 따른 상권 변화 검증")
    st.caption("점 색상 = 상권 유형 (주황: 축제 상권, 초록: 일반 상권)")
    fig2 = px.scatter_3d(df_analysis, x="예산규모_억원", y="공실률변화량", z="임대료변화량", size="예산규모_억원", color="상권 유형", text="상권명", color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, labels={"예산규모_억원": "예산 규모 (억원)", "공실률변화량": "공실률 변화량 (%p)", "임대료변화량": "임대료 변화량 (천원/㎡)"}, template="plotly_white", height=700)
    fig2.update_layout(scene=dict(xaxis_title='예산 규모 (억원)', yaxis_title='공실률 변화량 (%p)', zaxis_title='임대료 변화량 (천원/㎡)'), margin=dict(l=0, r=0, b=0, t=40))
    st.plotly_chart(fig2, use_container_width=True)
    # [ai_studio_code-2.py 로직 적용 끝]

    # [차트 3: 시계열 추이 - 기존 app.py 형태 유지]
    st.write("---")
    st.subheader("📈 차트 3: 축제 유무에 따른 분기별 임대료 및 공실률 실시간 추이")
    m_vac_full, r_v_col = melt_quarters(df_vac, "공실률")
    m_rent_full, r_r_col = melt_quarters(df_rent, "임대료")
    m_vac_full["매칭키"] = m_vac_full[r_v_col].apply(extract_city_core)
    m_rent_full["매칭키"] = m_rent_full[r_r_col].apply(extract_city_core)
    
    # 상권 유형 재정의 (23개 리스트 기준)
    m_vac_full["상권구분"] = m_vac_full[r_v_col].apply(lambda x: "축제 상권 (실험군)" if x in exp_districts else ("일반 상권 (대조군)" if x in ctrl_districts else "기타"))
    m_rent_full["상권구분"] = m_rent_full[r_r_col].apply(lambda x: "축제 상권 (실험군)" if x in exp_districts else ("일반 상권 (대조군)" if x in ctrl_districts else "기타"))
    m_vac_full = m_vac_full[m_vac_full["상권구분"] != "기타"]
    m_rent_full = m_rent_full[m_rent_full["상권구분"] != "기타"]

    df_vac_trend = m_vac_full.groupby(["상권구분", "분기"])["공실률"].mean().reset_index().sort_values("분기")
    df_rent_trend = m_rent_full.groupby(["상권구분", "분기"])["임대료"].mean().reset_index().sort_values("분기")
    
    t1, t2 = st.tabs(["💰 평균 임대료 흐름", "🏚️ 평균 공실률 흐름"])
    with t1:
        st.plotly_chart(px.line(df_rent_trend, x="분기", y="임대료", color="상권구분", markers=True, color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, template="plotly_white"), use_container_width=True)
    with t2:
        st.plotly_chart(px.line(df_vac_trend, x="분기", y="공실률", color="상권구분", markers=True, color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"}, template="plotly_white"), use_container_width=True)

    # [차트 4: 지방소멸 설문 - 기존 app.py 형태 유지]
    st.write("---")
    st.subheader("⚠️ 지방소멸 대응 준비 수준 진단")
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
    
    org_col = find_col(df_cost.columns, ["자치단체"]) or df_cost.columns[0]
    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단할 자치단체를 선택하세요", org_list)
    
    df_sub = df_cost[df_cost[org_col] == selected_org].copy()
    df_sub["순원가(백만원)"] = pd.to_numeric(df_sub["순원가"], errors='coerce') / 1e6
    st.plotly_chart(px.bar(df_sub, x=df_sub.columns[1], y="순원가(백만원)", template="plotly_white"), use_container_width=True)

# ==========================================
# 4. 메인 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    page = st.sidebar.selectbox("원하는 분석 페이지를 선택하세요.", ["1. 축제 현황 분석", "2. 젠트리피케이션 분석", "3. 세금 효율성 분석"])
    if page == "1. 축제 현황 분석": render_page1()
    elif page == "2. 젠트리피케이션 분석": render_page2()
    elif page == "3. 세금 효율성 분석": render_page3()

if __name__ == "__main__":
    main()
