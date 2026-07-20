## [실습 1] 자료구조 집계, 컴프리헨션, 제너레이터 
## 프로그램 설명 : 판매 데이터를 JSON 파일에서 불러온 후 조건별로 필터링하고 지역, 카테고리, 월을 기준으로 거래 건수와 매출을 집계 
            ##  또한 리스트와 제너레이터의 메모리 사용량을 비교
## 작성자 : 성가연
## 작성일 : 2026-07-20
## 변경내역 : 2026-07-20 - 프로그램 최초 작성

# json파일 불러오기
import json
# 리스트와 제너레이터의 메모리 비교시 사용
import sys
# dict·set·Counter 실전
from collections import Counter, defaultdict

# 분석에 사용할 데이터 파일명
DATA_FILE = "Python_Practice2_Data.json"

##----------------------------------------------------------------------------------##
## JSON 파일 불러오기 및 예외 처리
# json파일 불러오기 시도
try:
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        sales = json.load(file)
# 파일이 없는 경우 오류 메시지 출력
except FileNotFoundError:
    print(f"[오류] {DATA_FILE} 파일을 찾을 수 없습니다.")
    sys.exit()
# 파일의 형식이 틀리면 오류 메시지 출력
except json.JSONDecodeError:
    print(f"[오류] {DATA_FILE}의 JSON 형식이 올바르지 않습니다.")
    sys.exit() #오류 발생 시 계산 중단

print(f"[확인] 총 {len(sales)}건의 데이터를 불러왔습니다.")

##----------------------------------------------------------------------------------##
## 리스트/딕셔너리 컴프리헨션
# 1. amount가 1000 이상인 거래만 필터링
filtered_sales = [
    sale for sale in sales if sale["amount"] >= 1000
]

# 중복을 제거한 지역 집합
regions = {sale["region"] for sale in filtered_sales}

# 지역별 총매출 계산
region_total = {
    region: sum(
        sale["amount"]
        for sale in filtered_sales
        if sale["region"] == region
    )
    for region in sorted(regions)
}

# 결과 검증
assert region_total == {
    "광주": 4830, "대구": 8320, "대전": 6300, "부산": 4550,
    "서울": 17670, "세종": 5750, "울산": 7270, "인천": 11950
}

print("\n[1] 필터링 거래 수:", len(filtered_sales))
print("[1] 지역별 총매출:", region_total)

##----------------------------------------------------------------------------------##
## Counter + defaultdict
#2.필터링된 1000 이상 거래에 대해서만 지역별 거래 건수를 계산
region_counts = Counter(
    sale["region"] for sale in filtered_sales
)

# 거래 건수가 많은 지역부터 정렬
region_ranking = region_counts.most_common()

# 거래 건수와 most_common() 순서 검증 
assert region_ranking == [
    ("서울", 10),
    ("인천", 8),
    ("대구", 7),
    ("대전", 5),
    ("울산", 5),
    ("세종", 4),
    ("광주", 4),
    ("부산", 4)
]

print("\n[2] 지역별 거래 건수:", region_ranking)


# 새로운 카테고리 발생 시 빈 리스트를 자동 생성
category_amounts = defaultdict(list)


for sale in filtered_sales:
    category_amounts[sale["category"]].append(sale["amount"])
print("[2] 카테고리별 amount 리스트:")

for category, amounts in category_amounts.items():
    print(f"- {category}: {amounts}")

##----------------------------------------------------------------------------------##
## 제너레이터 - 메모리 비교
# 3. 메모리비교

# amount가 1000보다 큰 거래, 하나씩 반환
def generate_large_sales(sales_data):
    for sale in sales_data:
        if sale["amount"] > 1000:
            yield sale


# 리스트와 제너레이터 생성
large_sales_list = [
    sale for sale in sales if sale["amount"] > 1000
]
large_sales_generator = generate_large_sales(sales)

# 메모리 크기 비교
list_size = sys.getsizeof(large_sales_list)
generator_size = sys.getsizeof(large_sales_generator)

assert generator_size < list_size

print("\n[3] 리스트 크기:", list_size, "bytes") # 결과 표시 - [3] 리스트 크기: 472 bytes
print("[3] 제너레이터 크기:", generator_size, "bytes") # 결과 표시 - [3] 제너레이터 크기: 208 bytes

##----------------------------------------------------------------------------------##
## 종합 - 월별 카테고리 매출 집계
# 4. 월별 카테고리별 총매출
# 4. amount가 1000 이상인 거래를 month·category 기준으로 그룹핑
grouped_sales = defaultdict(lambda: defaultdict(int))

# month를 첫 번째 키, category를 두 번째 키로 사용해 amount 누적
for sale in filtered_sales:
    grouped_sales[sale["month"]][sale["category"]] += sale["amount"]

# 딕셔너리 컴프리헨션으로 월별·카테고리별 총매출 dict 완성
month_category_total = {
    month: dict(categories)
    for month, categories in grouped_sales.items()
}

print("\n[4] 월별·카테고리별 총매출:", month_category_total)


# Checkpoint: 필터링된 거래에서 금액 상위 3건 내림차순 정렬
top3 = sorted(
    filtered_sales,
    key=lambda sale: sale["amount"],
    reverse=True
)[:3]

assert [sale["amount"] for sale in top3] == [2500, 2200, 2200]

print("\n[4] 금액 상위 3건:", top3)

""" 결과 표시 (top3 금액 내림차순 정렬)
#[{'region': '서울', 'category': '전자', 'amount': 2500, 'month': '2024-04'}, 
# {'region': '인천', 'category': '전자', 'amount': 2200, 'month': '2024-04'}, 
# {'region': '서울', 'category': '전자', 'amount': 2200, 'month': '2024-01'}] """
