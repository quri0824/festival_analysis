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
    name_match = find_col(df.columns, ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명"])
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


def detect_numeric_col(df):
    name_match = find_col(df.columns, ["지표", "값", "실적", "방문", "관광객", "점수", "인원"])
    if name_match:
        return name_match
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for col in num_cols:
        if not any(ex in str(col).lower() for ex in ["연도", "년도", "id", "코드"]):
            return col
    return num_cols[0] if num_cols else None


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

# 💡 신규 추가: 지역명을 '충남', '강원' 등 2글자로 통일시키는 헬퍼 함수
def get_short_region(name):
    if pd.isna(name): return ""
    name = str(name).strip()
    mapping = {
        "강원": "강원", "경기": "경기", "경남": "경남", "경상남도": "경남",
        "경북": "경북", "경상북도": "경북", "전남": "전남", "전라남도": "전남",
        "전북": "전북", "전라북도": "전북", "충남": "충남", "충청남도": "충남",
        "충북": "충북", "충청북도": "충북", "제주": "제주", "서울": "서울",
        "부산": "부산", "대구": "대구", "인천": "인천", "광주": "광주",
        "대전": "대전", "울산": "울산", "세종": "세종"
    }
    for key, val in mapping.items():
        if name.startswith(key):
            return val
    return name[:2]


# ==========================================
# Fallback 데이터 (누락된 부분 보강)
# ==========================================
def get_fallback_festival():
    # 지역(개최지) 컬럼 명시 추가
    rows = [
        ("춘천마임축제", "강원", 0.244, 0.524, 0.395),
        ("정선아리랑제", "강원", 0.632, 0.492, 0.865),
        ("영동난계국악축제", "충북", 0.406, 0.480, 0.711),
        ("괴산고추축제", "충북", 0.721, 0.655, 0.671),
        ("천안흥타령축제", "충남", 0.765, 0.699, 0.846),
        ("보령머드축제", "충남", 0.533, 0.518, 0.916),
        ("한산모시문화제", "충남", 0.991, 0.488, 0.928),
        ("김제지평선축제", "전북", 0.631, 0.609, 0.828),
        ("진안홍삼축제", "전북", 0.716, 0.703, 0.981),
        ("임실N치즈축제", "전북", 0.805, 0.898, 0.773),
        ("순창장류축제", "전북", 0.886, 0.518, 0.906),
        ("목포항구축제", "전남", 0.827, 0.521, 0.908),
        ("함평나비축제", "전남", 0.515, 0.619, 0.848),
        ("안동탈춤축제", "경북", 0.645, 0.475, 0.875),
        ("고령대가야축제", "경북", 0.892, 0.855, 0.932),
        ("밀양아리랑대축제", "경남", 0.563, 0.661, 0.927),
        ("탐라문화제", "제주", 0.800, 0.799, 0.823),
        ("서울장미축제", "서울", 0.700, 0.800, 0.600),
        ("인천펜타포트", "인천", 0.850, 0.900, 0.850),
        ("부산국제영화제", "부산", 0.950, 0.950, 0.950)
    ]
    return pd.DataFrame(rows, columns=['축제명', '지역', '외부방문자_유입지표', '관광지수_지표', '축제지_집중률'])


def get_fallback_consume():
    # 💡 모든 업종이 차트에 보이게끔 Mock 데이터에 다수 업종 추가
    return pd.DataFrame({
        "연도": [2021, 2021, 2021, 2022, 2022, 2022, 2023, 2023, 2023],
        "쇼핑업 소비액 (천원)": [15e6, 16e6, 17e6, 18e6, 19e6, 20e6, 21e6, 22e6, 23e6],
        "숙박업 소비액 (천원)": [5e6, 4e6, 6e6, 4e6, 5e6, 3e6, 4e6, 3e6, 2e6],
        "식음료업 소비액 (천원)": [30e6, 32e6, 35e6, 31e6, 33e6, 36e6, 33e6, 35e6, 38e6],
        "여가문화업 소비액 (천원)": [8e6, 9e6, 10e6, 7e6, 8e6, 11e6, 9e6, 10e6, 12e6],
        "교통업 소비액 (천원)": [12e6, 11e6, 13e6, 14e6, 15e6, 14e6, 16e6, 17e6, 18e6]
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
        "자치단체": ["강원 춘천시", "충남 논산시", "전북 김제시", "부산 해운대구", "서울 중랑구"],
        "행사·축제명": ["마임축제", "강경젓갈축제", "지평선축제", "국제영화제", "장미축제"],
        "총비용": [1200000000, 850000000, 1400000000, 2000000000, 900000000],
        "사업수익": [250000000, 120000000, 180000000, 500000000, 150000000],
        "순원가": [950000000, 730000000, 1220000000, 1500000000, 750000000]
    })


# ==========================================
# 페이지 1: 축제 현황
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    st.markdown("축제별 외부방문자 유입과 관광
