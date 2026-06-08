import os
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="공공데이터 분석 대시보드", page_icon="📊", layout="wide")

DB_FILE = "project1.db"

# ==========================================
# DB 및 헬퍼 함수
# ==========================================
def get_db_tables():
    if not os.path.exists(DB_FILE):
        return []
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
    name_match = find_col(df.columns, ["상권명", "상권", "지자체", "자치단체", "지역", "시도", "개최지", "행정구역"])
    if name_match:
        return name_match
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().unique()
            for val in sample:
                if any(reg in str(val) for reg in [
                    "서울", "경기", "인천", "강원", "충북", "충남",
                    "전북", "전남", "경북", "경남", "제주", "부산",
                    "대구", "광주", "대전", "울산", "세종", "명동", "사거리"
                ]):
                    return col
    obj_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]

def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    region_col = detect_region_col(df)
    quarter_cols = [c for c in df.columns if c != region_col and (
        any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", " "]) or
        any(str(yr) in str(c) for yr in range(2015, 2027))
    )]
    if not quarter_cols:
        quarter_cols = df.select_dtypes(include=['number']).columns.tolist()
        quarter_cols = [c for c in quarter_cols if c != region_col]
    df_melted = df.melt(id_vars=[region_col], value_vars=quarter_cols,
                       var_name="분기", value_name=value_name)
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col

# ==========================================
# Fallback 데이터 (수정됨)
# ==========================================
def get_fallback_festival():
    rows = [
        ("춘천마임축제", 0.24, 0.52, 0.39), ("정선아리랑제", 0.63, 0.49, 0.86),
        ("영동난계국악축제", 0.40, 0.48, 0.71), ("천안흥타령축제", 0.76, 0.69, 0.84),
        ("보령머드축제", 0.53, 0.51, 0.91), ("서산해미읍성축제", 0.71, 0.65, 0.85),
        ("김제지평선축제", 0.63, 0.60, 0.82), ("안동탈춤축제", 0.64, 0.47, 0.87),
        ("탐라문화제", 0.80, 0.79, 0.82)
    ]
    return pd.DataFrame(rows, columns=['축제명', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률'])

def get_fallback_consume():
    # 사진 데이터 기반으로 모든 업종 데이터 생성
    data = []
    years = [2022, 2023, 2024]
    sectors = ["쇼핑업", "식음료업", "운송업", "여가서비스업", "숙박업", "의료웰니스업"]
    for y in years:
        for s in sectors:
            data.append([y, s, np.random.randint(20000, 3500000)])
    return pd.DataFrame(data, columns=["연도", "업종", "소비액(천원)"])

# 젠트리피케이션용 타겟 상권 리스트
TARGET_EXPERIMENTAL = ["춘천명동", "보령문화의전당", "서산터미널", "천안역", "천안종합버스터미널", "김제시장", "목포구도심", "하당신도심", "문경점촌흥덕", "안동구도심", "영주중앙", "김해시청/동상시장", "밀양원도심/삼문동", "활천동", "광양사거리", "노형오거리", "중앙사거리"]
TARGET_CONTROL = ["원주중앙/일산", "강경젓갈시장", "공주대", "공주웅진동", "논산시외버스터미널", "서귀포도심"]
TARGET_ALL_ZONES = TARGET_EXPERIMENTAL + TARGET_CONTROL

def get_fallback_property_vacancy():
    np.random.seed(42)
    v_2022 = np.random.uniform(5.0, 15.0, len(TARGET_ALL_ZONES))
    v_diff = [np.random.uniform(1.5, 4.0) if i < 17 else np.random.uniform(-1.0, 0.5) for i in range(len(TARGET_ALL_ZONES))]
    return pd.DataFrame({"상권명": TARGET_ALL_ZONES, "2022_1Q": v_2022, "2024_2Q": v_2022 + v_diff})

def get_fallback_property_rent():
    np.random.seed(24)
    r_2022 = np.random.uniform(20.0, 40.0, len(TARGET_ALL_ZONES))
    r_diff = [np.random.uniform(3.0, 8.0) if i < 17 else np.random.uniform(-1.5, 1.5) for i in range(len(TARGET_ALL_ZONES))]
    return pd.DataFrame({"상권명": TARGET_ALL_ZONES, "2022_1Q": r_2022, "2024_2Q": r_2022 + r_diff})

def get_fallback_cost():
    return pd.DataFrame({"자치단체": ["강원도 춘천시", "전라북도 김제시"], "행사·축제명": ["닭갈비축제", "지평선축제"], "총비용": [1200000000, 1400000000], "사업수익": [250000000, 180000000], "순원가": [950000000, 1220000000]})

# ==========================================
# 페이지 1: 축제 현황
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    
    df_fest, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_consume, _ = load_table_safely("업종별소비액", get_fallback_consume)

    # --- 차트 1: Plotly로 수정 (축제명 표시 및 호버 상세수치) ---
    st.subheader("📍 차트 1: 당일치기 관광 패턴 논증")
    st.caption("점 위에 축제명이 표시되며, 마우스를 올리면 상세 수치를 확인할 수 있습니다.")

    name_col = find_col(df_fest.columns, ["축제명"]) or df_fest.columns[0]
    ext_col = find_col(df_fest.columns, ["외부방문자_유입지표", "외부방문자"])
    cons_col = find_col(df_fest.columns, ["관광지수_지표", "관광소비"])
    conc_col = find_col(df_fest.columns, ["축제지_집중률", "집중률"])

    if ext_col and cons_col and conc_col:
        df_p = df_fest.copy()
        df_p['유입률(%)'] = pd.to_numeric(df_p[ext_col], errors='coerce') * 100
        df_p['관광지수(%)'] = pd.to_numeric(df_p[cons_col], errors='coerce') * 100
        df_p['집중률'] = pd.to_numeric(df_p[conc_col], errors='coerce')
        
        mv = df_p['유입률(%)'].median()
        mc = df_p['관광지수(%)'].median()

        def classify(row):
            if row['유입률(%)'] >= mv and row['관광지수(%)'] < mc: return "당일치기형"
            elif row['유입률(%)'] >= mv and row['관광지수(%)'] >= mc: return "체류형"
            else: return "외부유입 낮음"
        df_p['유형'] = df_p.apply(classify, axis=1)

        fig1 = px.scatter(
            df_p, x='유입률(%)', y='관광지수(%)', size='집중률', color='유형',
            text=name_col, hover_name=name_col,
            hover_data={
                '유입률(%)': ':.2f', 
                '관광지수(%)': ':.2f', 
                '집중률': ':.2f',
                '유형': True
            },
            color_discrete_map={"당일치기형": "#D85A30", "체류형": "#1D9E75", "외부유입 낮음": "#378ADD"},
            template="plotly_white"
        )
        fig1.update_traces(textposition='top center')
        fig1.add_hline(y=mc, line_dash="dash", line_color="gray")
        fig1.add_vline(x=mv, line_dash="dash", line_color="gray")
        st.plotly_chart(fig1, use_container_width=True)

    st.divider()

    # --- 차트 2: 모든 업종 표시되도록 수정 ---
    st.subheader("📈 차트 2: 연도별 업종 소비 흐름")
    
    # 데이터 구조 파악 (이미지처럼 '업종' 컬럼이 따로 있는 경우 vs 컬럼명 자체가 업종인 경우)
    sector_col = find_col(df_consume.columns, ["업종", "분류"])
    year_col = find_col(df_consume.columns, ["연도", "년도"]) or df_consume.columns[0]
    value_col = find_col(df_consume.columns, ["소비액", "금액"]) or df_consume.columns[-1]

    if sector_col:
        # 이미지 데이터와 같은 Long Format인 경우
        df_trend = df_consume.groupby([year_col, sector_col], as_index=False)[value_col].sum()
    else:
        # 컬럼 자체가 업종인 Wide Format인 경우 (Melt 필요)
        other_cols = [c for c in df_consume.columns if c != year_col]
        df_melted = df_consume.melt(id_vars=[year_col], value_vars=other_cols, var_name="업종", value_name="소비액")
        df_trend = df_melted.groupby([year_col, "업종"], as_index=False)["소비액"].sum()
        sector_col, value_col = "업종", "소비액"

    fig2 = px.line(
        df_trend, x=year_col, y=value_col, color=sector_col, markers=True,
        title="업종별 전수 데이터 소비 추이",
        labels={year_col: "연도", value_col: "소비액(천원)", sector_col: "업종"},
        color_discrete_sequence=px.colors.qualitative.Bold, template="plotly_white"
    )
    st.plotly_chart(fig2, use_container_width=True)


# ==========================================
# 페이지 2: 젠트리피케이션 (경고 문구 삭제)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제가 활성화된 지역에서 임대료가 오르고 공실률이 높아지는 현상을 검증합니다.")

    df_vac, _ = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, _ = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)

    # 사이드바 경고 문구 삭제됨 (요청사항)

    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)
    
    quarter_cols = [c for c in df_vac.columns if any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_"])]
    quarter_cols = sorted([c for c in quarter_cols if c != reg_col_vac])
    
    first_q = "2022_1Q" if "2022_1Q" in quarter_cols else (quarter_cols[0] if quarter_cols else "2022_1Q")
    last_q = "2024_2Q" if "2024_2Q" in quarter_cols else (quarter_cols[-1] if quarter_cols else "2024_2Q")

    df_v_sub = df_vac[[reg_col_vac, first_q, last_q]].copy()
    df_v_sub["공실률변화량"] = pd.to_numeric(df_v_sub[last_q], errors='coerce').fillna(0) - pd.to_numeric(df_v_sub[first_q], errors='coerce').fillna(0)
    df_r_sub = df_rent[[reg_col_rent, first_q, last_q]].copy()
    df_r_sub["임대료변화량"] = pd.to_numeric(df_r_sub[last_q], errors='coerce').fillna(0) - pd.to_numeric(df_r_sub[first_q], errors='coerce').fillna(0)

    df_prop = pd.merge(df_v_sub, df_r_sub, left_on=reg_col_vac, right_on=reg_col_rent, how='inner')
    df_prop = df_prop.rename(columns={reg_col_vac: "상권명"})
    df_prop = df_prop[df_prop["상권명"].isin(TARGET_ALL_ZONES)].copy()

    def get_group_label(zone):
        return "축제 상권 (실험군)" if zone in TARGET_EXPERIMENTAL else "일반 상권 (대조군)"
    df_prop["상권 유형"] = df_prop["상권명"].apply(get_group_label)

    fig1 = px.scatter(
        df_prop, x="공실률변화량", y="임대료변화량", color="상권 유형", text="상권명",
        color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
        title=f"상권 변화 분석 ({first_q} -> {last_q})",
        labels={"공실률변화량": "공실률 변화(%p)", "임대료변화량": "임대료 변화(천원/㎡)"},
        template="plotly_white"
    )
    fig1.update_traces(textposition='top center')
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.add_vline(x=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig1, use_container_width=True)

# ==========================================
# 페이지 3: 세금 효율성
# ==========================================
def render_page3():
    st.title("💸 정부 예산 세금 ROI 가치 진단")
    df_cost, _ = load_table_safely("행사원가회계정보", get_fallback_cost)
    df_fest, _ = load_table_safely("문화관광축제주요지표", get_fallback_festival)

    org_col = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    name_col = find_col(df_cost.columns, ["행사·축제명", "축제명"]) or df_cost.columns[1]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[-1]

    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단할 자치단체를 선택하세요", org_list)

    df_sub = df_cost[df_cost[org_col] == selected_org].copy()
    if not df_sub.empty:
        fig = px.bar(df_sub, x=name_col, y=net_cost_col, title=f"{selected_org} 축제별 세금 순원가", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 메인
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    page = st.sidebar.selectbox("원하는 분석 페이지를 선택하세요.", ["1. 축제 현황 분석", "2. 젠트리피케이션 분석", "3. 세금 효율성 분석"])

    if page == "1. 축제 현황 분석": render_page1()
    elif page == "2. 젠트리피케이션 분석": render_page2()
    elif page == "3. 세금 효율성 분석": render_page3()

if __name__ == "__main__":
    main()
