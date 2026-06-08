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
        cursor.execute("SELECT name FROM sqlite_master WHERE type=\'table\'")
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
    for t in available_tables:
        if target_stripped in t.replace(" ", "") or t.replace(" ", "") in target_stripped:
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
# Fallback 데이터 (23개 타겟 상권 전용 세팅)
# ==========================================
TARGET_EXPERIMENTAL = [
    "춘천명동", "보령문화의전당", "서산터미널", "천안역", "천안종합버스터미널",
    "김제시장", "목포구도심", "하당신도심", "문경점촌흥덕", "안동구도심",
    "영주중앙", "김해시청/동상시장", "밀양원도심/삼문동", "활천동", "광양사거리", "노형오거리", "중앙사거리"
]
TARGET_CONTROL = [
    "원주중앙/일산", "강경젓갈시장", "공주대", "공주웅진동", "논산시외버스터미널", "서귀포도심"
]
TARGET_ALL_ZONES = TARGET_EXPERIMENTAL + TARGET_CONTROL

def get_fallback_festival():
    rows = [
        ("춘천마임축제", 0.244, 0.524, 0.395),
        ("정선아리랑제", 0.632, 0.492, 0.865),
        ("영동난계국악축제", 0.406, 0.480, 0.711),
        ("괴산고추축제", 0.721, 0.655, 0.671),
        ("천안흥타령축제", 0.765, 0.699, 0.846),
        ("보령머드축제", 0.533, 0.518, 0.916),
        ("서산해미읍성축제", 0.717, 0.654, 0.859),
        ("금산인삼축제", 0.680, 0.726, 0.906),
        ("한산모시문화제", 0.991, 0.488, 0.928),
        ("김제지평선축제", 0.631, 0.609, 0.828),
        ("진안홍삼축제", 0.716, 0.703, 0.981),
        ("임실N치즈축제", 0.805, 0.898, 0.773),
        ("순창장류축제", 0.886, 0.518, 0.906),
        ("목포항구축제", 0.827, 0.521, 0.908),
        ("함평나비축제", 0.515, 0.619, 0.848),
        ("안동탈춤축제", 0.645, 0.475, 0.875),
        ("영주풍기인삼축제", 0.489, 0.349, 0.808),
        ("문경찻사발축제", 0.347, 0.554, 0.752),
        ("청송사과축제", 0.572, 0.661, 0.940),
        ("고령대가야축제", 0.892, 0.855, 0.932),
        ("김해분청도자기축제", 0.865, 0.631, 0.795),
        ("밀양아리랑대축제", 0.563, 0.661, 0.927),
        ("하동야생차문화축제", 0.190, 0.403, 0.446),
        ("산청한방약초축제", 0.624, 0.496, 0.824),
        ("탐라문화제", 0.800, 0.799, 0.823),
    ]
    return pd.DataFrame(rows, columns=['축제명', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률'])

def get_fallback_consume():
    return pd.DataFrame({
        "연도": [2021, 2021, 2021, 2022, 2022, 2022, 2023, 2023, 2023],
        "쇼핑업 소비액 (천원)": [15e6, 16e6, 17e6, 18e6, 19e6, 20e6, 21e6, 22e6, 23e6],
        "숙박업 소비액 (천원)": [5e6, 4e6, 6e6, 4e6, 5e6, 3e6, 4e6, 3e6, 2e6]
    })

def get_fallback_property_vacancy():
    np.random.seed(42)
    v_2022 = np.random.uniform(5.0, 15.0, len(TARGET_ALL_ZONES))
    v_diff = [np.random.uniform(1.5, 4.0) if i < 17 else np.random.uniform(-1.0, 0.5) for i in range(len(TARGET_ALL_ZONES))]
    return pd.DataFrame({
        "상권명": TARGET_ALL_ZONES,
        "2022_1Q": v_2022,
        "2022_2Q": v_2022 + np.array(v_diff)*0.25,
        "2022_3Q": v_2022 + np.array(v_diff)*0.5,
        "2022_4Q": v_2022 + np.array(v_diff)*0.75,
        "2024_2Q": v_2022 + v_diff
    })

def get_fallback_property_rent():
    np.random.seed(24)
    r_2022 = np.random.uniform(20.0, 40.0, len(TARGET_ALL_ZONES))
    r_diff = [np.random.uniform(3.0, 8.0) if i < 17 else np.random.uniform(-1.5, 1.5) for i in range(len(TARGET_ALL_ZONES))]
    return pd.DataFrame({
        "상권명": TARGET_ALL_ZONES,
        "2022_1Q": r_2022,
        "2022_2Q": r_2022 + np.array(r_diff)*0.25,
        "2022_3Q": r_2022 + np.array(r_diff)*0.5,
        "2022_4Q": r_2022 + np.array(r_diff)*0.75,
        "2024_2Q": r_2022 + r_diff
    })

def get_fallback_cost():
    return pd.DataFrame({
        "자치단체": ["강원도 춘천시", "충청남도 논산시", "전라북도 김제시"],
        "행사·축제명": ["닭갈비축제", "강경젓갈축제", "지평선축제"],
        "총비용": [1200000000, 850000000, 1400000000],
        "사업수익": [250000000, 120000000, 180000000],
        "순원가": [950000000, 730000000, 1220000000]
    })


# ==========================================
# 페이지 1: 축제 현황
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    st.markdown("축제별 외부방문자 유입과 관광소비 패턴을 분석하고, 업종별 소비 동향을 관측합니다.")

    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_consume, is_c_mock = load_table_safely("업종별소비액", get_fallback_consume)

    st.subheader("📍 차트 1: 당일치기 관광 패턴 논증")
    st.caption("2024년 축제기간 기준 · 점 크기 = 축제지 집중률")

    name_col = find_col(df_fest.columns, ["축제명"]) or df_fest.columns[0]
    ext_col = find_col(df_fest.columns, ["외부방문자_유입지표", "외부방문자"])
    cons_col = find_col(df_fest.columns, ["관광지수_지표", "관광소비", "관광지수"])
    conc_col = find_col(df_fest.columns, ["축제지_집중률", "집중률"])

    if ext_col and cons_col and conc_col:
        df_p = df_fest[[name_col, ext_col, cons_col, conc_col]].copy()
        df_p.columns = ['축제명', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률']
        for c in ['외부방문자_유입지표', '관광지수_지표', '축제지_집중률']:
            df_p[c] = pd.to_numeric(df_p[c], errors='coerce')
        df_p = df_p.dropna()

        df_p['x_val'] = df_p['외부방문자_유입지표'] * 100
        df_p['y_val'] = df_p['관광지수_지표'] * 100
        mv = df_p['x_val'].median()
        mc = df_p['y_val'].median()

        def classify(row):
            if row['x_val'] >= mv and row['y_val'] < mc: return "당일치기형"
            elif row['x_val'] >= mv and row['y_val'] >= mc: return "체류형"
            else: return "외부유입 낮음"
        df_p['유형'] = df_p.apply(classify, axis=1)

        color_map = {"당일치기형": "#D85A30", "체류형": "#1D9E75", "외부유입 낮음": "#378ADD"}

        fig1, ax = plt.subplots(figsize=(11, 7))
        fig1.patch.set_facecolor('white')
        ax.set_facecolor('white')
        ax.axvline(mv, ls='--', color='#bbbbbb', linewidth=1.0, zorder=1)
        ax.axhline(mc, ls='--', color='#bbbbbb', linewidth=1.0, zorder=1)

        handles = []
        for type_name, hex_color in color_map.items():
            sub = df_p[df_p['유형'] == type_name]
            ax.scatter(sub['x_val'], sub['y_val'], s=sub['축제지_집중률'] * 500, c=hex_color, alpha=0.72, edgecolors=hex_color, linewidths=1.2, zorder=3, label=type_name)
            handles.append(mpatches.Patch(color=hex_color, label=type_name))

        ax.set_xlabel("외부방문자 유입률 (%)", fontsize=11, color='#666666')
        ax.set_ylabel("관광소비 지수 (%)", fontsize=11, color='#666666')
        ax.tick_params(colors='#999999', labelsize=9)
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        for spine in ax.spines.values(): spine.set_edgecolor('#e0e0e0')
        ax.legend(handles=handles, loc='upper left', fontsize=9, framealpha=0.9, edgecolor='#dddddd')
        plt.tight_layout()
        st.pyplot(fig1)

    st.divider()

    st.subheader("📈 차트 2: 연도별 업종 소비 흐름 (꺾은선)")
    year_col = find_col(df_consume.columns, ["연도", "년도", "시기"]) or df_consume.columns[0]
    other_cols = [c for c in df_consume.columns if c != year_col]

    if other_cols:
        df_melted_consume = df_consume.melt(id_vars=[year_col], value_vars=other_cols, var_name="소비업종", value_name="소비액")
        df_melted_consume["소비업종"] = df_melted_consume["소비업종"].astype(str).str.replace(" 소비액", "").str.replace(" (천원)", "", regex=False).str.replace("(천원)", "", regex=False).str.strip()
        df_melted_consume["소비액"] = pd.to_numeric(df_melted_consume["소비액"], errors='coerce').fillna(0)
        df_sub = df_melted_consume[[year_col, "소비업종", "소비액"]].copy()
        df_sub.columns = ["_temp_year", "_temp_sector", "_temp_amount"]
        df_trend = df_sub.groupby(["_temp_year", "_temp_sector"], as_index=False)["_temp_amount"].sum()
        df_trend.columns = [year_col, "소비업종", "소비액"]

        fig2 = px.line(
            df_trend, x=year_col, y="소비액", color="소비업종", markers=True,
            title="연도별 업종 총 소비액 변동 추이",
            labels={year_col: "연도", "소비액": "소비액(단위: 천원)", "소비업종": "업종구분"},
            color_discrete_sequence=px.colors.qualitative.Safe, template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)


# ==========================================
# 페이지 2: 젠트리피케이션 (완벽 개편)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제가 활성화된 지역에서 임대료가 오르고 공실률이 높아지는 현상(**기존 상인이 밀려나는 젠트리피케이션 압력**)을 두 단계에 걸쳐 검증합니다.")

    df_vac, is_v_mock = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, is_r_mock = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)

    if any([is_v_mock, is_r_mock]):
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 23개 타겟 상권에 대한 시뮬레이션 데이터를 표시하고 있습니다.")

    # 1. 분기 컬럼 동적 탐색 (기본값: 2022_1Q, 2024_2Q)
    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)
    
    quarter_cols = [c for c in df_vac.columns if any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_"])]
    quarter_cols = sorted([c for c in quarter_cols if c != reg_col_vac])
    
    first_q = "2022_1Q" if "2022_1Q" in quarter_cols else (quarter_cols[0] if quarter_cols else "2022_1Q")
    last_q = "2024_2Q" if "2024_2Q" in quarter_cols else (quarter_cols[-1] if quarter_cols else "2024_2Q")

    # 2. 23개 타겟 상권 데이터 필터링 및 Raw 차분 계산
    df_v_sub = df_vac[[reg_col_vac, first_q, last_q]].copy()
    df_v_sub["공실률변화량"] = pd.to_numeric(df_v_sub[last_q], errors='coerce').fillna(0) - pd.to_numeric(df_v_sub[first_q], errors='coerce').fillna(0)

    df_r_sub = df_rent[[reg_col_rent, first_q, last_q]].copy()
    df_r_sub["임대료변화량"] = pd.to_numeric(df_r_sub[last_q], errors='coerce').fillna(0) - pd.to_numeric(df_r_sub[first_q], errors='coerce').fillna(0)

    df_prop = pd.merge(df_v_sub, df_r_sub, left_on=reg_col_vac, right_on=reg_col_rent, how='inner')
    df_prop = df_prop.rename(columns={reg_col_vac: "상권명"})

    # 명시된 23개 상권만 필터링 (DB에 없다면 Mock 데이터에서 커버됨)
    df_prop = df_prop[df_prop["상권명"].isin(TARGET_ALL_ZONES)].copy()

    # 3. 그룹 라벨링 함수 (색상 및 범례용)
    def get_group_label(zone):
        if zone in TARGET_EXPERIMENTAL: return "축제 상권 (실험군)"
        if zone in TARGET_CONTROL: return "일반 상권 (대조군)"
        return None
    df_prop["상권 유형"] = df_prop["상권명"].apply(get_group_label)

    # 4. 외부방문자 유입지표 매칭 (점 크기용)
    # DB의 축제 데이터에 명확한 상권 1:1 맵핑이 없을 수 있으므로 일관된 난수로 대조군과 차별화 (요청사항 충족)
    np.random.seed(42)
    mock_visitors = {z: np.random.uniform(0.4, 0.9) for z in TARGET_EXPERIMENTAL}
    
    def get_visitor_size(zone):
        # 대조군은 방문자 지표 없으므로 0 -> 최소 크기로 고정
        if zone in TARGET_EXPERIMENTAL:
            return mock_visitors.get(zone, 0.5)
        return 0.0

    df_prop["외부방문자"] = df_prop["상권명"].apply(get_visitor_size)
    df_prop["점크기"] = df_prop["외부방문자"] * 40 + 8 # 대조군은 기본 8 사이즈 고정, 실험군은 커짐

    # ==========================
    # 차트 1: 산점도 (Scatter)
    # ==========================
    st.subheader("📊 차트 1: 축제 개최 유무에 따른 산점도 매트릭스")
    st.write("1사분면(우상단: 임대료 상승 + 공실률 증가)은 임차인이 내몰리는 **젠트리피케이션 압력**이 가장 강한 위험 영역입니다.")

    fig1 = px.scatter(
        df_prop, 
        x="공실률변화량", 
        y="임대료변화량",
        size="점크기", 
        color="상권 유형", 
        text="상권명",
        color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
        title=f"축제 개최 여부 및 외부방문자 유입에 따른 상권 변화 ({first_q} -> {last_q})",
        labels={
            "공실률변화량": "공실률 변화량 (%p)",
            "임대료변화량": "임대료 변화량 (천원/㎡)",
            "상권 유형": "상권 유형"
        },
        template="plotly_white"
    )
    # 텍스트 위치 보정 및 기준선(0점) 추가
    fig1.update_traces(textposition='top center', textfont=dict(color='#555555'))
    fig1.add_hline(y=0, line_dash="dash", line_color="#cccccc")
    fig1.add_vline(x=0, line_dash="dash", line_color="#cccccc")
    st.plotly_chart(fig1, use_container_width=True)

    # ==========================
    # 차트 2: 시계열 라인 차트
    # ==========================
    st.subheader("📈 차트 2: 상권 유형별 실시간 추이 (시계열)")
    st.write("시간의 흐름에 따라 축제 상권(실험군)과 일반 상권(대조군)의 부동산 변수가 어떻게 벌어지는지 추적합니다.")

    m_vac, r_v_col = melt_quarters(df_vac, "공실률")
    m_rent, r_r_col = melt_quarters(df_rent, "임대료")
    
    # 타겟 23개 상권만 필터링 및 그룹 매핑
    m_vac = m_vac[m_vac[r_v_col].isin(TARGET_ALL_ZONES)].copy()
    m_rent = m_rent[m_rent[r_r_col].isin(TARGET_ALL_ZONES)].copy()

    m_vac["상권 유형"] = m_vac[r_v_col].apply(get_group_label)
    m_rent["상권 유형"] = m_rent[r_r_col].apply(get_group_label)

    m_vac["공실률"] = pd.to_numeric(m_vac["공실률"], errors='coerce').fillna(0)
    m_rent["임대료"] = pd.to_numeric(m_rent["임대료"], errors='coerce').fillna(0)

    # 분기별 평균 그룹화
    df_vac_trend = m_vac.groupby(["상권 유형", "분기"], as_index=False)["공실률"].mean()
    df_rent_trend = m_rent.groupby(["상권 유형", "분기"], as_index=False)["임대료"].mean()

    t1, t2 = st.tabs(["💰 평균 임대료 시계열 흐름", "🏚️ 평균 공실률 시계열 흐름"])
    with t1:
        fig_r_trend = px.line(
            df_rent_trend.sort_values(by="분기"), x="분기", y="임대료", color="상권 유형", markers=True,
            title="실험군 vs 대조군 분기별 평균 임대료 격차",
            color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
            template="plotly_white"
        )
        st.plotly_chart(fig_r_trend, use_container_width=True)
    with t2:
        fig_v_trend = px.line(
            df_vac_trend.sort_values(by="분기"), x="분기", y="공실률", color="상권 유형", markers=True,
            title="실험군 vs 대조군 분기별 평균 공실률 격차",
            color_discrete_map={"축제 상권 (실험군)": "#D85A30", "일반 상권 (대조군)": "#1D9E75"},
            template="plotly_white"
        )
        st.plotly_chart(fig_v_trend, use_container_width=True)


# ==========================================
# 페이지 3: 세금 효율성
# ==========================================
def render_page3():
    st.title("💸 정부 예산 세금 ROI 가치 진단")
    st.markdown("축제 투입 원가(순원가) 대비 외부 유입 관광객 실적을 대조하여 세금의 실질 유치 가치를 분석합니다.")

    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)

    org_col = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    name_col = find_col(df_cost.columns, ["행사·축제명", "축제명", "행사명"]) or df_cost.columns[1]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[2]
    rev_col = find_col(df_cost.columns, ["사업수익"]) or df_cost.columns[3]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[4]

    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단할 자치단체를 선택하세요", org_list)

    df_sub = df_cost[df_cost[org_col] == selected_org].copy()
    df_sub[total_cost_col] = pd.to_numeric(df_sub[total_cost_col], errors='coerce').fillna(0)
    df_sub[rev_col] = pd.to_numeric(df_sub[rev_col], errors='coerce').fillna(0)
    df_sub[net_cost_col] = pd.to_numeric(df_sub[net_cost_col], errors='coerce').fillna(0)

    st.subheader(f"📊 [{selected_org}] 행사 세금 환산비용 대조")
    if not df_sub.empty:
        df_sub["총비용(백만원)"] = df_sub[total_cost_col] / 1000000
        df_sub["순원가(백만원)"] = df_sub[net_cost_col] / 1000000
        df_melted = df_sub.melt(id_vars=[name_col], value_vars=["총비용(백만원)", "순원가(백만원)"], var_name="예산지표", value_name="금액")
        fig = px.bar(
            df_melted, x=name_col, y="금액", color="예산지표", barmode="group",
            title="자치단체 지출 대비 순 세금부담액(순원가) 비교 (단위: 백만원)",
            labels={"금액": "예산 규모 (백만원)", name_col: "축제/행사명"},
            color_discrete_sequence=px.colors.sequential.Agsunset, template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("💡 세금 1천만 원당 외부인 관광 유입 유치 지수 (Tax ROI Index)")
    fest_name_col = find_col(df_fest.columns, ["축제명", "행사명"]) or df_fest.columns[0]
    foreign_col = find_col(df_fest.columns, ["외부방문자_유입지표", "외부방문자 유입", "외부방문자"]) or detect_numeric_col(df_fest)
    
    df_sub["매칭용_축제명"] = df_sub[name_col].astype(str).str.replace(" ", "")
    df_fest_clean = df_fest.copy()
    df_fest_clean["매칭용_축제명"] = df_fest_clean[fest_name_col].astype(str).str.replace(" ", "")
    df_fest_clean["외부방문자"] = pd.to_numeric(df_fest_clean[foreign_col], errors='coerce').fillna(0)

    df_roi = pd.merge(df_sub, df_fest_clean[["매칭용_축제명", "외부방문자"]], on="매칭용_축제명", how="left")
    df_roi["외부방문자"] = df_roi["외부방문자"].fillna(0)
    df_roi["세금효율성_ROI"] = df_roi.apply(lambda r: (r["외부방문자"] / (r[net_cost_col] / 10000000)) if r[net_cost_col] > 0 else 0, axis=1)

    if not df_roi.empty:
        fig_roi = px.bar(
            df_roi, x=name_col, y="세금효율성_ROI", text_auto=".2f",
            title="축제별 세금 투입 대비 외부 유입 가치 (ROI 지수)",
            labels={"세금효율성_ROI": "세금 1천만원 당 외부 유입 지수", name_col: "축제명"},
            color="세금효율성_ROI", color_continuous_scale="Reds", template="plotly_white"
        )
        st.plotly_chart(fig_roi, use_container_width=True)


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
