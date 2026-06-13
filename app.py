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

# 예외 처리: 데이터베이스 파일 확인 후 경고만 표시 (CSV 폴백 동작 유도)
db_exists = os.path.exists(DB_FILE)
if not db_exists:
    st.warning("⚠️ 데이터베이스 파일(project1.db)이 감지되지 않아 로컬 CSV 데이터 또는 데모용 시뮬레이션 데이터를 활용하여 기동 중입니다.")


# 헬퍼 함수: DB 내 실제 존재하는 테이블 리스트 반환
def get_db_tables():
    if not db_exists:
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


# 헬퍼 함수: 테이블명 오타 보정 매칭
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


# 헬퍼 함수: CSV 파일 오타 보정 매칭
def find_matching_csv(target_name):
    target_stripped = target_name.replace(" ", "").lower()
    for f in os.listdir("."):
        if f.endswith(".csv"):
            f_stripped = f.replace(".csv", "").replace(" ", "").lower()
            if target_stripped == f_stripped or target_stripped in f_stripped or f_stripped in target_stripped:
                return f
    return None


# 헬퍼 함수: 안전한 데이터 로딩 (DB -> CSV -> Fallback 순차 탐색)
def load_table_safely(table_name, fallback_data_func):
    # 1. SQLite 데이터베이스 탐색
    matched_table = find_matching_table(table_name)
    if matched_table:
        conn = sqlite3.connect(DB_FILE)
        try:
            df = pd.read_sql_query(f"SELECT * FROM `{matched_table}`", conn)
            return df, False
        except Exception:
            pass
        finally:
            conn.close()
            
    # 2. 로컬 CSV 파일 탐색
    matched_csv = find_matching_csv(table_name)
    if matched_csv:
        try:
            df = pd.read_csv(matched_csv, encoding='utf-8-sig')
            return df, False
        except Exception:
            pass
            
    # 3. 실패 시 Fallback 임시 데이터 반환
    return fallback_data_func(), True


# 헬퍼 함수: 컬럼명 매칭
def find_col(columns, search_terms):
    for term in search_terms:
        for col in columns:
            clean_col = str(col).replace(" ", "").replace("·", "").replace("_", "").lower()
            clean_term = str(term).replace(" ", "").replace("·", "").replace("_", "").lower()
            if clean_term in clean_col:
                return col
    return None


# 동적 엔진 1: 행정구역(지역)이 포함된 컬럼 자동 검출
def detect_region_col(df):
    name_match = find_col(
        df.columns, 
        ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명"]
    )
    if name_match:
        return name_match
    
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().unique()
            for val in sample:
                if any(reg in str(val) for reg in [
                    "서울", "경기", "인천", "강원", "충북", "충남", 
                    "전북", "전남", "경북", "경남", "제주", "부산", 
                    "대구", "광주", "대전", "울산", "세종"
                ]):
                    return col
    
    obj_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]


# 동적 엔진 2: 년도/ID를 제외한 첫 번째 유효한 수치형 컬럼 검출
def detect_numeric_col(df):
    name_match = find_col(
        df.columns, 
        ["지표", "값", "실적", "방문", "관광객", "점수", "인원"]
    )
    if name_match:
        return name_match
    
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for col in num_cols:
        if not any(ex in str(col).lower() for ex in ["연도", "년도", "id", "코드"]):
            return col
    return num_cols[0] if num_cols else None


# 가로 형태 데이터를 세로 형태로 변환
def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    
    region_col = detect_region_col(df)
    quarter_cols = [
        c for c in df.columns 
        if c != region_col and (
            any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or 
            any(str(yr) in str(c) for yr in range(2015, 2027))
        )
    ]
    if not quarter_cols:
        quarter_cols = df.select_dtypes(include=['number']).columns.tolist()
        quarter_cols = [c for c in quarter_cols if c != region_col]
        
    df_melted = df.melt(
        id_vars=[region_col], 
        value_vars=quarter_cols, 
        var_name="분기", 
        value_name=value_name
    )
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col


# ==========================================
# 행정구역 매핑 및 세로형 축제 데이터 정규화 모듈
# ==========================================
CITY_TO_PROVINCE = {
    "춘천": "강원", "강릉": "강원", "원주": "강원", "속초": "강원", "평창": "강원", "화천": "강원", "인제": "강원", "홍천": "강원", "횡성": "강원",
    "논산": "충남", "천안": "충남", "아산": "충남", "공주": "충남", "보령": "충남", "강경": "충남", "금산": "충남", "부여": "충남", "서천": "충남",
    "김제": "전북", "전주": "전북", "군산": "전북", "익산": "전북", "남원": "전북", "무주": "전북", "임실": "전북", "순창": "전북", "고창": "전북", "부안": "전북",
    "수원": "경기", "성남": "경기", "고양": "경기", "용인": "경기", "부천": "경기", "안산": "경기", "여주": "경기", "이천": "경기", "가평": "경기", "양평": "경기", "포천": "경기",
    "여수": "전남", "순천": "전남", "목포": "전남", "담양": "전남", "보성": "전남", "해남": "전남", "함평": "전남", "진도": "전남", "완도": "전남", "신안": "전남",
    "안동": "경북", "경주": "경북", "포항": "경북", "구미": "경북", "영주": "경북", "문경": "경북", "봉화": "경북", "청송": "경북", "영덕": "경북", "울릉": "경북",
    "진주": "경남", "창원": "경남", "김해": "경남", "통영": "경남", "거제": "경남", "남해": "경남", "하동": "경남", "산청": "경남", "함양": "경남", "합천": "경남",
    "청주": "충북", "충주": "충북", "제천": "충북", "단양": "충북", "괴산": "충북", "영동": "충북", "옥천": "충북", "보은": "충북",
    "제주": "제주", "서귀포": "제주",
    "서울": "서울", "부산": "부산", "대구": "대구", "인천": "인천", "광주": "광주", "대전": "대전", "울산": "울산", "세종": "세종"
}

def get_region_from_festival(name, df_cost=None):
    name = str(name)
    
    # 1. 원가회계 정보가 제공될 경우 자치단체 텍스트 매핑 활용
    if df_cost is not None:
        org_col = find_col(df_cost.columns, ["자치단체", "지자체"])
        name_col = find_col(df_cost.columns, ["행사·축제명", "축제명", "행사명"])
        if org_col and name_col:
            for _, row in df_cost.iterrows():
                fest_name = str(row[name_col])
                if fest_name in name or name in fest_name:
                    org_val = str(row[org_col])
                    for reg in ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "부산", "대구", "광주", "대전", "울산", "세종"]:
                        if reg in org_val:
                            return reg

    # 2. 내장 사전을 기반으로 지자체 텍스트 매칭
    for city, prov in CITY_TO_PROVINCE.items():
        if city in name:
            return prov
            
    # 3. 고유 명사 예외 처리
    if "지평선" in name:
        return "전북"
    if "머드" in name:
        return "충남"
    if "탈춤" in name:
        return "경북"
    if "대보름" in name:
        return "부산"
    return None


def normalize_festival_data(df, df_cost=None):
    # CSV의 롱 포맷 식별용 주요 컬럼 확인
    gubun_col = find_col(df.columns, ["구분명", "구분"])
    val_col = find_col(df.columns, ["지표값", "값", "실적"])
    name_col = find_col(df.columns, ["축제명", "행사명", "축제"])
    
    if gubun_col and val_col and name_col:
        try:
            # 실적 평가는 '축제기간'을 기준으로 통일하여 분석 편차 제거
            group_col = find_col(df.columns, ["그룹명", "그룹"])
            if group_col:
                df_filtered = df[df[group_col].astype(str).str.contains("축제기간")].copy()
                if df_filtered.empty:
                    df_filtered = df.copy()
            else:
                df_filtered = df.copy()
                
            # 롱 포맷 -> 와이드 포맷으로 구조 재가공 (피벗)
            df_pivoted = df_filtered.pivot_table(
                index=[name_col], 
                columns=gubun_col, 
                values=val_col, 
                aggfunc='mean'
            ).reset_index()
            
            # 비율 데이터(0~1)를 백분율(0~100) 단위로 통일 (축제지 집중률 및 관광소비 포함)
            for col in ["외부방문자 유입", "현지인방문자 유입", "축제지 집중률", "관광소비"]:
                matched_c = find_col(df_pivoted.columns, [col])
                if matched_c:
                    df_pivoted[matched_c] = pd.to_numeric(df_pivoted[matched_c], errors='coerce').fillna(0)
                    if df_pivoted[matched_c].max() <= 1.0:
                        df_pivoted[matched_c] = df_pivoted[matched_c] * 100
            
            # 분석을 위한 표준 '지자체' 행정구역 매핑 추가
            df_pivoted["지자체"] = df_pivoted[name_col].apply(lambda x: get_region_from_festival(x, df_cost))
            return df_pivoted
        except Exception:
            return df
    else:
        # 기존 와이드 형태일 때 '지자체'가 결여되어 있다면 보강
        if "지자체" not in df.columns:
            name_col = find_col(df.columns, ["축제명", "행사명", "축제"]) or df.columns[0]
            df["지자체"] = df[name_col].apply(lambda x: get_region_from_festival(x, df_cost))
        return df


# ==========================================
# Fallback 시뮬레이션용 예비 데이터 생성기
# ==========================================
def get_fallback_festival():
    # 유형별(당일치기형, 체류형, 외부유입 낮음) 분포를 사분면과 격자에 매핑하기 위해 보정한 가상 데이터
    return pd.DataFrame({
        "축제명": ["춘천닭갈비축제", "강경젓갈축제", "지평선축제", "머드축제"],
        "현지인방문자 유입": [32.4, 45.1, 28.7, 15.3],
        "외부방문자 유입": [82.6, 51.9, 75.3, 84.7],
        "관광소비": [35.2, 78.9, 42.4, 75.1],
        "축제지 집중률": [75.4, 58.2, 91.3, 84.5],
        "지자체": ["강원", "충남", "전북", "충남"]
    })

def get_fallback_consume():
    return pd.DataFrame({
        "연도": [2021, 2021, 2021, 2022, 2022, 2022, 2023, 2023, 2023],
        "쇼핑업 소비액 (천원)": [15e6, 16e6, 17e6, 18e6, 19e6, 20e6, 21e6, 22e6, 23e6],
        "숙박업 소비액 (천원)": [5e6, 4e6, 6e6, 4e6, 5e6, 3e6, 4e6, 3e6, 2e6]
    })

def get_fallback_property_vacancy():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [12.1, 14.5, 10.2, 8.5, 9.1, 11.2, 13.1, 14.0],
        "2022_2Q": [12.3, 14.8, 10.5, 8.7, 9.3, 11.5, 13.5, 14.2],
        "2022_3Q": [12.8, 15.2, 11.2, 9.0, 8.9, 12.1, 14.0, 13.8],
        "2022_4Q": [13.1, 15.9, 11.8, 9.2, 8.5, 12.4, 14.5, 13.3],
        "2024_2Q": [13.5, 16.2, 12.0, 9.5, 8.7, 12.8, 14.9, 13.1]
    })

def get_fallback_property_rent():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [3.2, 2.5, 2.8, 5.1, 4.2, 3.8, 4.0, 3.5],
        "2022_2Q": [3.3, 2.6, 2.9, 5.2, 4.1, 3.9, 4.1, 3.4],
        "2022_3Q": [3.4, 2.7, 3.0, 5.3, 4.0, 4.1, 4.2, 3.3],
        "2022_4Q": [3.4, 2.8, 3.1, 5.4, 3.9, 4.2, 4.2, 3.3],
        "2024_2Q": [3.5, 2.8, 3.1, 5.5, 4.0, 4.3, 4.2, 3.2]
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
# 1. 페이지 1: 축제 현황 및 업종별 누적 소비 구조
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    st.markdown("축제 지표 데이터 구조를 동적으로 정제하여 시계열 동향을 보다 명확하게 파악합니다.")
    
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_fest = normalize_festival_data(df_fest)
    df_consume, is_c_mock = load_table_safely("업종별소비액", get_fallback_consume)
    
    if is_f_mock or is_c_mock:
        st.sidebar.warning("⚠️ 일부 원본 데이터 누락으로 예비 시뮬레이션 데이터를 함께 활용 중입니다.")
        
    col1, col2 = st.columns(2)
    
    # 1) 축제별 관광소비 및 외부인 유입 수준 4사분면 버블 차트 (col1)
    with col1:
        st.subheader("📍 축제 유형 분석 (관광소비 × 외부인 유입)")
        name_col = find_col(
            df_fest.columns, 
            ["축제명", "행사명", "축제", "이름"]
        ) or df_fest.columns[0]
        
        foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"])
        consume_col = find_col(df_fest.columns, ["관광소비", "소비"])
        focus_col = find_col(df_fest.columns, ["축제지 집중률", "집중률"])
        
        if foreign_col and consume_col and focus_col:
            df_fest[foreign_col] = pd.to_numeric(df_fest[foreign_col], errors='coerce').fillna(0)
            df_fest[consume_col] = pd.to_numeric(df_fest[consume_col], errors='coerce').fillna(0)
            df_fest[focus_col] = pd.to_numeric(df_fest[focus_col], errors='coerce').fillna(0)
            
            # 중앙값 연산 (데이터 결여 시 0)
            x_median = df_fest[consume_col].median() if len(df_fest) > 0 else 0
            y_median = df_fest[foreign_col].median() if len(df_fest) > 0 else 0
            
            if pd.isna(x_median): x_median = 0
            if pd.isna(y_median): y_median = 0
            
            # 사분면 분류 알고리즘 구축
            def classify_quadrant(row):
                y_val = row[foreign_col]
                x_val = row[consume_col]
                if y_val >= y_median and x_val < x_median:
                    return "당일치기형"
                elif y_val >= y_median and x_val >= x_median:
                    return "체류형"
                else:
                    return "외부유입 낮음"
            
            df_fest["유형"] = df_fest.apply(classify_quadrant, axis=1)
            
            # 버블 최소 크기 및 표출 안전성 보장용 임시 컬럼 생성
            df_fest["_bubble_size"] = df_fest[focus_col].apply(lambda x: x if x > 0 else 8)
            
            fig1 = px.scatter(
                df_fest,
                x=consume_col,
                y=foreign_col,
                size="_bubble_size",
                color="유형",
                color_discrete_map={
                    "당일치기형": "#D85A30",
                    "체류형": "#1D9E75",
                    "외부유입 낮음": "#378ADD"
                },
                hover_name=name_col,
                text=name_col,
                title="축제별 관광소비 및 외부인 유입 수준 (중앙값 기준 사분면)",
                labels={
                    consume_col: "관광소비 지수",
                    foreign_col: "외부인 방문자 유입 (%)",
                    "_bubble_size": "축제지 집중률 (%)",
                    "유형": "축제 유형"
                },
                template="plotly_white"
            )
            
            # 중앙값 구분 기준선(Dashed Line) 추가
            fig1.add_vline(x=x_median, line_dash="dash", line_color="gray", annotation_text="X 중앙값", annotation_position="top left")
            fig1.add_hline(y=y_median, line_dash="dash", line_color="gray", annotation_text="Y 중앙값", annotation_position="bottom right")
            
            fig1.update_traces(textposition='top center')
            st.plotly_chart(fig1, use_container_width=True, key="p1_visit_bubble_chart")
        else:
            st.write("분석 필수 항목(관광소비, 외부인 유입, 축제지 집중률) 검색에 실패하였습니다. 원본 데이터프레임을 직접 출력합니다.")
            st.dataframe(df_fest.head())
            
    # 2) 시계열 꺾은선 소비 차트 (col2)
    with col2:
        st.subheader("📈 연도별 업종 소비 흐름 (꺾은선)")
        year_col = find_col(df_consume.columns, ["연도", "년도", "시기"]) or df_consume.columns[0]
        
        other_cols = [c for c in df_consume.columns if c != year_col]
        
        df_melted_consume = df_consume.melt(
            id_vars=[year_col],
            value_vars=other_cols,
            var_name="소비업종",
            value_name="소비액"
        )
        
        df_melted_consume["소비업종"] = df_melted_consume["소비업종"].astype(str)\
            .str.replace(" 소비액", "")\
            .str.replace(" (천원)", "", regex=False)\
            .str.replace("(천원)", "", regex=False)\
            .str.strip()
            
        df_melted_consume["소비액"] = pd.to_numeric(df_melted_consume["소비액"], errors='coerce').fillna(0)
        
        df_sub = df_melted_consume[[year_col, "소비업종", "소비액"]].copy()
        df_sub.columns = ["_temp_year", "_temp_sector", "_temp_amount"]
        df_trend = df_sub.groupby(["_temp_year", "_temp_sector"])["_temp_amount"].sum().reset_index()
        df_trend.columns = [year_col, "소비업종", "소비액"]
        
        fig2 = px.line(
            df_trend,
            x=year_col,
            y="소비액",
            color="소비업종",
            markers=True,
            title="연도별 업종 총 소비액 변동 추이",
            labels={year_col: "연도", "소비액": "소비액(단위: 천원)", "소비업종": "업종구분"},
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True, key="p1_consume_trend_line_safe")

    st.info("""
    **💡 데이터 분석 결과 보고**
    
    데이터 분석 결과, 다른 소비 카테고리에 비해 '숙박업 소비액'의 비중이 낮게 분포하는 특성이 나타납니다. 이는 다수의 방문객들이 목적지에 체류하기보다는 단기 '당일치기 관광'을 주로 소비하고 있음을 시사합니다. 향후 실질적인 지방 관광 활성화와 상권 유치를 위해서는 체류 기반 프로그램을 확장할 필요성이 제기됩니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (상관성 추적 보완)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제가 상권 변동(임대료 및 공실률)에 미치는 영향을 실험군과 대조군 설정을 통해 분석합니다.")
    
    df_vac, is_v_mock = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, is_r_mock = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    
    # 축제 데이터 전처리 및 지자체-원가 매칭 통합
    df_fest = normalize_festival_data(df_fest, df_cost)
    
    if is_v_mock or is_r_mock or is_f_mock or is_c_mock:
        st.sidebar.warning("⚠️ 일부 원본 데이터 누락으로 예비 시뮬레이션 데이터를 함께 활용 중입니다.")
        
    quarter_cols_vac = [c for c in df_vac.columns if any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."])]
    quarter_cols_vac = sorted(quarter_cols_vac)
    
    if len(quarter_cols_vac) >= 2:
        first_q = quarter_cols_vac[0]
        last_q = quarter_cols_vac[-1]
    else:
        first_q, last_q = "2022_1Q", "2024_2Q"
        
    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)
    
    # 1) 공실률 변화량 및 임대료 변화율 연산
    df_vac_calc = df_vac[[reg_col_vac, first_q, last_q]].copy()
    df_vac_calc["공실률_first"] = pd.to_numeric(df_vac_calc[first_q], errors='coerce').fillna(0)
    df_vac_calc["공실률_last"] = pd.to_numeric(df_vac_calc[last_q], errors='coerce').fillna(0)
    df_vac_calc["공실률변화량"] = df_vac_calc["공실률_last"] - df_vac_calc["공실률_first"]
    
    df_rent_calc = df_rent[[reg_col_rent, first_q, last_q]].copy()
    df_rent_calc["임대료_first"] = pd.to_numeric(df_rent_calc[first_q], errors='coerce').fillna(1e-5)
    df_rent_calc["임대료_last"] = pd.to_numeric(df_rent_calc[last_q], errors='coerce').fillna(0)
    df_rent_calc["임대료변화율"] = ((df_rent_calc["임대료_last"] - df_rent_calc["임대료_first"]) / df_rent_calc["임대료_first"]) * 100
    
    # 2) 상권 변화 데이터 통합
    df_prop = pd.merge(
        df_vac_calc[[reg_col_vac, "공실률변화량"]], 
        df_rent_calc[[reg_col_rent, "임대료변화율"]], 
        left_on=reg_col_vac, 
        right_on=reg_col_rent
    )
    df_prop["매칭키"] = df_prop[reg_col_vac].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 3) 축제 규모(외부방문자 유입) 연동
    fest_reg = detect_region_col(df_fest)
    foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"]) or detect_numeric_col(df_fest)
    
    df_fest_clean = df_fest.copy()
    df_fest_clean[foreign_col] = pd.to_numeric(df_fest_clean[foreign_col], errors='coerce').fillna(0)
    
    df_f_sub = df_fest_clean[[fest_reg, foreign_col]].copy()
    df_f_sub.columns = ["_temp_reg", "_temp_foreign"]
    df_fest_group = df_f_sub.groupby("_temp_reg")["_temp_foreign"].mean().reset_index()
    
    df_fest_group.columns = ["지자체명", "외부방문자유입"]
    df_fest_group["매칭키"] = df_fest_group["지자체명"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 4) 지자체 총 예산액 연동
    cost_org = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    cost_val = find_col(df_cost.columns, ["총비용"]) or df_cost.select_dtypes(include=['number']).columns[-1]
    
    df_cost_clean = df_cost.copy()
    df_cost_clean[cost_val] = pd.to_numeric(df_cost_clean[cost_val], errors='coerce').fillna(0)
    
    df_c_sub = df_cost_clean[[cost_org, cost_val]].copy()
    df_c_sub.columns = ["_temp_org", "_temp_cost"]
    df_cost_group = df_c_sub.groupby("_temp_org")["_temp_cost"].sum().reset_index()
    
    df_cost_group.columns = ["예산지자체", "예산총액(원)"]
    df_cost_group["매칭키"] = df_cost_group["예산지자체"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 5) 종합 조인 (실험군 vs 대조군 레이블 수립)
    df_relation = pd.merge(df_prop, df_fest_group, on="매칭키", how="left")
    df_relation = pd.merge(df_relation, df_cost_group, on="매칭키", how="left")
    
    df_relation["외부방문자유입"] = df_relation["외부방문자유입"].fillna(0)
    df_relation["예산총액(원)"] = df_relation["예산총액(원)"].fillna(1e6)
    
    df_relation["상권구분"] = df_relation["지자체명"].apply(
        lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)"
    )
    
    # 거품 크기의 급격한 불균형 및 표현 한계를 완화하기 위한 크기 보정식 적용
    df_relation["점크기_방문자"] = df_relation["외부방문자유입"].apply(lambda x: x * 100 if x <= 1.0 else x)
    df_relation["점크기_방문자"] = df_relation["점크기_방문자"].apply(lambda x: x if x > 0 else 8)
    
    df_relation["예산(백만원)"] = df_relation["예산총액(원)"] / 1000000
    df_relation["점크기_예산"] = df_relation["예산(백만원)"] / 100
    df_relation.loc[df_relation["점크기_예산"] < 5, "점크기_예산"] = 8
    
    # ------------------------------------------
    # 차트 1번: 임대료 변화율 x 공실률 변화 산점도
    # ------------------------------------------
    st.subheader("📊 차트 1: 임대료 변화율 × 공실률 변화 사분면 매트릭스")
    st.write("1사분면(우상단: 임대료 상승 + 공실률 증가)은 임차인이 내몰리는 **젠트리피케이션 압력**이 상대적으로 두드러지는 위험 영역입니다.")
    
    fig1 = px.scatter(
        df_relation,
        x="임대료변화율",
        y="공실률변화량",
        size="점크기_방문자",
        color="상권구분",
        text=reg_col_vac,
        color_discrete_map={
            "축제 상권 (실험군)": "#FF4B4B",
            "일반 상권 (대조군)": "#1F77B4"
        },
        labels={
            "임대료변화율": f"임대료 변화율 (% / {first_q} ➔ {last_q})",
            "공실률변화량": f"공실률 변화량 (p.p. / {first_q} ➔ {last_q})",
            "점크기_방문자": "외부방문자 유입 지수 (환산)"
        },
        template="plotly_white"
    )
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.add_vline(x=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig1, use_container_width=True, key="p2_quadrant_matrix")
    
    # ------------------------------------------
    # 차트 2번: 3차원 버블 차트 (예산 규모 통제 분석)
    # ------------------------------------------
    st.subheader("🪐 차트 2: 지자체 예산 규모를 통제한 3차원 버블 입체 분석")
    st.write("지자체의 예산 고저를 통제 변수로 두고 축제 개최 여부에 따른 부동산 상권 변동의 정위적 구분을 고찰합니다.")
    
    fig2 = px.scatter_3d(
        df_relation,
        x="임대료변화율",
        y="공실률변화량",
        z="예산(백만원)",
        size="점크기_예산",
        color="상권구분",
        text=reg_col_vac,
        color_discrete_map={
            "축제 상권 (실험군)": "#FF4B4B",
            "일반 상권 (대조군)": "#1F77B4"
        },
        labels={
            "임대료변화율": "임대료 변화율 (%)",
            "공실률변화량": "공실률 변화량 (p.p.)",
            "예산(백만원)": "지자체 예산 규모 (백만원)",
            "상권구분": "상권 유형"
        },
        template="plotly_white"
    )
    fig2.update_layout(margin=dict(l=0, r=0, b=0, t=40))
    st.plotly_chart(fig2, use_container_width=True, key="p2_3d_bubble")

    # ------------------------------------------
    # 차트 3번: 시계열 실시간 동향 비교 (꺾은선)
    # ------------------------------------------
    st.subheader("📈 차트 3: 축제 유무에 따른 분기별 임대료 및 공실률 실시간 추이")
    st.write("시간 흐름의 연장선상에서 두 비교군(실험군 및 대조군)의 주요 상권 지표 추이를 조망합니다.")
    
    m_vac_full, r_v_col = melt_quarters(df_vac, "공실률")
    m_rent_full, r_r_col = melt_quarters(df_rent, "임대료")
    
    m_vac_full["매칭키"] = m_vac_full[r_v_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    m_rent_full["매칭키"] = m_rent_full[r_r_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    m_vac_full = pd.merge(m_vac_full, df_fest_group[["매칭키", "지자체명"]], on="매칭키", how="left")
    m_vac_full["상권구분"] = m_vac_full["지자체명"].apply(lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)")
    
    m_rent_full = pd.merge(m_rent_full, df_fest_group[["매칭키", "지자체명"]], on="매칭키", how="left")
    m_rent_full["상권구분"] = m_rent_full["지자체명"].apply(lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)")
    
    m_vac_full["공실률"] = pd.to_numeric(m_vac_full["공실률"], errors='coerce').fillna(0)
    m_rent_full["임대료"] = pd.to_numeric(m_rent_full["임대료"], errors='coerce').fillna(0)
    
    v_sub = m_vac_full[["상권구분", "분기", "공실률"]].copy()
    v_sub.columns = ["_temp_group", "_temp_quarter", "_temp_vac"]
    df_vac_trend = v_sub.groupby(["_temp_group", "_temp_quarter"])["_temp_vac"].mean().reset_index()
    df_vac_trend.columns = ["상권구분", "분기", "평균공실률(%)"]
    df_vac_trend = df_vac_trend.sort_values(by="분기")
    
    r_sub = m_rent_full[["상권구분", "분기", "임대료"]].copy()
    r_sub.columns = ["_temp_group", "_temp_quarter", "_temp_rent"]
    df_rent_trend = r_sub.groupby(["_temp_group", "_temp_quarter"])["_temp_rent"].mean().reset_index()
    df_rent_trend.columns = ["상권구분", "분기", "평균임대료"]
    df_rent_trend = df_rent_trend.sort_values(by="분기")
    
    t1, t2 = st.tabs(["💰 평균 임대료 시계열 흐름", "🏚️ 평균 공실률 시계열 흐름"])
    with t1:
        fig_r_trend = px.line(
            df_rent_trend,
            x="분기",
            y="평균임대료",
            color="상권구분",
            markers=True,
            title="실험군 vs 대조군 분기별 평균 임대료 격차",
            color_discrete_map={"축제 상권 (실험군)": "#FF4B4B", "일반 상권 (대조군)": "#1F77B4"},
            template="plotly_white"
        )
        st.plotly_chart(fig_r_trend, use_container_width=True)
    with t2:
        fig_v_trend = px.line(
            df_vac_trend,
            x="분기",
            y="평균공실률(%)",
            color="상권구분",
            markers=True,
            title="실험군 vs 대조군 분기별 평균 공실률 격차",
            color_discrete_map={"축제 상권 (실험군)": "#FF4B4B", "일반 상권 (대조군)": "#1F77B4"},
            template="plotly_white"
        )
        st.plotly_chart(fig_v_trend, use_container_width=True)

    st.markdown("---")
    st.markdown("""
    **📋 상권 분석 요약**
    * **시계열 추적**: 차트 3의 추이를 통하여, 축제 활성화 구역과 일반 통제 구역 사이에서 시간에 따라 나타나는 상권 변동의 편차를 통계적으로 모니터링할 수 있습니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 관광 효과 (가치 효율성 ROI 지수 도입)
# ==========================================
def render_page3():
    st.title("💸 정부 예산 세금 ROI 가치 진단")
    st.markdown("축제 투입 순원가 대비 외부 유치 실적을 기초로 예산 집행 대비 공공 편익 성과를 검토합니다.")
    
    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    
    # 축제 데이터 전처리 및 지자체 매칭 통합
    df_fest = normalize_festival_data(df_fest, df_cost)
    
    if is_c_mock or is_f_mock:
        st.sidebar.warning("⚠️ 일부 원본 데이터 누락으로 예비 시뮬레이션 데이터를 함께 활용 중입니다.")
        
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
        
        df_melted = df_sub.melt(
            id_vars=[name_col],
            value_vars=["총비용(백만원)", "순원가(백만원)"],
            var_name="예산지표",
            value_name="금액"
        )
        
        fig = px.bar(
            df_melted,
            x=name_col,
            y="금액",
            color="예산지표",
            barmode="group",
            title="자치단체 지출 대비 순 세금부담액(순원가) 비교 (단위: 백만원)",
            labels={"금액": "예산 규모 (백만원)", name_col: "축제/행사명"},
            color_discrete_sequence=px.colors.sequential.Agsunset,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True, key="p3_budget_bar")
        
    # ------------------------------------------
    # 예산 대비 외부방문객 유치 가치(ROI) 분석
    # ------------------------------------------
    st.subheader("💡 세금 1천만 원당 외부인 관광 유입 유치 지수 (Tax ROI Index)")
    st.write("지출된 행사 순원가 대비 실제로 발생한 외부 방문 유입도를 비교하여 세금 투입당 공공가치 유치 성과를 평가합니다.")
    
    fest_reg = detect_region_col(df_fest)
    foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"]) or detect_numeric_col(df_fest)
    
    df_fest_clean = df_fest.copy()
    df_fest_clean[foreign_col] = pd.to_numeric(df_fest_clean[foreign_col], errors='coerce').fillna(0)
    
    df_sub["매칭키"] = df_sub[org_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    df_f_map = df_fest_clean[[fest_reg, foreign_col]].copy()
    df_f_map.columns = ["지자체명", "외부방문자"]
    df_f_map["매칭키"] = df_f_map["지자체명"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    df_roi = pd.merge(df_sub, df_f_map, on="매칭키", how="left")
    df_roi["외부방문자"] = df_roi["외부방문자"].fillna(0)
    
    # 효율성 지수 산출: (외부방문자 규모 / (순원가 / 10,000,000))
    df_roi["세금효율성_ROI"] = df_roi.apply(
        lambda r: (r["외부방문자"] / (r[net_cost_col] / 10000000)) if r[net_cost_col] > 0 else 0, axis=1
    )
    
    if not df_roi.empty:
        fig_roi = px.bar(
            df_roi,
            x=name_col,
            y="세금효율성_ROI",
            text_auto=".2f",
            title="축제별 세금 투입 대비 외부 유입 가치 (ROI 지수)",
            labels={"세금효율성_ROI": "세금 1천만원 당 외부 유입 지수", name_col: "축제명"},
            color="세금효율성_ROI",
            color_continuous_scale="Reds",
            template="plotly_white"
        )
        st.plotly_chart(fig_roi, use_container_width=True, key="p3_tax_roi_chart")
    else:
        st.write("진단 데이터의 충분한 확보를 대기하고 있어 효율성 차트 구성을 임시 생략합니다.")
        
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📉 세금 효율성 분석")
        st.markdown("""
        * **자원 배분 관점**: 효율성 ROI 지수가 높은 축제 및 행사는 상대적으로 제한된 공적 적자 내에서 많은 외부 유입 성과를 거두었음을 알 수 있습니다.
        * **예산 구조 개선**: 성과 지표가 낮게 누적되는 비효율 사업 예산을 점검하고 우수 축제 지원군으로 재배분하는 재정적 점검 전략을 모색할 수 있습니다.
        """)
    with col2:
        st.write("### ✈️ 지방 관광 대체 효과")
        st.markdown("""
        * **관광 수요 흡수**: 지역적 축제 예산 지원을 통하여 해외나 타 상권으로 유출될 수 있는 내수 관광 수요를 관내로 순환시키는 마중물 효과를 유도합니다.
        * **인구 소멸 예방**: 정주 인구가 부족해지는 소도시 거점에 외부 생활인구를 반복적으로 유입시킴으로써 지역 내 단기 활력을 견인하는 공공 가치가 존재합니다.
        """)


# ==========================================
# 4. 메인 실행 함수 및 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    
    with st.sidebar.expander("🛠️ 실시간 데이터셋 진단"):
        st.write("데이터베이스 내 테이블 구조:")
        tables = get_db_tables()
        if tables:
            st.code("\n".join(tables), language="text")
        else:
            st.info("project1.db 파일이 없거나 테이블이 비어 있습니다. 로컬 CSV 파일을 우선 탐색합니다.")
            
    page = st.sidebar.selectbox(
        "원하는 분석 페이지를 선택하세요.",
        ["1. 축제 현황 분석", "2. 젠트리피케이션 분석", "3. 세금 효율성 분석"]
    )
    
    if page == "1. 축제 현황 분석":
        render_page1()
    elif page == "2. 젠트리피케이션 분석":
        render_page2()
    elif page == "3. 세금 효율성 분석":
        render_page3()


if __name__ == "__main__":
    main()
