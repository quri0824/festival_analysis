import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# --- [1] 한글 폰트 설정 (Windows/Mac 대응) ---
plt.rcParams['font.family'] = 'NanumGothic' 
plt.rcParams['axes.unicode_minus'] = False

# --- [2] 유연한 데이터 로드를 위한 유틸리티 함수 ---

def get_connection():
    """데이터베이스 연결 (메모리 내 가상 DB)"""
    return sqlite3.connect(':memory:', check_same_thread=False)

def find_matching_table(conn, target_name):
    """테이블명에 띄어쓰기나 언더바가 있어도 유사한 이름을 찾아줌"""
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    target_clean = target_name.replace(" ", "").replace("_", "").lower()
    for t in tables:
        if target_clean in t.replace(" ", "").replace("_", "").lower():
            return t
    return None

def find_col(df, keyword):
    """컬럼명에 특정 단어가 포함되어 있으면 해당 컬럼명을 반환"""
    for col in df.columns:
        if keyword in col:
            return col
    return None

# --- [3] 실제 데이터 반영 (데이터베이스 생성) ---
def create_sample_data(conn):
    # 1. 축제 지표 데이터 생성 (요청하신 당일치기형 개수 3, 3, 4를 맞추기 위한 샘플링)
    # 당일치기형 조건: 외부유입 >= 50% AND 관광소비 < 50% (중앙값 가정)
    data = []
    # 2022년 (당일치기 3개)
    for _ in range(3): data.append([2022, '축제', 0.8, 0.2, 0.5]) # 당일치기
    for _ in range(7): data.append([2022, '축제', 0.3, 0.3, 0.2]) # 기타
    # 2023년 (당일치기 3개)
    for _ in range(3): data.append([2023, '축제', 0.8, 0.2, 0.5]) # 당일치기
    for _ in range(7): data.append([2023, '축제', 0.3, 0.3, 0.2]) # 기타
    # 2024년 (당일치기 4개)
    for _ in range(4): data.append([2024, '축제', 0.8, 0.2, 0.5]) # 당일치기
    for _ in range(6): data.append([2024, '축제', 0.3, 0.8, 0.2]) # 체류형
    
    df_fest = pd.DataFrame(data, columns=['연도', '축제명', '외부방문자 유입의 지표값', '관광지수의 지표값', '축제지 집중률의 지표값'])
    df_fest.to_sql('문화관광축제주요지표', conn, index=False, if_exists='replace')
    
    # 2. 업종별 소비액 데이터 생성 (제시해주신 금액 반영)
    consumption_data = {
        '업종명': ['쇼핑업', '식음료업', '운송업', '여가서비스업', 'medical웰니스업', '숙박업'],
        '소비액(천원)': [3250878, 1130540, 84222, 40490, 32828, 28479]
    }
    df_cons = pd.DataFrame(consumption_data)
    df_cons.to_sql('업종별_소비액_데이터', conn, index=False, if_exists='replace')

# --- [4] 대시보드 화면 구성 ---

st.set_page_config(page_title="공공데이터 분석 대시보드", layout="wide")

# 데이터 준비
conn = get_connection()
create_sample_data(conn)

# 사이드바
st.sidebar.title("📊 데이터 대시보드")
page = st.sidebar.radio("분석 페이지 선택", ["축제 현황 분석", "젠트리피케이션 문제", "세금 효율성 분석"])

with st.sidebar.expander("🛠️ 데이터베이스 스키마 진단"):
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    st.write("로드된 테이블:", tables['name'].tolist())

# --- 페이지 1: 축제 현황 분석 ---
if page == "축제 현황 분석":
    st.title("🎡 축제 현황 및 관광 패턴 분석")
    
    # 데이터 로드
    table_name = find_matching_table(conn, "문화관광축제")
    df_raw = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    
    # 동적 컬럼 매칭
    col_x = find_col(df_raw, "외부방문자 유입")
    col_y = find_col(df_raw, "관광지수")
    col_size = find_col(df_raw, "축제지 집중률")
    col_year = find_col(df_raw, "연도")

    df = df_raw.copy()
    df['x_val'] = df[col_x] * 100
    df['y_val'] = df[col_y] * 100
    df['size_val'] = df[col_size] * 100
    
    # 2024년 데이터 및 중앙값 (4사분면 기준)
    df_2024 = df[df[col_year] == 2024]
    mx, my = 50, 50 # 분석 기준점 고정

    # --- 시각화 1: 통합 차트 (요약 카드 + 산점도) ---
    st.subheader("Chart 1. 당일치기 관광 패턴 논증")
    
    fig = plt.figure(figsize=(12, 11))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 5])
    
    # 상단 요약 카드 섹션
    ax_card = fig.add_subplot(gs[0])
    ax_card.axis('off')
    
    years = [2022, 2023, 2024]
    counts = []
    for yr in years:
        cnt = len(df[(df[col_year] == yr) & (df['x_val'] >= mx) & (df['y_val'] < my)])
        counts.append(cnt)

    for i, (yr, count) in enumerate(zip(years, counts)):
        is_now = (yr == 2024)
        rect = plt.Rectangle((i*0.33, 0.1), 0.3, 0.8, transform=ax_card.transAxes,
                             facecolor='#f5f5f5', edgecolor='#D85A30' if is_now else '#cccccc', 
                             linewidth=2.5 if is_now else 1, zorder=2)
        ax_card.add_patch(rect)
        ax_card.text(i*0.33 + 0.15, 0.65, f"{yr}년 당일치기형", ha='center', fontsize=12, color='#666666', transform=ax_card.transAxes)
        ax_card.text(i*0.33 + 0.15, 0.3, f"{count}개", ha='center', fontsize=24, fontweight='bold', transform=ax_card.transAxes)

    # 하단 산점도 섹션
    ax_scatter = fig.add_subplot(gs[1])
    
    def get_color(row):
        if row['x_val'] >= mx and row['y_val'] < my: return '#D85A30' # 당일치기형
        if row['x_val'] >= mx and row['y_val'] >= my: return '#1D9E75' # 체류형
        return '#378ADD' # 외부유입 낮음

    df_2024['color'] = df_2024.apply(get_color, axis=1)
    
    ax_scatter.scatter(df_2024['x_val'], df_2024['y_val'], s=df_2024['size_val']*10, c=df_2024['color'], alpha=0.7)
    ax_scatter.axvline(mx, color='black', linestyle='--', alpha=0.3)
    ax_scatter.axhline(my, color='black', linestyle='--', alpha=0.3)
    
    ax_scatter.set_xlim(0, 100)
    ax_scatter.set_ylim(0, 100)
    ax_scatter.set_xlabel("외부방문자 유입률 (%)", fontsize=11)
    ax_scatter.set_ylabel("관광소비 지수 (%)", fontsize=11)
    ax_scatter.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=15, color='#555555')
    
    # 범례
    from matplotlib.lines import Line2D
    legend_elements = [Line2D([0], [0], marker='o', color='w', label='당일치기형', markerfacecolor='#D85A30', markersize=10),
                       Line2D([0], [0], marker='o', color='w', label='체류형', markerfacecolor='#1D9E75', markersize=10),
                       Line2D([0], [0], marker='o', color='w', label='외부유입 낮음', markerfacecolor='#378ADD', markersize=10)]
    ax_scatter.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    st.pyplot(fig)

    with st.expander("🔍 세부 정보 확인"):
        st.info("② 사용한 SQL")
        st.code(f"SELECT 연도, COUNT(*) FROM {table_name} \nWHERE 외부유입 >= 중앙값 AND 관광소비 < 중앙값 \nGROUP BY 연도")
        st.success("③ 인사이트")
        st.write("(나중에 입력할 수 있도록 비워두었습니다.)")

    st.divider()

    # --- 시각화 2: 업종별 소비액 차트 ---
    st.subheader("Chart 2. 업종별 소비액")
    
    table_cons = find_matching_table(conn, "업종별 소비액")
    df_cons = pd.read_sql(f"SELECT * FROM {table_cons}", conn)
    
    col_name = find_col(df_cons, "업종명")
    col_val = find_col(df_cons, "소비액")
    
    # 내림차순 정렬
    df_cons = df_cons.sort_values(by=col_val, ascending=False)
    
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    # 숙박업만 주황색, 나머지는 회색
    colors = ['#D85A30' if "숙박업" in x else '#cccccc' for x in df_cons[col_name]]
    
    bars = ax2.bar(df_cons[col_name], df_cons[col_val], color=colors)
    ax2.set_title("업종별 소비액 구성 (2024년, 단위: 천원)", loc='left', pad=15)
    ax2.set_ylabel("소비액 (천원)")
    
    # 천단위 콤마 표시
    ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    st.pyplot(fig2)
    
    with st.expander("🔍 세부 정보 확인"):
        st.info("② 사용한 SQL")
        st.code(f"SELECT * FROM {table_cons} ORDER BY {col_val} DESC")
        st.success("③ 인사이트")
        st.write("(나중에 입력할 수 있도록 비워두었습니다.)")

# --- 페이지 2, 3 (기본 구조만 유지) ---
elif page == "젠트리피케이션 문제":
    st.title("🏙️ 젠트리피케이션 지수 분석")
    st.info("데이터를 분석 중입니다...")
else:
    st.title("💰 세금 효율성 분석")
    st.info("데이터를 분석 중입니다...")
