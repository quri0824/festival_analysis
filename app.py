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
        "2022_4Q": r_2022 + np.array(
