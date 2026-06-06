import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# --- 1. 기본 설정 및 한글 폰트 ---
st.set_page_config(page_title="지역 축제 및 상권 분석 대시보드", layout="wide")

# 한글 깨짐 방지 (Windows: Malgun Gothic, Mac: AppleGothic)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# --- 2. 데이터베이스 연결 함수 ---
def run_query(q):
    with sqlite3.connect('project.db') as conn:
        return pd.read_sql_query(q, conn)

# --- 3. 사이드바 네비게이션 ---
st.sidebar.title("🔍 분석 메뉴")
page = st.sidebar.radio("페이지 선택", ["축제 현황", "젠트리피케이션 문제", "세금 효율성 분석"])

# ==========================================
# 페이지 1: 축제 현황
# ==========================================
if page == "축제 현황":
    st.title("🎡 문화관광축제 및 관광 패턴 분석")

    # [차트 1 데이터] 
    # 지표값이 세로로 쌓여있는 '문화관광축제주요지표' 테이블을 가로로 펼침(Pivot)
    query1 = """
    SELECT 개최년도, 축제명,
           MAX(CASE WHEN 구분명 = '외부방문자 유입률' THEN 지표값 END) as inflow_rate,
           MAX(CASE WHEN 구분명 = '관광소비 지수' THEN 지표값 END) as consumption_idx,
           MAX(CASE WHEN 구분명 = '축제지 집중률' THEN 지표값 END) as concentration
    FROM 문화관광축제주요지표
    WHERE 개최년도 BETWEEN 2022 AND 2024
    GROUP BY 개최년도, 축제명
    """
    df_fest = run_query(query1)
    df_2024 = df_fest[df_fest['개최년도'] == 2024].dropna()

    # 사분면 분류 로직
    mx, my = df_2024['inflow_rate'].median(), df_2024['consumption_idx'].median()
    
    def classify(row):
        if row['inflow_rate'] >= mx and row['consumption_idx'] < my: return '당일치기형'
        if row['inflow_rate'] >= mx and row['consumption_idx'] >= my: return '체류형'
        return '외부유입 낮음'
    
    df_2024['type'] = df_2024.apply(classify, axis=1)

    # 시각화 1: 산점도 + 요약 카드 통합
    fig1 = plt.figure(figsize=(12, 10))
    gs = fig1.add_gridspec(2, 1, height_ratios=[1, 4], hspace=0.3)
    
    # 상단 요약 카드 (3개년 당일치기형 개수)
    ax_card = fig1.add_subplot(gs[0])
    ax_card.axis('off')
    for i, year in enumerate([2022, 2023, 2024]):
        # 연도별 중앙값은 2024년 기준으로 통일하거나 연도별로 계산 가능 (여기선 2024 기준)
        count = len(df_fest[(df_fest['개최년도'] == year) & (df_fest['inflow_rate'] >= mx) & (df_fest['consumption_idx'] < my)])
        rect_color = '#f5f5f5'
        edge_color = '#D85A30' if year == 2024 else '#cccccc'
        rect = plt.Rectangle((i*0.33, 0.2), 0.3, 0.6, facecolor=rect_color, edgecolor=edge_color, lw=2 if year == 2024 else 1)
        ax_card.add_patch(rect)
        ax_card.text(i*0.33 + 0.15, 0.6, f"{year}년 당일치기형", ha='center', fontsize=12, color='gray')
        ax_card.text(i*0.33 + 0.15, 0.35, f"{count}개", ha='center', fontsize=22, fontweight='bold')

    # 하단 산점도
    ax_scatter = fig1.add_subplot(gs[1])
    colors = {'당일치기형': '#D85A30', '체류형': '#1D9E75', '외부유입 낮음': '#378ADD'}
    for t, color in colors.items():
        subset = df_2024[df_2024['type'] == t]
        ax_scatter.scatter(subset['inflow_rate'], subset['consumption_idx'], s=subset['concentration']*20, c=color, label=t, alpha=0.7)
    
    ax_scatter.axvline(mx, color='gray', linestyle='--')
    ax_scatter.axhline(my, color='gray', linestyle='--')
    ax_scatter.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=15)
    ax_scatter.set_xlabel("외부방문자 유입률 (%)")
    ax_scatter.set_ylabel("관광소비 지수 (%)")
    ax_scatter.legend(loc='upper right')

    st.subheader("차트 1. 축제 방문 패턴 분석")
    st.pyplot(fig1)
    with st.expander("사용한 SQL 및 인사이트"):
        st.code(query1)
        st.write("① 인사이트: ")

    # [차트 2 데이터] 업종별 소비액
    query2 = "SELECT * FROM 업종별소비액 WHERE 연도 = 2024"
    df_spend = run_query(query2)
    # 컬럼명을 행으로 변경 (Melt)
    df_spend_melt = df_spend.melt(id_vars=['연도'], var_name='업종', value_name='소비액')
    df_spend_melt = df_spend_melt.sort_values('소비액', ascending=False)

    fig2, ax2 = plt.subplots(figsize=(10, 6))
    sns.barplot(data=df_spend_melt, x='업종', y='소비액', palette=['#D85A30' if '숙박' in x else '#cccccc' for x in df_spend_melt['업종']], ax=ax2)
    ax2.set_title("업종별 소비액 구성 (2024년, 단위: 천원)", loc='left')
    plt.xticks(rotation=45)
    
    st.subheader("차트 2. 업종별 소비액")
    st.pyplot(fig2)
    with st.expander("사용한 SQL 및 인사이트"):
        st.code(query2)
        st.write("② 인사이트: ")

# ==========================================
# 페이지 2: 젠트리피케이션 문제
# ==========================================
elif page == "젠트리피케이션 문제":
    st.title("🏚️ 축제 활성화에 따른 상권 젠트리피케이션 분석")

    # 데이터 로드 및 차분 계산
    # (공실률, 임대료 테이블에서 2024_Q2 - 2022_1Q 계산)
    q_vacancy = "SELECT 상권명, (`2024_Q2` - `2022_1Q`) as v_diff FROM `임대동향 지역별 공실률 소규모 상가`"
    q_rent = "SELECT 상권명, (`2024_Q2` - `2022_1Q`) as r_diff FROM `임대동향 지역별 임대료 소규모 상가`"
    q_mapping = "SELECT 상권명, 연구그룹, 연동자치단체명 FROM 매핑테이블"
    q_inflow = "SELECT 축제명, AVG(지표값) as avg_inflow FROM 문화관광축제주요지표 WHERE 구분명='외부방문자 유입' GROUP BY 축제명"
    
    df_v = run_query(q_vacancy)
    df_r = run_query(q_rent)
    df_m = run_query(q_mapping)
    df_i = run_query(q_inflow)

    # 데이터 병합
    df_gent = df_m.merge(df_v, on='상권명').merge(df_r, on='상권명')
    
    # 실험군/대조군 매핑
    exp_list = ['춘천명동', '보령문화의전당', '서산터미널', '천안역', '천안종합버스터미널', '김제시장', '목포구도심', '하당신도심', '문경점촌흥덕', '안동구도심', '영주중앙', '김해시청/동상시장', '밀양원도심/삼문동', '활천동', '광양사거리', '노형오거리', '중앙사거리']
    df_gent['type'] = df_gent['상권명'].apply(lambda x: '축제 상권' if x in exp_list else '일반 상권')

    # 시각화 1: 젠트리피케이션 산점도
    fig3 = plt.figure(figsize=(10, 10))
    gs = fig3.add_gridspec(2, 1, height_ratios=[1, 5], hspace=0.2)
    
    # 요약 카드
    ax_c = fig3.add_subplot(gs[0])
    ax_c.axis('off')
    avg_v = df_gent[df_gent['type']=='축제 상권']['v_diff'].mean()
    avg_r = df_gent[df_gent['type']=='축제 상권']['r_diff'].mean()
    for i, (label, val, unit) in enumerate([("공실률 변화량(평균)", avg_v, "%p"), ("임대료 변화량(평균)", avg_r, "천원/㎡")]):
        rect = plt.Rectangle((i*0.5, 0.2), 0.45, 0.6, facecolor='#f5f5f5', edgecolor='#D85A30', lw=1)
        ax_c.add_patch(rect)
        ax_c.text(i*0.5 + 0.22, 0.6, label, ha='center', color='gray')
        ax_c.text(i*0.5 + 0.22, 0.35, f"{val:+.2f}{unit}", ha='center', fontsize=20, fontweight='bold')

    ax_s = fig3.add_subplot(gs[1])
    sns.scatterplot(data=df_gent, x='v_diff', y='r_diff', hue='type', 
                    palette={'축제 상권': '#D85A30', '일반 상권': '#1D9E75'}, s=100, ax=ax_s)
    ax_s.axvline(df_gent['v_diff'].median(), ls='--', color='gray')
    ax_s.axhline(df_gent['r_diff'].median(), ls='--', color='gray')
    ax_s.set_title("축제 개최 여부에 따른 상권 변화 (2022 Q1 → 2024 Q2)", loc='left')
    ax_s.set_xlabel("공실률 변화량 (%p)")
    ax_s.set_ylabel("임대료 변화량 (천원/㎡)")

    st.subheader("차트 1. 상권 변화 분석")
    st.pyplot(fig3)

    # 시각화 2: 예산 통제 분석
    q_budget = """
    SELECT 자치단체명, AVG(세출예산총계액)/100000000 as budget_avg
    FROM `기능별 회계별 세출예산`
    WHERE 분야명 IN ('국토및지역개발', '문화및관광') AND 회계연도 BETWEEN 2022 AND 2024
    GROUP BY 자치단체명
    """
    df_budget = run_query(q_budget)
    df_final = df_gent.merge(df_budget, left_on='연동자치단체명', right_on='자치단체명')

    fig4, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    for ax, y_col, title in zip([ax1, ax2], ['v_diff', 'r_diff'], ['공실률 변화', '임대료 변화']):
        sns.scatterplot(data=df_final, x='budget_avg', y=y_col, hue='type', palette={'축제 상권': '#D85A30', '일반 상권': '#1D9E75'}, ax=ax)
        for i in range(len(df_final)):
            ax.text(df_final['budget_avg'][i], df_final[y_col][i], df_final['상권명'][i], fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("지자체 예산 규모 (억원)")
        
    st.subheader("차트 2. 지자체 예산 통제 시 변화 검증")
    st.pyplot(fig4)

# ==========================================
# 페이지 3: 세금 효율성 분석
# ==========================================
elif page == "세금 효율성 분석":
    st.title("💰 축제 재정 건전성 및 세금 회수율 분석")

    # 차트 1: 세금 회수율
    query5 = """
    SELECT `행사·축제명` as name, 
           (CAST(사업수입 AS FLOAT) / NULLIF(총비용, 0)) * 100 as recovery_rate
    FROM 행사원가회계정보
    WHERE 년도 = 2024 AND 총비용 > 0
    ORDER BY recovery_rate DESC
    """
    df_tax = run_query(query5)
    
    def tax_color(v):
        if v >= 20: return '#1D9E75'
        if v >= 10: return '#378ADD'
        if v >= 1: return '#F9AD12'
        return '#D85A30'
    
    fig5, ax5 = plt.subplots(figsize=(10, 10))
    colors = [tax_color(x) for x in df_tax['recovery_rate']]
    ax5.barh(df_tax['name'], df_tax['recovery_rate'], color=colors)
    ax5.set_title("축제별 세금 회수율 (2024, %)", loc='left')
    
    st.subheader("차트 1. 세금 회수율 분석")
    st.pyplot(fig5)

    # 차트 2: 순원가 추이
    query6 = """
    SELECT `행사·축제명` as name, 년도, 순원가
    FROM 행사원가회계정보
    WHERE name IN (SELECT `행사·축제명` FROM 행사원가회계정보 GROUP BY `행사·축제명` HAVING COUNT(DISTINCT 년도) = 3)
    AND 총비용 > 0
    ORDER BY name, 년도
    """
    df_trend = run_query(query6)
    
    fig6, ax6 = plt.subplots(figsize=(12, 7))
    for name in df_trend['name'].unique():
        subset = df_trend[df_trend['name'] == name]
        vals = subset['순원가'].values
        # 추세 판별
        if vals[0] < vals[1] < vals[2]: color, ls = 'red', '-'
        elif vals[0] > vals[1] > vals[2]: color, ls = 'green', '-'
        else: color, ls = 'gray', '--'
        
        ax6.plot(subset['년도'].astype(str), subset['순원가'], label=name, color=color, linestyle=ls, marker='o')

    ax6.set_title("3개년 축제별 순원가 추이 (백만원)", loc='left')
    ax6.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    st.subheader("차트 2. 순원가 추이 분석")
    st.pyplot(fig6)
