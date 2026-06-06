import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# --- [1] 한글 폰트 설정 (Mac/Windows 공용) ---
plt.rcParams['font.family'] = 'Malgun Gothic' # Windows 기준 (Mac은 AppleGothic)
plt.rcParams['axes.unicode_minus'] = False

# --- [2] 유틸리티 함수 (시니어 개발자의 팁: 유연한 데이터 로딩) ---

def get_connection():
    """SQLite 연결 생성 (여기서는 예시를 위해 메모리 DB 사용)"""
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    # 실제 환경에서는 sqlite3.connect('your_data.db')를 사용하세요.
    return conn

def find_matching_table(conn, target_name):
    """유사한 이름의 테이블을 자동으로 찾아줍니다."""
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    target_clean = target_name.replace(" ", "").replace("_", "").lower()
    for t in tables:
        if target_clean in t.replace(" ", "").replace("_", "").lower():
            return t
    return None

def find_col(df, keyword):
    """데이터프레임에서 특정 키워드가 포함된 컬럼명을 반환합니다."""
    for col in df.columns:
        if keyword in col:
            return col
    return None

# --- [3] 샘플 데이터 생성 (실습용) ---
def create_sample_data(conn):
    # 1. 문화관광축제주요지표 생성
    fest_data = pd.DataFrame({
        '연도': [2022, 2023, 2024] * 10,
        '축제명': [f'축제_{i}' for i in range(30)],
        '외부방문자 유입의 지표값': np.random.rand(30),
        '관광지수의 지표값': np.random.rand(30),
        '축제지 집중률의 지표값': np.random.rand(30)
    })
    fest_data.to_sql('문화관광축제주요지표', conn, index=False, if_exists='replace')
    
    # 2. 업종별 소비액 생성
    cons_data = pd.DataFrame({
        '업종명': ['숙박업', '음식점업', '대중교통', '기념품샵', '레저용품', '문화서비스'],
        '소비액(천원)': [50000, 120000, 30000, 45000, 15000, 25000]
    })
    cons_data.to_sql('업종별_소비액_데이터', conn, index=False, if_exists='replace')

# --- [4] 대시보드 UI 구성 ---

conn = get_connection()
create_sample_data(conn) # 샘플 데이터 주입

st.set_page_config(page_title="공공데이터 분석 대시보드", layout="wide")

# 사이드바: 페이지 이동 및 진단 툴바
st.sidebar.title("📌 네비게이션")
page = st.sidebar.radio("페이지 선택", ["축제 현황 분석", "젠트리피케이션 문제", "세금 효율성 분석"])

with st.sidebar.expander("🔍 스키마 진단 툴바"):
    st.write("현재 DB 내 테이블 목록:")
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    st.write(tables)
    if not tables.empty:
        selected_t = st.selectbox("테이블 상세 보기", tables['name'])
        st.write(pd.read_sql(f"PRAGMA table_info('{selected_t}')", conn)[['name', 'type']])

# --- 페이지 1: 축제 현황 분석 ---
if page == "축제 현황 분석":
    st.title("🎡 문화관광축제 및 관광 패턴 분석")
    
    # 데이터 로드 (find_matching_table 활용)
    table_name = find_matching_table(conn, "문화관광축제주요지표")
    df_raw = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    
    # 컬럼 동적 매칭
    col_x = find_col(df_raw, "외부방문자 유입")
    col_y = find_col(df_raw, "관광지수")
    col_size = find_col(df_raw, "축제지 집중률")
    col_year = find_col(df_raw, "연도")

    # 데이터 전처리 (0~100 스케일링)
    df = df_raw.copy()
    df['x_val'] = df[col_x] * 100
    df['y_val'] = df[col_y] * 100
    df['size_val'] = df[col_size] * 100
    
    # 2024년 데이터 필터링
    df_2024 = df[df[col_year] == 2024]
    
    # 중앙값 계산
    mx, my = df_2024['x_val'].median(), df_2024['y_val'].median()

    # 시각화 1: 통합 차트 (요약 카드 + 산점도)
    st.subheader("① 시각화: 관광 패턴 분석 (4사분면)")
    
    fig = plt.figure(figsize=(12, 10))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 5])
    
    # --- 섹션 1: 요약 카드 (Matplotlib로 구현) ---
    ax_card = fig.add_subplot(gs[0])
    ax_card.axis('off')
    
    years = [2022, 2023, 2024]
    for i, yr in enumerate(years):
        # 당일치기형 조건: X >= median AND Y < median
        # (실제 구현 시 전체 기간 median을 쓸지 연도별로 쓸지 결정 가능, 여기선 2024년 기준 median 사용)
        count = len(df[(df[col_year] == yr) & (df['x_val'] >= mx) & (df['y_val'] < my)])
        
        # 카드 그리기
        rect = plt.Rectangle((i*0.3, 0.1), 0.25, 0.8, transform=ax_card.transAxes,
                             facecolor='#f5f5f5', edgecolor='#D85A30' if yr == 2024 else '#cccccc', 
                             linewidth=2 if yr == 2024 else 1)
        ax_card.add_patch(rect)
        ax_card.text(i*0.3 + 0.125, 0.65, f"{yr}년 당일치기형", ha='center', fontsize=12, color='gray')
        ax_card.text(i*0.3 + 0.125, 0.3, f"{count}개", ha='center', fontsize=22, fontweight='bold')

    # --- 섹션 2: 산점도 ---
    ax_scatter = fig.add_subplot(gs[1])
    
    def get_color(row):
        if row['x_val'] >= mx and row['y_val'] < my: return '#D85A30' # 당일치기
        if row['x_val'] >= mx and row['y_val'] >= my: return '#1D9E75' # 체류형
        return '#378ADD' # 외부유입 낮음

    df_2024['color'] = df_2024.apply(get_color, axis=1)
    
    scatter = ax_scatter.scatter(df_2024['x_val'], df_2024['y_val'], 
                                 s=df_2024['size_val']*5, c=df_2024['color'], alpha=0.6)
    
    ax_scatter.axvline(mx, color='gray', linestyle='--', linewidth=1)
    ax_scatter.axhline(my, color='gray', linestyle='--', linewidth=1)
    ax_scatter.set_xlabel("외부방문자 유입률 (%)")
    ax_scatter.set_ylabel("관광소비 지수 (%)")
    ax_scatter.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=20, fontsize=10)
    
    # 범례 설정
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], marker='o', color='w', label='당일치기형', markerfacecolor='#D85A30', markersize=10),
                       Line2D([0], [0], marker='o', color='w', label='체류형', markerfacecolor='#1D9E75', markersize=10),
                       Line2D([0], [0], marker='o', color='w', label='외부유입 낮음', markerfacecolor='#378ADD', markersize=10)]
    ax_scatter.legend(handles=legend_elements, loc='upper right')
    
    st.pyplot(fig)

    st.info("② 사용한 SQL")
    st.code(f"SELECT * FROM {table_name}")
    
    st.success("③ 인사이트")
    st.write("(여기에 나중에 인사이트 내용을 입력하세요)")

    st.divider()

    # 시각화 2: 가로 막대 차트
    st.subheader("① 시각화: 업종별 소비액")
    table_cons = find_matching_table(conn, "업종별 소비액")
    df_cons = pd.read_sql(f"SELECT * FROM {table_cons}", conn)
    
    col_name = find_col(df_cons, "업종명")
    col_val = find_col(df_cons, "소비액")
    
    df_cons = df_cons.sort_values(by=col_val, ascending=False)
    
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    colors = ['#D85A30' if x == '숙박업' else '#cccccc' for x in df_cons[col_name]]
    ax2.bar(df_cons[col_name], df_cons[col_val], color=colors)
    ax2.set_title("업종별 소비액 구성 (2024년, 단위: 천원)", loc='left')
    ax2.set_ylabel("소비액 (천원)")
    
    st.pyplot(fig2)
    
    st.info("② 사용한 SQL")
    st.code(f"SELECT * FROM {table_cons} ORDER BY {col_val} DESC")
    
    st.success("③ 인사이트")
    st.write("(여기에 나중에 인사이트 내용을 입력하세요)")

# --- 페이지 2: 젠트리피케이션 ---
elif page == "젠트리피케이션 문제":
    st.title("🏙️ 젠트리피케이션 지수 분석")
    st.warning("데이터 로드 중...")
    # 여기에 차트 구현 (위와 동일한 패턴)
    st.subheader("① 시각화")
    st.info("② 사용한 SQL")
    st.success("③ 인사이트")

# --- 페이지 3: 세금 효율성 ---
else:
    st.title("💰 세금 효율성 및 재정 자립도")
    st.warning("데이터 로드 중...")
    # 여기에 차트 구현 (위와 동일한 패턴)
    st.subheader("① 시각화")
    st.info("② 사용한 SQL")
    st.success("③ 인사이트")
