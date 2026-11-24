
import streamlit as st
import csv
import io
import math
from datetime import datetime

# ==========================================
# 1. 기본 설정
# ==========================================

st.set_page_config(
    page_title="공유자전거 수요 분석 시스템",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 시간대별·장소별 공유자전거 수요 분석")
st.write(
    "과거 대여 데이터를 바탕으로 시간대와 대여소별 평균 수요를 분석하고, "
    "적정 자전거 배치량을 안내합니다."
)

st.divider()

# ==========================================
# 2. CSV 파일 읽기
# ==========================================

def read_csv_file(uploaded_file):
    content = uploaded_file.getvalue()

    encodings = ["utf-8-sig", "cp949"]

    for encoding in encodings:
        try:
            text = content.decode(encoding)
            reader = csv.DictReader(io.StringIO(text))
            return list(reader)
        except UnicodeDecodeError:
            continue

    st.error("CSV 파일의 인코딩을 읽을 수 없습니다.")
    st.stop()


# ==========================================
# 3. 데이터 업로드
# ==========================================

st.subheader("📂 분석 데이터 업로드")

col1, col2 = st.columns(2)

with col1:
    rental_file = st.file_uploader(
        "대여 기록 CSV",
        type=["csv"],
        key="rental"
    )

with col2:
    stock_file = st.file_uploader(
        "대여소별 자전거 보유량 CSV",
        type=["csv"],
        key="stock"
    )

if rental_file is None or stock_file is None:
    st.info("대여 기록과 자전거 보유량 CSV 파일을 모두 업로드해 주세요.")

    st.markdown("**① 대여 기록 CSV 예시**")
    st.code(
        "대여일시,대여소명\n"
        "2026-01-01 08:15,강남역 1번 출구\n"
        "2026-01-01 08:30,강남역 1번 출구\n"
        "2026-01-01 09:10,시청역 2번 출구\n"
        "2026-01-02 08:20,강남역 1번 출구",
        language="csv"
    )

    st.markdown("**② 자전거 보유량 CSV 예시**")
    st.code(
        "대여소명,잔여자전거\n"
        "강남역 1번 출구,12\n"
        "시청역 2번 출구,8",
        language="csv"
    )

    st.stop()


rental_data = read_csv_file(rental_file)
stock_data = read_csv_file(stock_file)

# ==========================================
# 4. 데이터 전처리
# ==========================================

required_rental = ["대여일시", "대여소명"]
required_stock = ["대여소명", "잔여자전거"]

if not rental_data or not stock_data:
    st.error("업로드한 CSV 파일에 데이터가 없습니다.")
    st.stop()

if not all(key in rental_data[0] for key in required_rental):
    st.error("대여 기록 CSV에 '대여일시', '대여소명' 열이 필요합니다.")
    st.stop()

if not all(key in stock_data[0] for key in required_stock):
    st.error("보유량 CSV에 '대여소명', '잔여자전거' 열이 필요합니다.")
    st.stop()

clean_rentals = []

for row in rental_data:
    try:
        rental_time = datetime.fromisoformat(
            row["대여일시"].strip()
        )

        station = row["대여소명"].strip()

        if not station:
            continue

        clean_rentals.append({
            "날짜": rental_time.date(),
            "시간": rental_time.hour,
            "대여소명": station
        })

    except (ValueError, AttributeError, TypeError):
        continue

if not clean_rentals:
    st.error("유효한 대여 기록을 찾을 수 없습니다.")
    st.stop()

# 보유량 데이터 정리
stock_dict = {}

for row in stock_data:
    try:
        station = row["대여소명"].strip()
        count = int(float(row["잔여자전거"]))

        if station and count >= 0:
            stock_dict[station] = stock_dict.get(station, 0) + count

    except (ValueError, AttributeError, TypeError):
        continue

if not stock_dict:
    st.error("유효한 자전거 보유량 데이터가 없습니다.")
    st.stop()

# ==========================================
# 5. 분석 조건 선택
# ==========================================

st.sidebar.header("🔎 분석 조건")

hours = []

for hour in range(24):
    hours.append(f"{hour:02d}시")

selected_hour = st.sidebar.selectbox(
    "분석할 시간대",
    hours
)

hour_number = int(selected_hour[:2])

available_stations = []

for station in stock_dict:
    available_stations.append(station)

available_stations.sort()

selected_station = st.sidebar.selectbox(
    "분석할 대여소",
    available_stations
)

safety_rate = st.sidebar.slider(
    "수요 대비 여유 배치 비율",
    min_value=1.0,
    max_value=1.5,
    value=1.2,
    step=0.1
)

# ==========================================
# 6. 시간대별·장소별 수요 분석
# ==========================================

def analyze_demand(data, stock, hour, station, rate):

    # 전체 데이터의 관측 날짜 수집
    all_dates = set()

    for row in data:
        all_dates.add(row["날짜"])

    all_dates = sorted(all_dates)

    # 선택한 대여소와 시간대의 대여 기록 집계
    daily_counts = {}

    for date in all_dates:
        daily_counts[date] = 0

    for row in data:
        if (
            row["시간"] == hour
            and row["대여소명"] == station
        ):
            daily_counts[row["날짜"]] += 1

    # 관측 기간 동안의 평균 대여량
    total_rentals = 0

    for count in daily_counts.values():
        total_rentals += count

    average_demand = total_rentals / len(all_dates)

    # 현재 보유 자전거 수
    current_bikes = stock[station]

    # 적정 배치량 계산
    target_bikes = math.ceil(
        average_demand * rate
    )

    difference = target_bikes - current_bikes

    return {
        "average": average_demand,
        "current": current_bikes,
        "target": target_bikes,
        "difference": difference,
        "days": len(all_dates),
        "daily": daily_counts
    }


# ==========================================
# 7. 자전거 배치 가이드
# ==========================================

def make_guide(result):

    difference = result["difference"]
    average = result["average"]

    if average == 0:
        return (
            "⚪ 해당 시간대의 과거 대여 기록이 없습니다.",
            "분석 기간 내 대여 수요가 확인되지 않았습니다."
        )

    elif difference >= 3:
        return (
            "🔴 자전거 추가 배치 권장",
            f"현재보다 자전거 {difference}대를 추가하는 것이 권장됩니다."
        )

    elif difference > 0:
        return (
            "🟠 소량 추가 배치 권장",
            f"자전거 {difference}대를 추가하는 것이 권장됩니다."
        )

    elif difference <= -3:
        return (
            "🔵 자전거 재배치 검토",
            f"현재보다 자전거 {-difference}대를 줄이는 것이 권장됩니다."
        )

    else:
        return (
            "🟢 현재 배치 유지",
            "현재 자전거 보유량이 분석상 적정 수준입니다."
        )


# ==========================================
# 8. 분석 실행
# ==========================================

result = analyze_demand(
    clean_rentals,
    stock_dict,
    hour_number,
    selected_station,
    safety_rate
)

guide_title, guide_description = make_guide(result)

# ==========================================
# 9. 분석 결과 출력
# ==========================================

st.divider()

st.subheader("📊 분석 결과")

st.markdown(
    f"**선택 조건:** {selected_station} / {selected_hour}"
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "평균 시간당 대여 수요",
        f"{result['average']:.2f}대"
    )

with col2:
    st.metric(
        "현재 자전거 보유량",
        f"{result['current']}대"
    )

with col3:
    st.metric(
        "권장 자전거 배치량",
        f"{result['target']}대",
        delta=f"{result['difference']:+d}대"
    )

# ==========================================
# 10. 자전거 수요 및 보유량 그래프
# ==========================================

st.subheader("📈 수요량과 보유량 비교")

chart_data = {
    "평균 대여 수요": result["average"],
    "현재 보유량": result["current"],
    "권장 배치량": result["target"]
}

st.bar_chart(chart_data)

# ==========================================
# 11. 배치 가이드 출력
# ==========================================

st.subheader("🚲 자전거 재배치 가이드")

if result["difference"] >= 3:
    st.error(guide_title)
elif result["difference"] > 0:
    st.warning(guide_title)
elif result["difference"] <= -3:
    st.info(guide_title)
else:
    st.success(guide_title)

st.write(guide_description)

st.caption(
    f"분석 기간: {result['days']}일 | "
    f"수요 대비 여유 배치 비율: {safety_rate:.1f}"
)

# ==========================================
# 12. 날짜별 대여량 확인
# ==========================================

st.divider()
st.subheader("📅 날짜별 대여 기록")

daily_chart = {}

for date, count in result["daily"].items():
    daily_chart[str(date)] = count

st.bar_chart(daily_chart)

# ==========================================
# 13. 상세 분석 데이터 출력 및 다운로드
# ==========================================

st.subheader("📋 상세 분석 데이터")

detail_rows = []

for date, count in result["daily"].items():
    detail_rows.append({
        "날짜": str(date),
        "대여소명": selected_station,
        "시간대": selected_hour,
        "대여량": count
    })

st.dataframe(
    detail_rows,
    use_container_width=True,
    hide_index=True
)

# CSV 다운로드
output = io.StringIO()

writer = csv.DictWriter(
    output,
    fieldnames=["날짜", "대여소명", "시간대", "대여량"]
)

writer.writeheader()
writer.writerows(detail_rows)

st.download_button(
    label="📥 분석 결과 CSV 다운로드",
    data=output.getvalue().encode("utf-8-sig"),
    file_name="공유자전거_수요분석결과.csv",
    mime="text/csv"
)

st.caption(
    "※ 본 분석은 업로드된 과거 대여 기록의 날짜별 평균을 활용한 "
    "기초 수요 분석이며, 실시간 수요나 미래 수요를 예측하지 않습니다."
)
