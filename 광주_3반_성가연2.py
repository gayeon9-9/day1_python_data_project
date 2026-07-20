"""------------------------------------------------------------------------------------------
# [실습 2] 파일 I/O, 예외 처리, Pydantic 검증 파이프라인
# 프로그램 설명
1. safe_load_csv()로 CSV 파일을 안전하게 읽어 dict 리스트로 반환한다.
2. SalesRecord(Pydantic v2) 모델로 각 레코드를 검증하여 valid / errors로 분리한다.
3. valid 레코드는 CSV로, errors는 JSON(한글 깨짐 방지를 위해 ensure_ascii=False)으로 저장한다.
4. 저장한 파일을 다시 읽어 건수가 맞는지 확인한다.
(CSV 로딩의 성공/실패는 logging으로 기록하고, finally에서 '로딩 종료'를 출력한다.)
# 작성자 : 성가연  
# 작성일 : 2026-07-20
# 변경내역 : 2026-07-20 - 프로그램 최초 작성
------------------------------------------------------------------------------------------ """
from pathlib import Path
import csv
import json
import logging
from pydantic import BaseModel, Field, ValidationError
##----------------------------------------------------------------------------------##

# 실행 기록 설정
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = Path("Python_Practice2_Data.json")
VALID_PATH = Path("valid_sales.csv")
ERROR_PATH = Path("errors.json")


# CSV를 안전하게 읽고 딕셔너리 리스트로 반환
def safe_load_csv(path: str | Path) -> list[dict] | None:
    path = Path(path)

    try:
        with path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))

        logger.info("CSV 로딩 성공: %s (%d건)", path, len(rows))
        return rows

    except FileNotFoundError:
        logger.error("파일 없음: %s", path)
        return None

    finally:
        print("로딩 종료")

# 판매 데이터 검증 규칙
class SalesRecord(BaseModel):
    month: str = Field(min_length=1)
    region: str = Field(min_length=1)
    amount: float = Field(gt=0)
    category: str | None = None

# 원본 JSON 읽기
with DATA_PATH.open(encoding="utf-8") as file:
    raw_data = json.load(file)


# 정상 데이터와 오류 데이터 분리
valid = []
errors = []

for row_number, row in enumerate(raw_data, start=1):
    try:
        record = SalesRecord.model_validate(row)
        valid.append(record.model_dump())

    except ValidationError as error:
        print(f"{row_number}행 검증 오류:\n{error}")
        errors.append({
            "row": row_number,
            "error": str(error)
        })

# 정상 데이터를 CSV로 저장
with VALID_PATH.open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=list(SalesRecord.model_fields)
    )
    writer.writeheader()
    writer.writerows(valid)

# 오류 데이터를 JSON으로 저장
with ERROR_PATH.open("w", encoding="utf-8") as file:
    json.dump(errors, file, ensure_ascii=False, indent=2)

# 없는 파일 처리 확인
assert safe_load_csv("없는_파일.csv") is None

# 모든 원본 데이터가 정상 또는 오류로 분리됐는지 확인한다.
assert len(valid) + len(errors) == len(raw_data)

# 저장된 결과를 다시 읽는다.
reloaded = safe_load_csv(VALID_PATH)

with ERROR_PATH.open(encoding="utf-8") as file:
    reloaded_errors = json.load(file)

# 저장 전과 재로딩 후의 건수가 같은지 확인한다.
assert reloaded is not None
assert len(reloaded) == len(valid)
assert len(reloaded_errors) == len(errors)

# 최종 결과를 출력한다.
print(f"정상: {len(valid)}건 / 오류: {len(errors)}건")
print(f"재로딩: {len(reloaded)}건")

"""
결과값
- ERROR | 파일 없음: 없는_파일.csv
- 로딩 종료
- INFO | CSV 로딩 성공: valid_sales.csv (100건)
- 로딩 종료
- 정상: 100건 / 오류: 0건
- 재로딩: 100건
"""