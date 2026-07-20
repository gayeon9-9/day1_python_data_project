"""Day1 API 비동기 파이프라인 자동 테스트

실제 API를 호출하지 않고 샘플 데이터로 Pydantic 검증 규칙과 DataFrame 변환 기능을 확인

작성자: 성가연
작성일: 2026-07-20
"""

from copy import deepcopy
import pytest
from pydantic import ValidationError
from models import CountryResponse, IpResponse, WeatherResponse
from pipeline import build_dataframe


# 정상적인 Open-Meteo 응답 샘플
VALID_WEATHER = {
    "latitude": 37.5665,
    "longitude": 126.9780,
    "timezone": "Asia/Seoul",
    "hourly": {
        "time": [
            "2026-07-20T00:00",
            "2026-07-20T01:00",
        ],
        "temperature_2m": [
            25.1,
            24.8,
        ],
        "precipitation_probability": [
            10,
            20,
        ],
    },
}


# 정상적인 Countries.dev 응답 샘플
VALID_COUNTRY = {
    "name": "Korea (Republic of)",
    "alpha2Code": "KR",
    "alpha3Code": "KOR",
    "capital": "Seoul",
    "region": "Asia",
    "population": 51780579,
    "latlng": [
        37.0,
        127.5,
    ],
}


# 정상적인 ip-api 응답 샘플
VALID_IP = {
    "status": "success",
    "query": "8.8.8.8",
    "country": "United States",
    "countryCode": "US",
    "regionName": "Virginia",
    "city": "Ashburn",
    "lat": 39.03,
    "lon": -77.5,
    "timezone": "America/New_York",
}


def test_weather_response_is_valid():
    """정상 날씨 데이터가 검증을 통과하는지 확인한다."""

    weather = WeatherResponse.model_validate(VALID_WEATHER)

    assert weather.timezone == "Asia/Seoul"
    assert len(weather.hourly.time) == 2


def test_invalid_precipitation_probability_is_rejected():
    """100을 초과한 강수확률이 거부되는지 확인한다."""

    invalid_data = deepcopy(VALID_WEATHER)
    invalid_data["hourly"]["precipitation_probability"][0] = 150

    with pytest.raises(ValidationError):
        WeatherResponse.model_validate(invalid_data)


def test_different_weather_list_lengths_are_rejected():
    """시간·기온·강수확률 개수가 다르면 거부되는지 확인한다."""

    invalid_data = deepcopy(VALID_WEATHER)
    invalid_data["hourly"]["temperature_2m"] = [25.1]

    with pytest.raises(ValidationError):
        WeatherResponse.model_validate(invalid_data)


def test_negative_population_is_rejected():
    """음수 인구가 거부되는지 확인한다."""

    invalid_data = deepcopy(VALID_COUNTRY)
    invalid_data["population"] = -1

    with pytest.raises(ValidationError):
        CountryResponse.model_validate(invalid_data)


def test_failed_ip_response_is_rejected():
    """ip-api의 실패 응답이 거부되는지 확인한다."""

    invalid_data = deepcopy(VALID_IP)
    invalid_data["status"] = "fail"

    with pytest.raises(ValidationError):
        IpResponse.model_validate(invalid_data)


def test_build_dataframe_row_count():
    """검증된 API 데이터가 필요한 행 수로 변환되는지 확인한다."""

    weather = WeatherResponse.model_validate(VALID_WEATHER)
    country = CountryResponse.model_validate(VALID_COUNTRY)
    ip_info = IpResponse.model_validate(VALID_IP)

    dataframe = build_dataframe(
        weather,
        country,
        ip_info,
    )

    # 날씨 2행 + 국가 1행 + IP 1행
    assert len(dataframe) == 4

    # 세 API 데이터가 모두 포함됐는지 확인
    assert set(dataframe["source"]) == {
        "Open-Meteo",
        "Countries.dev",
        "ip-api",
    }


def test_invalid_temperature_type_is_rejected():
    """숫자가 아닌 기온 데이터가 거부되는지 확인한다."""

    invalid_data = deepcopy(VALID_WEATHER)
    invalid_data["hourly"]["temperature_2m"][0] = "숫자아님"

    with pytest.raises(ValidationError):
        WeatherResponse.model_validate(invalid_data)