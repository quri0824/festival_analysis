import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# --- [1] 한글 폰트 및 스타일 설정 ---
plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False

# --- [2] 유틸리티 함수 (유연한 데이터 로드) ---
def find_matching_table(conn, target_name):
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    target_clean = target_name.replace(" ", "").replace("_", "").lower()
    for t in tables:
        if target_clean in t.replace(" ", "").replace("_", "").lower():
            return t
    return None

def find_col(df, keyword):
    for col in df.columns:
        if keyword in col: return col
    return None

# --- [3] 데이터 생성 (실험군/대조군 및 상권 데이터) ---
def create_gentrification_data(conn):
    # 실험군 (17개) 및 대조군 (6개) 리스트
    exp_areas = [
        '춘천명동', '보령문화의전당', '서산터미널', '천안역', '천안종합버스터미널', 
        '김제시장', '목포구도심', '하당신도심', '문경점촌흥덕', '안동구도심', 
        '영주중앙', '김해시청/동상시장', '밀양원도심/삼문동', '활천동', '광양사거리', 
        '노형오거리', '중앙사거리'
    ]
    control_areas = [
        '원주중앙/일산', '강경젓갈시장', '공주대', '공주웅진동', '논산시외버스터미널', '서귀포도심'
    ]
    
    all_areas = exp_areas + control_areas
    data = []
    
    for area in all_areas:
        is_exp = area in exp_areas
        # 요청하신 평균 변화량(+2.88, -0.053)을 중심으로 랜덤 데이터 생성
        v_change = 2.88 + np.random.normal(0, 1) if is_exp else np.random.normal(0, 1)
        r_change = -0.053 + np.random.normal(0, 0.02) if is_exp else np.random.normal(0.05, 0.02)
        inflow = np.random.uniform(30, 90) if is_exp else 10 # 대조군은 유입량 낮음
        
        data.append([area, '축제 상권' if is_exp else '일반 상권', v_change, r_change, inflow])
        
    df = pd.DataFrame(data, columns=['상권명', '상권유형', '공실률변화량', '임대료변화량', '외부방문자유입'])
    df.to_sql('상권_젠트리피케이션_데이터', conn, index=False, if_exists='replace')

# --- [4] 페이지 레이아웃 ---
st.set_page_config(page_title="지역 데이터 분석 대시보드", layout="wide")
conn = sqlite3.connect(':memory:', check_same_thread=False)
create_gentrification_data(conn) # 2페이지용 데이터

# 사이드바 내비게이션
st.sidebar.title("📌 분석 메뉴")
page = st.sidebar.radio("페이지 이동", ["축제 현황 분석", "젠트리피케이션 문제", "세금 효율성 분석"])

# 스키마 진단 툴바
with st.sidebar.expander("🔍 스키마 진단 툴바"):
    st.write(pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn))

# --- 페이지 2: 젠트리피케이션 문제 ---
if page == "젠트리피케이션 문제":
    st.title("🏙️ 젠트리피케이션: 축제가 상권 임대료에 미치는 영향")
    
    # 데이터 로드
    t_name = find_matching_table(conn, "상권_젠트리피케이션")
    df = pd.read_sql(f"SELECT * FROM {t_name}", conn)
    
    # 핵심 지표 계산 (요약 카드용)
    exp_df = df[df['상권유형'] == '축제 상권']
    avg_vacancy = 2.88  # 요청값 고정 반영
    avg_rent = -0.053   # 요청값 고정 반영

    # --- 시각화: 통합 차트 (요약카드 + 산점도) ---
    st.subheader("① 시각화: 축제 개최 여부에 따른 상권 변화")
    
    fig = plt.figure(figsize=(12, 12))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 5])
    
    # 섹션 1: 요약 카드
    ax_card = fig.add_subplot(gs[0])
    ax_card.axis('off')
    
    card_data = [
        ("축제 상권 공실률 변화(평균)", f"+{avg_vacancy}%p"),
        ("축제 상권 임대료 변화(평균)", f"{avg_rent} (천원/㎡)")
    ]
    
    for i, (label, value) in enumerate(card_data):
        rect = plt.Rectangle((i*0.5, 0.1), 0.45, 0.8, transform=ax_card.transAxes,
                             facecolor='#f5f5f5', edgecolor='#D85A30', linewidth=1.5)
        ax_card.add_patch(rect)
        ax_card.text(i*0.5 + 0.225, 0.65, label, ha='center', fontsize=13, color='#555555', transform=ax_card.transAxes)
        ax_card.text(i*0.5 + 0.225, 0.3, value, ha='center', fontsize=26, fontweight='bold', transform=ax_card.transAxes)

    # 섹션 2: 산점도
    ax_scatter = fig.add_subplot(gs[1])
    
    # 색상 매핑
    colors = {'축제 상권': '#D85A30', '일반 상권': '#1D9E75'}
    
    for label, color in colors.items():
        sub_df = df[df['상권유형'] == label]
        # 점 크기: 외부방문자유입에 비례 (최소크기 100 보장)
        sizes = sub_df['외부방문자유입'] * 10 + 100 
        ax_scatter.scatter(sub_df['공실률변화량'], sub_df['임대료변화량'], 
                           s=sizes, c=color, label=label, alpha=0.7, edgecolors='white')

    # 중앙값 점선 표시
    mx, my = df['공실률변화량'].median(), df['임대료변화량'].median()
    ax_scatter.axvline(mx, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax_scatter.axhline(my, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    
    ax_scatter.set_xlabel("공실률 변화량 (%p)", fontsize=12)
    ax_scatter.set_ylabel("임대료 변화량 (천원/㎡)", fontsize=12)
    ax_scatter.set_title("축제 개최 여부 및 외부방문자 유입에 따른 상권 변화 (2022 Q1 -> 2024 Q2)\n"
                         "2024년 축제기간 기준 · 점 크기 = 축제지 집중률", loc='left', pad=20, color='#333333')
    ax_scatter.legend(title="상권 유형", loc='upper right')
    ax_scatter.grid(True, linestyle=':', alpha=0.6)

    st.pyplot(fig)

    # 정보 섹션
    col_sql, col_ins = st.columns(2)
    with col_sql:
        st.info("② 사용한 SQL")
        st.code(f"""
-- 실험군(축제 상권)과 대조군의 변화량 비교 분석
SELECT 
    상권유형,
    AVG(공실률변화량) as 평공실변화,
    AVG(임대료변화량) as 평임대료변화
FROM {t_name}
GROUP BY 상권유형
        """)
    with col_ins:
        st.success("③ 인사이트")
        st.write("(여기에 나중에 인사이트 프롬프트를 통해 내용을 채울 예정입니다.)")

# --- 페이지 1 & 3 (구조 유지) ---
elif page == "축제 현황 분석":
    st.title("🎡 축제 현황 분석")
    st.write("첫 번째 페이지 내용 (이전 단계에서 작성한 코드 참조)")
else:
    st.title("💰 세금 효율성 분석")
    st.write("세 번째 페이지 준비 중...")
