import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import numpy as np

# --- 페이지 설정 ---
st.set_page_config(page_title="공공데이터 분석 대시보드", layout="wide")

# --- 폰트 설정 (한글 깨짐 방지) ---
# Matplotlib에서 한글을 표시하기 위해 나눔고딕 등 한글 폰트 설정이 필요할 수 있습니다.
plt.rcParams['font.family'] = 'Malgun Gothic' # 윈도우 기준
plt.rcParams['axes.unicode_minus'] = False

# --- 데이터베이스 연결 함수 ---
def get_query_result(query):
    conn = sqlite3.connect('project.db')
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# --- 사이드바 네비게이션 ---
st.sidebar.title("🔍 분석 메뉴")
page = st.sidebar.radio("페이지를 선택하세요", ["축제 현황", "젠트리피케이션 문제", "세금 효율성 분석"])

# --- 1번째 페이지: 축제 현황 ---
if page == "축제 현황":
    st.title("🎊 축제 현황 분석")
    st.markdown("#### 문화관광축제 데이터를 이용해 당일치기 관광 패턴을 분석합니다.")

    # [데이터 준비] SQL 쿼리
    # 문화관광축제주요지표 테이블에서 필요한 데이터를 가져와 피벗(재구성)합니다.
    sql_scatter = """
    SELECT 축제명, 개최년도, 구분명, 지표값
    FROM 문화관광축제주요지표
    WHERE 개최년도 IN (2022, 2023, 2024)
    """
    raw_df = get_query_result(sql_scatter)
    
    # 지표 구분에 따라 데이터를 열로 변환 (Pivot)
    df_pivot = raw_df.pivot_table(index=['축제명', '개최년도'], columns='구분명', values='지표값').reset_index()

    # ⭐ [추가할 마법의 코드] 재조립된 데이터의 진짜 기둥(컬럼) 이름들을 화면에 띄워줘!
    st.write("🔍 실제 만들어진 컬럼 이름들:", df_pivot.columns.tolist())
    
    # 2024년 데이터 필터링
    df_2024 = df_pivot[df_pivot['개최년도'] == 2024].copy()

    # --- 차트 1. 산점도 및 요약 카드 ---
    st.subheader("1. 관광 패턴 산점도 및 연도별 요약")
    
    # 메디안(중앙값) 계산
    x_median = df_2024['외부방문자 유입'].median() if '외부방문자 유입' in df_2024 else 50
    y_median = df_2024['관광소비'].median() if '관광소비' in df_2024 else 50

    # 색상 분류 로직
    def get_color(row):
        if row['외부방문자 유입'] >= x_median and row['관광소비'] < y_median:
            return '#D85A30' # 당일치기형 (주황)
        elif row['외부방문자 유입'] >= x_median and row['관광소비'] >= y_median:
            return '#1D9E75' # 체류형 (초록)
        else:
            return '#378ADD' # 외부유입 낮음 (파란)

    df_2024['color'] = df_2024.apply(get_color, axis=1)

    # Figure 생성 (하나의 피겨에 카드와 차트 배치)
    fig = plt.figure(figsize=(12, 10))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 4]) # 상단 카드(1), 하단 차트(4)

    # 1-1. 요약 카드 구현 (2022, 2023, 2024)
    years = [2022, 2023, 2024]
    for i, year in enumerate(years):
        ax_card = fig.add_subplot(gs[0, i])
        
        # '당일치기형' 개수 계산 (해당 연도 중앙값 기준)
        yr_data = df_pivot[df_pivot['개최년도'] == year]
        yr_x_med = yr_data['외부방문자 유입'].median()
        yr_y_med = yr_data['관광소비'].median()
        count = len(yr_data[(yr_data['외부방문자 유입'] >= yr_x_med) & (yr_data['관광소비'] < yr_y_med)])
        
        # 카드 디자인
        border_color = '#D85A30' if year == 2024 else '#cccccc'
        linewidth = 3 if year == 2024 else 1
        rect = plt.Rectangle((0.1, 0.1), 0.8, 0.8, transform=ax_card.transAxes, 
                             color='#f5f5f5', ec=border_color, lw=linewidth, zorder=0)
        ax_card.add_patch(rect)
        
        ax_card.text(0.5, 0.6, f"{year}년 당일치기형", ha='center', va='center', fontsize=12, color='gray')
        ax_card.text(0.5, 0.3, f"{count}개", ha='center', va='center', fontsize=22, fontweight='bold')
        ax_card.axis('off')

    # 1-2. 산점도 구현
    ax_scatter = fig.add_subplot(gs[1, :])
    scatter = ax_scatter.scatter(
        df_2024['외부방문자 유입'], 
        df_2024['관광소비'], 
        s=df_2024['축제지 집중률'] * 10, # 점 크기 조절
        c=df_2024['color'],
        alpha=0.7
    )
    
    # 가이드 라인 및 레이블
    ax_scatter.axvline(x_median, color='gray', linestyle='--', lw=1)
    ax_scatter.axhline(y_median, color='gray', linestyle='--', lw=1)
    ax_scatter.set_xlabel("외부방문자 유입", fontsize=12)
    ax_scatter.set_ylabel("관광소비", fontsize=12)
    ax_scatter.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=20, fontsize=10, color='gray')
    fig.suptitle("축제 방문객 유입-소비 패턴 분석", fontsize=16, fontweight='bold', y=0.95)

    # 범례 커스텀
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='당일치기형', markerfacecolor='#D85A30', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='체류형', markerfacecolor='#1D9E75', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='외부유입 낮음', markerfacecolor='#378ADD', markersize=10)
    ]
    ax_scatter.legend(handles=legend_elements, loc='upper right')

    st.pyplot(fig)

    with st.expander("📝 사용한 SQL 및 인사이트"):
        st.code(sql_scatter, language='sql')
        st.info("💡 인사이트: (이곳에 나중에 프롬프트를 통해 내용을 채울 수 있습니다.)")


    # --- 차트 2. 세로 막대 차트 ---
    st.write("---")
    st.subheader("2. 업종별 소비액")
    
    sql_bar = """
    SELECT * FROM "업종별 소비액" WHERE 연도 = 2024
    """
    df_bar_raw = get_query_result(sql_bar)
    
    # 데이터 재구조화 (컬럼명을 행으로)
    cols = ['쇼핑업 소비액', '식음료업 소비액', '운소업 소비액', '여가서비스업 소비액', '숙박업 소비액', '의료웰니스업 소비액']
    values = df_bar_raw[cols].iloc[0].values
    df_bar = pd.DataFrame({'업종': [c.replace(' 소비액', '') for c in cols], '소비액': values})
    df_bar = df_bar.sort_values(by='소비액', ascending=False)

    fig2, ax2 = plt.subplots(figsize=(10, 6))
    colors = ['#D85A30' if x == '숙박업' else '#cccccc' for x in df_bar['업종']]
    
    bars = ax2.bar(df_bar['업종'], df_bar['소비액'], color=colors)
    ax2.set_ylabel("소비액 (단위: 천원)")
    ax2.set_title("업종별 소비액 구성 (2024년, 단위: 천원)", loc='left', fontsize=12, color='gray')
    
    st.pyplot(fig2)

    with st.expander("📝 사용한 SQL 및 인사이트"):
        st.code(sql_bar, language='sql')
        st.info("💡 인사이트: (이곳에 나중에 프롬프트를 통해 내용을 채울 수 있습니다.)")

# --- 2번째 페이지: 젠트리피케이션 문제 (가이드용 빈 페이지) ---
elif page == "젠트리피케이션 문제":
    st.title("🏘️ 젠트리피케이션 분석")
    st.warning("이 페이지는 데이터를 분석 중입니다. (임대동향 테이블 활용 예정)")
    # 여기에 임대료 및 공실률 차트를 추가할 수 있습니다.

# --- 3번째 페이지: 세금 효율성 분석 (가이드용 빈 페이지) ---
elif page == "세금 효율성 분석":
    st.title("💰 세금 효율성 분석")
    st.warning("이 페이지는 데이터를 분석 중입니다. (세출예산 및 행사원가 테이블 활용 예정)")
    # 여기에 예산 대비 성과 차트를 추가할 수 있습니다.
