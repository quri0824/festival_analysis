import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import numpy as np

# --- [1] 한글 폰트 설정 (Windows/Mac 공용) ---
plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False

# --- [2] 시니어 개발자의 유틸리티 함수 (유연한 로직) ---

def get_connection():
    """가상의 SQLite 데이터베이스 연결"""
    return sqlite3.connect(':memory:', check_same_thread=False)

def find_matching_table(conn, target_name):
    """유사한 이름의 테이블을 자동으로 탐색"""
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)['name'].tolist()
    target_clean = target_name.replace(" ", "").replace("_", "").lower()
    for t in tables:
        if target_clean in t.replace(" ", "").replace("_", "").lower():
            return t
    return None

def find_col(df, keyword):
    """컬럼명에서 특정 키워드를 찾아 실제 이름을 반환"""
    for col in df.columns:
        if keyword in col: return col
    return None

# --- [3] 데이터베이스 초기화 ---

def init_database(conn):
    # (1) 문화관광축제주요지표 — 2024년 실제 데이터
    fest_data = [
        ("춘천마임축제",      0.244, 0.524, 0.395),
        ("정선아리랑제",      0.632, 0.492, 0.865),
        ("영동난계국악축제",   0.406, 0.480, 0.711),
        ("괴산고추축제",      0.721, 0.655, 0.671),
        ("천안흥타령축제",    0.765, 0.699, 0.846),
        ("보령머드축제",      0.533, 0.518, 0.916),
        ("서산해미읍성축제",  0.717, 0.654, 0.859),
        ("금산인삼축제",      0.680, 0.726, 0.906),
        ("한산모시문화제",    0.991, 0.488, 0.928),
        ("김제지평선축제",    0.631, 0.609, 0.828),
        ("진안홍삼축제",      0.716, 0.703, 0.981),
        ("임실N치즈축제",     0.805, 0.898, 0.773),
        ("순창장류축제",      0.886, 0.518, 0.906),
        ("목포항구축제",      0.827, 0.521, 0.908),
        ("함평나비축제",      0.515, 0.619, 0.848),
        ("안동탈춤축제",      0.645, 0.475, 0.875),
        ("영주풍기인삼축제",  0.489, 0.349, 0.808),
        ("문경찻사발축제",    0.347, 0.554, 0.752),
        ("청송사과축제",      0.572, 0.661, 0.940),
        ("고령대가야축제",    0.892, 0.855, 0.932),
        ("김해분청도자기축제", 0.865, 0.631, 0.795),
        ("밀양아리랑대축제",  0.563, 0.661, 0.927),
        ("하동야생차문화축제", 0.190, 0.403, 0.446),
        ("산청한방약초축제",  0.624, 0.496, 0.824),
        ("탐라문화제",        0.800, 0.799, 0.823),
    ]
    df_fest = pd.DataFrame(fest_data, columns=['축제명', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률'])
    df_fest['연도'] = 2024
    df_fest.to_sql('문화관광축제주요지표', conn, index=False)

    # (2) 업종별 소비액 생성
    cons_data = {
        '업종명': ['쇼핑업', '식음료업', '운송업', '여가서비스업', '의료웰니스업', '숙박업'],
        '소비액_천원': [3250878, 1130540, 84222, 40490, 32828, 28479]
    }
    pd.DataFrame(cons_data).to_sql('업종별_소비액', conn, index=False)

    # (3) 젠트리피케이션 & 예산 데이터 생성
    exp_areas = ['춘천명동', '보령문화의전당', '서산터미널', '천안역', '천안종합버스터미널',
                 '김제시장', '목포구도심', '하당신도심', '문경점촌흥덕', '안동구도심',
                 '영주중앙', '김해시청/동상시장', '밀양원도심/삼문동', '활천동',
                 '광양사거리', '노형오거리', '중앙사거리']
    control_areas = ['원주중앙/일산', '강경젓갈시장', '공주대', '공주웅진동', '논산시외버스터미널', '서귀포도심']

    gent_list = []
    for area in exp_areas:
        gent_list.append([area, '축제 상권', 2.88 + np.random.normal(0, 0.3),
                          -0.053 + np.random.normal(0, 0.01), 75, np.random.randint(1000, 5000)])
    for area in control_areas:
        gent_list.append([area, '일반 상권', 0.5 + np.random.normal(0, 0.3),
                          0.02 + np.random.normal(0, 0.01), 20, np.random.randint(500, 3000)])
    pd.DataFrame(gent_list, columns=['상권명', '상권유형', '공실률변화량', '임대료변화량',
                                      '외부방문자유입', '예산규모_억원']).to_sql('상권_변화_데이터', conn, index=False)

    # (4) 세금 회수율 데이터
    tax_data = [
        ('임실N치즈축제', 500000, 2000000),
        ('보령머드축제', 450000, 2200000),
        ('논산딸기축제', 350000, 1800000),
    ]
    for i in range(26):
        tax_data.append((f'무수익축제_{i}', 0, 1000000))
    pd.DataFrame(tax_data, columns=['축제명', '사업수익', '총비용']).to_sql('축제_재정_2024', conn, index=False)

    # (5) 순원가 추이 데이터
    trend_list = [
        (2022, '천안흥타령춤축제', 2196), (2023, '천안흥타령춤축제', 2800), (2024, '천안흥타령춤축제', 3407),
        (2022, '보령머드축제', 4542),     (2023, '보령머드축제', 3800),     (2024, '보령머드축제', 3053),
        (2022, '기타축제', 1000),         (2023, '기타축제', 1200),         (2024, '기타축제', 1100),
    ]
    pd.DataFrame(trend_list, columns=['연도', '축제명', '순원가']).to_sql('축제_순원가_추이', conn, index=False)


# --- [4] UI 및 페이지 로직 ---

st.set_page_config(page_title="지역 데이터 통합 분석 대시보드", layout="wide")
conn = get_connection()
init_database(conn)

# 사이드바
st.sidebar.title("📊 분석 메뉴")
page = st.sidebar.radio("보고서 페이지 이동",
                        ["1. 축제 현황 분석", "2. 젠트리피케이션 문제", "3. 세금 효율성 분석"])

with st.sidebar.expander("🔍 데이터베이스 진단 (Schema)"):
    st.write(pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn))


# --- [페이지 1: 축제 현황] ---
if page == "1. 축제 현황 분석":
    st.title("🎡 축제 현황 및 관광 패턴 분석")

    # ── Chart 1. 당일치기 관광 패턴 산점도 ──────────────────────────────
    st.subheader("Chart 1. 당일치기 관광 패턴 논증")

    df_fest = pd.read_sql("SELECT * FROM 문화관광축제주요지표 WHERE 연도 = 2024", conn)

    # 백분율 변환
    df_fest['x_val'] = df_fest['외부방문자_유입지표'] * 100   # 외부방문자 유입률 (%)
    df_fest['y_val'] = df_fest['관광지수_지표'] * 100         # 관광소비 지수 (%)

    # 중앙값 기준 분류
    mv = df_fest['x_val'].median()   # 외부방문자 중앙값
    mc = df_fest['y_val'].median()   # 관광소비 중앙값

    def classify(row):
        if row['x_val'] >= mv and row['y_val'] < mc:
            return "당일치기형"
        elif row['x_val'] >= mv and row['y_val'] >= mc:
            return "체류형"
        else:
            return "외부유입 낮음"

    df_fest['유형'] = df_fest.apply(classify, axis=1)

    color_map = {
        "당일치기형":   "#D85A30",
        "체류형":       "#1D9E75",
        "외부유입 낮음": "#378ADD",
    }
    df_fest['color'] = df_fest['유형'].map(color_map)

    # 레이블 표시 축제 및 offset
    label_fests = {
        "한산모시문화제":    ( 0.8, -2.5),
        "임실N치즈축제":    ( 0.8, -2.5),
        "고령대가야축제":   ( 0.8,  2.0),
        "탐라문화제":       (-9.0,  2.0),
        "천안흥타령축제":   ( 0.8, -2.5),
        "순창장류축제":     (-10.0,  2.0),
        "영주풍기인삼축제": ( 0.8,  2.0),
        "하동야생차문화축제":( 0.8,  2.0),
    }

    # 점 크기: 집중률 * 500
    sizes = df_fest['축제지_집중률'] * 500

    fig1, ax = plt.subplots(figsize=(11, 7))
    fig1.patch.set_facecolor('white')
    ax.set_facecolor('white')

    # 중앙값 점선
    ax.axvline(mv, ls='--', color='#bbbbbb', linewidth=1.0, zorder=1)
    ax.axhline(mc, ls='--', color='#bbbbbb', linewidth=1.0, zorder=1)

    # 산점도 (유형별로 분리하여 범례 처리)
    scatter_handles = []
    for type_name, hex_color in color_map.items():
        sub = df_fest[df_fest['유형'] == type_name]
        sc = ax.scatter(
            sub['x_val'], sub['y_val'],
            s=sub['축제지_집중률'] * 500,
            c=hex_color,
            alpha=0.72,
            edgecolors=hex_color,
            linewidths=1.2,
            zorder=3,
            label=type_name,
        )
        scatter_handles.append(mpatches.Patch(color=hex_color, label=type_name))

    # 축제명 레이블
    for _, row in df_fest.iterrows():
        if row['축제명'] in label_fests:
            dx, dy = label_fests[row['축제명']]
            ax.annotate(
                row['축제명'],
                xy=(row['x_val'], row['y_val']),
                xytext=(row['x_val'] + dx, row['y_val'] + dy),
                fontsize=8.5,
                color='#444444',
                ha='left',
            )

    # 툴팁 (mplcursors)
    try:
        import mplcursors
        cursor = mplcursors.cursor(ax.collections, hover=True)

        @cursor.connect("add")
        def on_add(sel):
            idx = sel.index
            row = df_fest.iloc[idx]
            sel.annotation.set_text(
                f"{row['축제명']}\n"
                f"외부방문자 유입률: {row['x_val']:.1f}%\n"
                f"관광소비 지수: {row['y_val']:.1f}%\n"
                f"집중률: {row['축제지_집중률']*100:.1f}%\n"
                f"유형: {row['유형']}"
            )
            sel.annotation.get_bbox_patch().set(
                facecolor='white', edgecolor='#cccccc', alpha=0.95
            )
    except ImportError:
        pass  # mplcursors 미설치 시 툴팁 생략

    ax.set_xlabel("외부방문자 유입률 (%)", fontsize=11, color='#666666')
    ax.set_ylabel("관광소비 지수 (%)", fontsize=11, color='#666666')
    ax.set_title("2024년 축제기간 기준  ·  점 크기 = 축제지 집중률", loc='left',
                 fontsize=10, color='#888888', pad=10)
    ax.tick_params(colors='#999999', labelsize=9)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    for spine in ax.spines.values():
        spine.set_edgecolor('#e0e0e0')
    ax.grid(False)

    ax.legend(
        handles=scatter_handles,
        loc='upper left',
        fontsize=9,
        framealpha=0.9,
        edgecolor='#dddddd',
    )

    plt.tight_layout()
    st.pyplot(fig1)

    col1, col2 = st.columns(2)
    with col1:
        st.info("② SQL")
        st.code("SELECT * FROM 문화관광축제주요지표 WHERE 연도 = 2024")
    with col2:
        st.success("③ 인사이트")
        daytrip_cnt = int((df_fest['유형'] == '당일치기형').sum())
        stay_cnt    = int((df_fest['유형'] == '체류형').sum())
        st.write(f"당일치기형 **{daytrip_cnt}개** / 체류형 **{stay_cnt}개** / "
                 f"외부유입 낮음 **{int((df_fest['유형']=='외부유입 낮음').sum())}개**")

    st.divider()

    # ── Chart 2. 업종별 소비액 ────────────────────────────────────────────
    st.subheader("Chart 2. 업종별 소비액")
    df_c = pd.read_sql("SELECT * FROM 업종별_소비액 ORDER BY 소비액_천원 DESC", conn)
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    colors2 = ['#D85A30' if '숙박업' in x else '#cccccc' for x in df_c['업종명']]
    ax2.bar(df_c['업종명'], df_c['소비액_천원'], color=colors2)
    ax2.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))
    st.pyplot(fig2)


# --- [페이지 2: 젠트리피케이션] ---
elif page == "2. 젠트리피케이션 문제":
    st.title("🏙️ 젠트리피케이션 및 예산 통제 분석")
    df_g = pd.read_sql("SELECT * FROM 상권_변화_데이터", conn)

    # Chart 1. 상권 변화 산점도
    st.subheader("Chart 1. 축제 상권 vs 일반 상권 변화")
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    for grp, col in zip(['축제 상권', '일반 상권'], ['#D85A30', '#1D9E75']):
        sub = df_g[df_g['상권유형'] == grp]
        ax1.scatter(sub['공실률변화량'], sub['임대료변화량'],
                    s=sub['외부방문자유입'] * 10, c=col, label=grp, alpha=0.6)
    ax1.set_xlabel("공실률 변화량 (%p)")
    ax1.set_ylabel("임대료 변화량 (천원/㎡)")
    ax1.legend()
    st.pyplot(fig1)

    # Chart 2. 예산 통제 산점도
    st.subheader("Chart 2. 지자체 예산 통제 시 상권 변화 검증")
    fig2, (sax1, sax2) = plt.subplots(1, 2, figsize=(15, 6))
    for grp, col in zip(['축제 상권', '일반 상권'], ['#D85A30', '#1D9E75']):
        sub = df_g[df_g['상권유형'] == grp]
        sax1.scatter(sub['예산규모_억원'], sub['공실률변화량'], c=col, label=grp)
        sax2.scatter(sub['예산규모_억원'], sub['임대료변화량'], c=col, label=grp)
        for _, r in sub.iterrows():
            sax1.text(r['예산규모_억원'], r['공실률변화량'], r['상권명'], fontsize=8)
            sax2.text(r['예산규모_억원'], r['임대료변화량'], r['상권명'], fontsize=8)
    st.pyplot(fig2)
    st.info("② SQL")
    st.code("SELECT a.*, b.예산 FROM 상권 a JOIN 예산 b ON a.상권=b.상권")


# --- [페이지 3: 세금 효율성] ---
elif page == "3. 세금 효율성 분석":
    st.title("💰 축제 세금 효율성 분석")

    # Chart 1. 세금 회수율
    st.subheader("Chart 1. 축제별 세금 회수율 (2024)")
    sql = ("SELECT 축제명, (사업수익 * 100.0 / 총비용) as 회수율 "
           "FROM 축제_재정_2024 WHERE 총비용 > 0 ORDER BY 회수율 DESC LIMIT 15")
    df_tax = pd.read_sql(sql, conn)
    df_tax['color'] = df_tax['회수율'].apply(
        lambda x: '#D85A30' if x >= 20 else '#378ADD' if x >= 10 else '#1D9E75' if x > 0 else '#cccccc'
    )
    fig1, ax1 = plt.subplots(figsize=(10, 7))
    ax1.barh(df_tax['축제명'], df_tax['회수율'], color=df_tax['color'])
    ax1.invert_yaxis()
    st.pyplot(fig1)
    st.info("② SQL")
    st.code(sql)

    # Chart 2. 순원가 추이
    st.subheader("Chart 2. 축제별 순원가 추이 (2022-2024)")
    df_trend = pd.read_sql("SELECT * FROM 축제_순원가_추이", conn)
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    for name in df_trend['축제명'].unique():
        sub = df_trend[df_trend['축제명'] == name].sort_values('연도')
        vals = sub['순원가'].values
        if vals[0] < vals[1] < vals[2]:
            col, ls = 'red', '-'
        elif vals[0] > vals[1] > vals[2]:
            col, ls = 'green', '-'
        else:
            col, ls = 'gray', '--'
        ax2.plot(sub['연도'].astype(str), vals, marker='o',
                 color=col, linestyle=ls, label=name)
    ax2.legend(loc='upper left', bbox_to_anchor=(1, 1))
    st.pyplot(fig2)
