import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# --- [1] 한글 폰트 설정 (Windows/Mac 대응) ---
plt.rcParams['font.family'] = 'NanumGothic' 
plt.rcParams['axes.unicode_minus'] = False

# --- [2] 시니어 개발자의 유틸리티 함수 (유연한 로드 알고리즘) ---

def get_connection():
    """데이터베이스 연결 생성"""
    return sqlite3.connect(':memory:', check_same_thread=False)

def find_matching_table(conn, target_name):
    """테이블명 유사 매칭 (공백, 언더바 무시)"""
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    target_clean = target_name.replace(" ", "").replace("_", "").lower()
    for t in tables:
        if target_clean in t.replace(" ", "").replace("_", "").lower():
            return t
    return None

def find_col(df, keyword):
    """컬럼명 내 키워드 포함 여부로 실제 컬럼명 탐색"""
    for col in df.columns:
        if keyword in col: return col
    return None

# --- [3] 데이터 주입 (제시해주신 수치 반영) ---

def init_database(conn):
    # --- 페이지 1 데이터 (축제 지표) ---
    # 2022(3개), 2023(3개), 2024(4개) 당일치기형 데이터 생성
    fest_list = []
    for yr, count in zip([2022, 2023, 2024], [3, 3, 4]):
        for _ in range(count): fest_list.append([yr, "축제A", 0.8, 0.2, 0.6]) # 당일치기 (X고, Y저)
        for _ in range(5): fest_list.append([yr, "축제B", 0.3, 0.3, 0.2])     # 외부유입 낮음
    df_fest = pd.DataFrame(fest_list, columns=['연도', '축제명', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률'])
    df_fest.to_sql('문화관광축제주요지표', conn, index=False, if_exists='replace')

    # --- 페이지 1 데이터 (업종별 소비액) ---
    cons_data = {
        '업종명': ['쇼핑업', '식음료업', '운송업', '여가서비스업', 'medical웰니스업', '숙박업'],
        '소비액_천원': [3250878, 1130540, 84222, 40490, 32828, 28479]
    }
    pd.DataFrame(cons_data).to_sql('업종별_소비액', conn, index=False, if_exists='replace')

    # --- 페이지 2 데이터 (젠트리피케이션) ---
    exp_areas = ['춘천명동', '보령문화의전당', '서산터미널', '천안역', '천안종합버스터미널', '김제시장', '목포구도심', '하당신도심', '문경점촌흥덕', '안동구도심', '영주중앙', '김해시청/동상시장', '밀양원도심/삼문동', '활천동', '광양사거리', '노형오거리', '중앙사거리']
    control_areas = ['원주중앙/일산', '강경젓갈시장', '공주대', '공주웅진동', '논산시외버스터미널', '서귀포도심']
    
    gent_list = []
    for area in exp_areas: # 실험군
        gent_list.append([area, '축제 상권', 2.88 + np.random.normal(0, 0.5), -0.053 + np.random.normal(0, 0.01), 70])
    for area in control_areas: # 대조군
        gent_list.append([area, '일반 상권', 0.5 + np.random.normal(0, 0.5), 0.02 + np.random.normal(0, 0.01), 20])
    
    df_gent = pd.DataFrame(gent_list, columns=['상권명', '상권유형', '공실률변화량', '임대료변화량', '외부방문자유입'])
    df_gent.to_sql('상권_젠트리피케이션_데이터', conn, index=False, if_exists='replace')

# --- [4] 메인 대시보드 구조 ---

st.set_page_config(page_title="공공데이터 분석 대시보드", layout="wide")
conn = get_connection()
init_database(conn)

# 사이드바 설정
st.sidebar.title("🔍 분석 컨트롤러")
page = st.sidebar.radio("분석 주제 선택", ["1. 축제 현황 분석", "2. 젠트리피케이션 문제", "3. 세금 효율성 분석"])

with st.sidebar.expander("🛠️ 스키마 진단 툴바"):
    st.write("로드된 테이블 리스트:")
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    st.table(tables)

# --- [페이지 1: 축제 현황] ---
if page == "1. 축제 현황 분석":
    st.title("🎡 문화관광축제 현황 및 소비 패턴")
    
    # 데이터 로드
    table = find_matching_table(conn, "문화관광축제주요지표")
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    
    # 차트 1. 산점도 및 요약카드
    st.subheader("Chart 1. 당일치기 관광 패턴 논증")
    
    # 계산 및 전처리
    col_x = find_col(df, "외부방문자")
    col_y = find_col(df, "관광지수")
    col_sz = find_col(df, "집중률")
    df['x_scaled'] = df[col_x] * 100
    df['y_scaled'] = df[col_y] * 100
    
    fig = plt.figure(figsize=(12, 10))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.2, 5])
    
    # 1-1. 요약 카드 섹션
    ax_card = fig.add_subplot(gs[0])
    ax_card.axis('off')
    years = [2022, 2023, 2024]
    mx, my = 50, 50 # 중앙값 기준선
    
    for i, yr in enumerate(years):
        cnt = len(df[(df['연도'] == yr) & (df['x_scaled'] >= mx) & (df['y_scaled'] < my)])
        is_2024 = (yr == 2024)
        rect = plt.Rectangle((i*0.33, 0.1), 0.3, 0.8, transform=ax_card.transAxes, 
                             facecolor='#f5f5f5', edgecolor='#D85A30' if is_2024 else '#ccc', linewidth=2 if is_2024 else 1)
        ax_card.add_patch(rect)
        ax_card.text(i*0.33+0.15, 0.6, f"{yr}년 당일치기형", ha='center', fontsize=12, color='gray', transform=ax_card.transAxes)
        ax_card.text(i*0.33+0.15, 0.3, f"{cnt}개", ha='center', fontsize=22, fontweight='bold', transform=ax_card.transAxes)

    # 1-2. 산점도 섹션
    ax_scat = fig.add_subplot(gs[1])
    df_2024 = df[df['연도'] == 2024].copy()
    
    def get_color(r):
        if r['x_scaled'] >= mx and r['y_scaled'] < my: return '#D85A30' # 당일치기
        if r['x_scaled'] >= mx and r['y_scaled'] >= my: return '#1D9E75' # 체류형
        return '#378ADD' # 외부유입 낮음
    
    df_2024['color'] = df_2024.apply(get_color, axis=1)
    ax_scat.scatter(df_2024['x_scaled'], df_2024['y_scaled'], s=df_2024[col_sz]*500, c=df_2024['color'], alpha=0.6)
    ax_scat.axvline(mx, ls='--', color='gray', lw=1); ax_scat.axhline(my, ls='--', color='gray', lw=1)
    ax_scat.set_xlabel("외부방문자 유입률 (%)"); ax_scat.set_ylabel("관광소비 지수 (%)")
    ax_scat.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=15)
    
    st.pyplot(fig)
    
    # 정보 표시
    c1, c2 = st.columns(2)
    c1.info("② 사용한 SQL"); c1.code(f"SELECT * FROM {table}")
    c2.success("③ 인사이트"); c2.write("(공란: 프롬프트를 통해 내용을 채워주세요)")

    st.divider()

    # 차트 2. 막대 차트
    st.subheader("Chart 2. 업종별 소비액")
    table_c = find_matching_table(conn, "업종별 소비액")
    df_c = pd.read_sql(f"SELECT * FROM {table_c}", conn).sort_values(by="소비액_천원", ascending=False)
    
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    colors = ['#D85A30' if '숙박업' in x else '#cccccc' for x in df_c['업종명']]
    ax2.bar(df_c['업종명'], df_c['소비액_천원'], color=colors)
    ax2.set_title("업종별 소비액 구성 (2024년, 단위: 천원)", loc='left')
    ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    st.pyplot(fig2)

# --- [페이지 2: 젠트리피케이션] ---
elif page == "2. 젠트리피케이션 문제":
    st.title("🏙️ 젠트리피케이션 및 상권 변화 분석")
    
    # 데이터 로드
    table = find_matching_table(conn, "상권_젠트리피케이션")
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    
    st.subheader("Chart 1. 축제 개최 여부에 따른 상권 변화 (2022 Q1 -> 2024 Q2)")
    
    fig = plt.figure(figsize=(12, 10))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 5])
    
    # 2-1. 요약 카드 (실험군 평균)
    ax_card = fig.add_subplot(gs[0])
    ax_card.axis('off')
    card_info = [("공실률 변화량(평균)", "+2.88%p"), ("임대료 변화량(평균)", "-0.053")]
    
    for i, (lab, val) in enumerate(card_info):
        rect = plt.Rectangle((i*0.5, 0.1), 0.45, 0.8, transform=ax_card.transAxes, facecolor='#f5f5f5', edgecolor='#D85A30', linewidth=2)
        ax_card.add_patch(rect)
        ax_card.text(i*0.5+0.225, 0.6, lab, ha='center', fontsize=12, transform=ax_card.transAxes)
        ax_card.text(i*0.5+0.225, 0.3, val, ha='center', fontsize=22, fontweight='bold', transform=ax_card.transAxes)

    # 2-2. 산점도
    ax_scat = fig.add_subplot(gs[1])
    # 실험군/대조군 분리 시각화
    for grp, col in zip(['축제 상권', '일반 상권'], ['#D85A30', '#1D9E75']):
        sub = df[df['상권유형'] == grp]
        ax_scat.scatter(sub['공실률변화량'], sub['임대료변화량'], s=sub['외부방문자유입']*10, c=col, label=grp, alpha=0.7)
    
    mx, my = df['공실률변화량'].median(), df['임대료변화량'].median()
    ax_scat.axvline(mx, ls='--', color='gray', alpha=0.5); ax_scat.axhline(my, ls='--', color='gray', alpha=0.5)
    ax_scat.set_xlabel("공실률 변화량 (%p)"); ax_scat.set_ylabel("임대료 변화량 (천원/㎡)")
    ax_scat.set_title("2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=15)
    ax_scat.legend()
    
    st.pyplot(fig)
    
    c1, c2 = st.columns(2)
    c1.info("② 사용한 SQL"); c1.code(f"SELECT * FROM {table} --실험군/대조군 비교")
    c2.success("③ 인사이트"); c2.write("(공란: 프롬프트를 통해 내용을 채워주세요)")

# --- [페이지 3: 세금 효율성 (Placeholder)] ---
else:
    st.title("💰 세금 효율성 분석")
    st.info("이 페이지는 현재 분석 준비 중입니다.")
