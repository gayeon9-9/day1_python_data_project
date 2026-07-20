"""Day1 종합실습: 실제 API 비동기 수집 파이프라인

1. asyncio와 httpx로 API 3개를 동시에 수집
2. Pydantic v2 모델로 응답 데이터를 검증
3. 검증된 데이터를 하나의 DataFrame으로 정리
4. CSV와 Parquet으로 저장하고 읽기·쓰기 시간을 비교

작성자: 성가연
작성일: 2026-07-20
"""

from __future__ import annotations
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import httpx
import pandas as pd
from pydantic import BaseModel, ValidationError
from models import CountryResponse, IpResponse, WeatherResponse


# 현재 파일을 기준으로 output 폴더 경로 생성
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

CSV_PATH = OUTPUT_DIR / "api_data.csv"
PARQUET_PATH = OUTPUT_DIR / "api_data.parquet"
ERROR_PATH = OUTPUT_DIR / "validation_errors.json"


# 서울의 3일 시간대별 기온과 강수확률을 요청
OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=37.5665"
    "&longitude=126.9780"
    "&hourly=temperature_2m,precipitation_probability"
    "&forecast_days=3"
    "&timezone=Asia/Seoul"
)

# 대한민국 국가 정보를 요청
COUNTRIES_URL = "https://countries.dev/alpha/KOR"

# 8.8.8.8 IP의 지역 정보를 요청
# ip-api 무료 API는 HTTP 주소를 사용
IP_API_URL = "http://ip-api.com/json/8.8.8.8"


# API 이름과 주소를 한 곳에서 관리
API_URLS = {
    "open_meteo": OPEN_METEO_URL,
    "countries_dev": COUNTRIES_URL,
    "ip_api": IP_API_URL,
}


@dataclass(frozen=True)
class FetchResult:
    """API 하나의 수집 결과."""

    source: str
    data: dict[str, Any] | None
    elapsed: float
    error: str | None


async def fetch_api(
    client: httpx.AsyncClient,
    source: str,
    url: str,
) -> FetchResult:
    """API 하나를 호출하고 응답시간과 결과를 반환"""

    start = time.perf_counter()

    try:
        response = await client.get(url)

        # 400번대나 500번대 응답이면 HTTP 오류를 발생시킴
        response.raise_for_status()

        # 정상 응답을 JSON 딕셔너리로 변환
        data = response.json()
        elapsed = time.perf_counter() - start

        return FetchResult(
            source=source,
            data=data,
            elapsed=elapsed,
            error=None,
        )

    except httpx.HTTPError as error:
        elapsed = time.perf_counter() - start

        return FetchResult(
            source=source,
            data=None,
            elapsed=elapsed,
            error=f"HTTP 오류: {error}",
        )

    except ValueError as error:
        # 응답이 JSON 형식이 아닐 때 처리
        elapsed = time.perf_counter() - start

        return FetchResult(
            source=source,
            data=None,
            elapsed=elapsed,
            error=f"JSON 변환 오류: {error}",
        )


async def collect_all_apis() -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, str]],
]:
    """asyncio.gather로 API 3개를 동시에 수집"""

    timeout = httpx.Timeout(10.0)

    headers = {
        "User-Agent": "SKALA-Day1-Project/1.0",
    }

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        # 세 작업을 먼저 만듦
        tasks = [fetch_api(client, source, url) for source, url in API_URLS.items()]

        start = time.perf_counter()

        # API 3개를 순서대로 기다리지 않고 동시에 실행
        results = await asyncio.gather(*tasks)

        total_elapsed = time.perf_counter() - start

    raw_data: dict[str, dict[str, Any]] = {}

    errors: list[dict[str, str]] = []

    print("=" * 62)
    print("API 비동기 수집 결과")
    print("=" * 62)

    for result in results:
        if result.error is None and result.data is not None:
            raw_data[result.source] = result.data

            print(f"[성공] {result.source:<15} {result.elapsed * 1000:>9.2f} ms")

        else:
            print(f"[실패] {result.source:<15} {result.elapsed * 1000:>9.2f} ms")

            errors.append(
                {
                    "source": result.source,
                    "stage": "collection",
                    "error": result.error or "알 수 없는 오류",
                }
            )

    print("-" * 62)
    print(f"전체 동시 수집 시간: {total_elapsed * 1000:.2f} ms")
    print(f"정상 응답 API     : {len(raw_data)}/3개")

    return raw_data, errors


# API 이름과 해당 Pydantic 모델을 연결
VALIDATOR_MAP: dict[str, type[BaseModel]] = {
    "open_meteo": WeatherResponse,
    "countries_dev": CountryResponse,
    "ip_api": IpResponse,
}


def validate_responses(
    raw_data: dict[str, dict[str, Any]],
) -> tuple[dict[str, BaseModel], list[dict[str, str]]]:
    """수집된 JSON을 Pydantic v2 모델로 검증한다."""

    validated: dict[str, BaseModel] = {}

    errors: list[dict[str, str]] = []

    print()
    print("=" * 62)
    print("Pydantic 스키마 검증 결과")
    print("=" * 62)

    for source, model_class in VALIDATOR_MAP.items():
        data = raw_data.get(source)

        if data is None:
            print(f"[검증 제외] {source}: 수집된 데이터가 없습니다.")

            errors.append(
                {
                    "source": source,
                    "stage": "validation",
                    "error": "수집된 데이터가 없습니다.",
                }
            )
            continue

        try:
            # Pydantic v2 방식으로 API 응답을 검증
            validated[source] = model_class.model_validate(data)
            print(f"[검증 통과] {source}")

        except ValidationError as error:
            print(f"[검증 실패] {source}")
            print(error)

            errors.append(
                {
                    "source": source,
                    "stage": "validation",
                    "error": str(error),
                }
            )

    print("-" * 62)
    print(f"검증 통과 API: {len(validated)}/3개")

    return validated, errors


def build_dataframe(
    weather: WeatherResponse,
    country: CountryResponse,
    ip_info: IpResponse,
) -> pd.DataFrame:
    """검증된 API 데이터를 하나의 DataFrame으로 정리한다."""

    rows: list[dict[str, Any]] = []

    # Open-Meteo의 3일 시간대별 데이터를 한 행씩 추가
    for timestamp, temperature, precipitation in zip(
        weather.hourly.time,
        weather.hourly.temperature_2m,
        weather.hourly.precipitation_probability,
        strict=True,
    ):
        rows.append(
            {
                "source": "Open-Meteo",
                "record_type": "hourly_weather",
                "timestamp": timestamp,
                "temperature_2m": temperature,
                "precipitation_probability": precipitation,
                "name": "Seoul",
                "country_code": "KR",
                "capital": None,
                "population": None,
                "ip_address": None,
                "region": None,
                "city": None,
                "latitude": weather.latitude,
                "longitude": weather.longitude,
                "timezone": weather.timezone,
            }
        )

    # Countries.dev에서 받은 대한민국 정보를 추가
    rows.append(
        {
            "source": "Countries.dev",
            "record_type": "country",
            "timestamp": None,
            "temperature_2m": None,
            "precipitation_probability": None,
            "name": country.name,
            "country_code": country.alpha3Code,
            "capital": country.capital,
            "population": country.population,
            "ip_address": None,
            "region": country.region,
            "city": None,
            "latitude": country.latlng[0],
            "longitude": country.latlng[1],
            "timezone": None,
        }
    )

    # ip-api에서 받은 IP 지역 정보를 추가
    rows.append(
        {
            "source": "ip-api",
            "record_type": "ip_location",
            "timestamp": None,
            "temperature_2m": None,
            "precipitation_probability": None,
            "name": ip_info.country,
            "country_code": ip_info.countryCode,
            "capital": None,
            "population": None,
            "ip_address": str(ip_info.query),
            "region": ip_info.regionName,
            "city": ip_info.city,
            "latitude": ip_info.lat,
            "longitude": ip_info.lon,
            "timezone": ip_info.timezone,
        }
    )

    return pd.DataFrame(rows)


def save_error_report(errors: list[dict[str, str]]) -> None:
    """수집 또는 검증 오류를 JSON 파일로 저장한다."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with ERROR_PATH.open("w", encoding="utf-8") as file:
        json.dump(
            errors,
            file,
            ensure_ascii=False,
            indent=2,
        )


def save_and_compare(
    dataframe: pd.DataFrame,
) -> list[dict[str, float | int | str]]:
    """CSV와 Parquet의 쓰기·읽기 시간 및 크기를 비교"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    performance: list[dict[str, float | int | str]] = []

    # CSV 쓰기 시간을 측정한다.
    start = time.perf_counter()
    dataframe.to_csv(
        CSV_PATH,
        index=False,
        encoding="utf-8-sig",
    )
    csv_write_time = time.perf_counter() - start

    # CSV 읽기 시간을 측정
    start = time.perf_counter()
    csv_reloaded = pd.read_csv(CSV_PATH)
    csv_read_time = time.perf_counter() - start

    performance.append(
        {
            "format": "CSV",
            "write_ms": csv_write_time * 1000,
            "read_ms": csv_read_time * 1000,
            "size_bytes": CSV_PATH.stat().st_size,
        }
    )

    # Parquet 쓰기 시간을 측정
    start = time.perf_counter()
    dataframe.to_parquet(
        PARQUET_PATH,
        index=False,
    )
    parquet_write_time = time.perf_counter() - start

    # Parquet 읽기 시간을 측정
    start = time.perf_counter()
    parquet_reloaded = pd.read_parquet(PARQUET_PATH)
    parquet_read_time = time.perf_counter() - start

    performance.append(
        {
            "format": "Parquet",
            "write_ms": parquet_write_time * 1000,
            "read_ms": parquet_read_time * 1000,
            "size_bytes": PARQUET_PATH.stat().st_size,
        }
    )

    # 저장 후 다시 읽었을 때 행 개수가 같은지 확인
    assert len(csv_reloaded) == len(dataframe)
    assert len(parquet_reloaded) == len(dataframe)

    return performance


def print_performance(
    performance: list[dict[str, float | int | str]],
) -> None:
    """저장 형식별 성능 비교 결과를 표로 출력"""

    print()
    print("=" * 62)
    print("CSV · Parquet 저장 성능 비교")
    print("=" * 62)
    print(f"{'형식':<10}{'쓰기(ms)':>14}{'읽기(ms)':>14}{'크기(bytes)':>16}")
    print("-" * 62)

    for result in performance:
        print(
            f"{str(result['format']):<10}"
            f"{float(result['write_ms']):>14.3f}"
            f"{float(result['read_ms']):>14.3f}"
            f"{int(result['size_bytes']):>16,}"
        )


async def run() -> dict[str, int]:
    """수집 → 검증 → 저장 과정을 순서대로 실행"""

    # Extract: API 3개를 비동기로 수집
    raw_data, collection_errors = await collect_all_apis()

    # Transform: Pydantic으로 응답 스키마를 검증
    validated, validation_errors = validate_responses(raw_data)

    all_errors = collection_errors + validation_errors
    save_error_report(all_errors)

    # API 3개가 모두 정상이어야 다음 저장 단계로 진행
    if collection_errors or validation_errors:
        raise RuntimeError(
            "API 수집 또는 스키마 검증에 실패했습니다. "
            "output/validation_errors.json을 확인해주세요."
        )

    weather = validated["open_meteo"]
    country = validated["countries_dev"]
    ip_info = validated["ip_api"]

    # 연결된 모델이 정확한지 한 번 더 확인
    if not isinstance(weather, WeatherResponse):
        raise RuntimeError("Open-Meteo 모델 연결이 올바르지 않습니다.")

    if not isinstance(country, CountryResponse):
        raise RuntimeError("Countries.dev 모델 연결이 올바르지 않습니다.")

    if not isinstance(ip_info, IpResponse):
        raise RuntimeError("ip-api 모델 연결이 올바르지 않습니다.")

    # 검증된 데이터를 저장하기 좋은 표 형태로 바꿈
    dataframe = build_dataframe(
        weather,
        country,
        ip_info,
    )

    # Load: CSV와 Parquet으로 저장하고 성능을 비교
    performance = save_and_compare(dataframe)
    print_performance(performance)

    print()
    print("=" * 62)
    print("Day1 API 비동기 파이프라인 최종 결과")
    print("=" * 62)
    print(f"API 정상 수집 : {len(raw_data)}/3개")
    print(f"스키마 검증   : {len(validated)}/3개")
    print(f"저장 행 수    : {len(dataframe)}건")
    print(f"CSV 파일      : {CSV_PATH}")
    print(f"Parquet 파일  : {PARQUET_PATH}")
    print(f"오류 기록     : {ERROR_PATH}")

    return {
        "collected": len(raw_data),
        "validated": len(validated),
        "rows_saved": len(dataframe),
        "errors": len(all_errors),
    }


if __name__ == "__main__":
    try:
        asyncio.run(run())

    except RuntimeError as error:
        print()
        print(f"[실행 실패] {error}")
        raise SystemExit(1) from error
