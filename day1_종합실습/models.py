"""Day1 종합실습

주제 : Open-Meteo, Countries.dev, ip-api에서 받은 JSON 데이터의 필요한 필드와 값의 범위를 검증한다.

작성자: 성가연
작성일: 2026-07-20
"""

from __future__ import annotations
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    model_validator,
)

# 강수확률은 반드시 0에서 100 사이의 정수
Probability = Annotated[int, Field(ge=0, le=100)]


class ApiBaseModel(BaseModel):
    """API 검증 모델에서 공통으로 사용할 설정."""

    # 필요한 필드만 검증하고 API가 추가로 주는 필드는 무시
    # 문자열 앞뒤에 불필요한 공백이 있으면 자동으로 제거
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )


class WeatherHourly(ApiBaseModel):
    """Open-Meteo의 시간대별 날씨 데이터."""

    # API가 보내주는 문자열 시간을 datetime으로 자동 변환
    time: list[datetime] = Field(min_length=1)

    # 서울의 3일 시간대별 기온
    temperature_2m: list[float] = Field(min_length=1)

    # 강수확률은 각 값이 0에서 100 사이인지 확인
    precipitation_probability: list[Probability] = Field(min_length=1)

    @model_validator(mode="after")
    def check_list_lengths(self) -> WeatherHourly:
        """시간, 기온, 강수확률의 데이터 개수가 같은지 확인한다."""

        time_count = len(self.time)
        temperature_count = len(self.temperature_2m)
        precipitation_count = len(self.precipitation_probability)

        if not (time_count == temperature_count == precipitation_count):
            raise ValueError("시간, 기온, 강수확률의 데이터 개수가 같아야 합니다")

        return self


class WeatherResponse(ApiBaseModel):
    """Open-Meteo API 응답 검증 모델."""

    # 위도와 경도의 실제 범위를 검사
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    # 요청한 시간대가 반환됐는지 확인
    timezone: str = Field(min_length=1)

    # 모델 안에 또 다른 모델을 넣어 중첩 JSON을 검증
    hourly: WeatherHourly


class CountryResponse(ApiBaseModel):
    """Countries.dev의 대한민국 국가 정보 검증 모델."""

    name: str = Field(min_length=1)

    # 국가 코드는 영문 대문자 2자리와 3자리인지 검사
    alpha2Code: str = Field(pattern=r"^[A-Z]{2}$")
    alpha3Code: str = Field(pattern=r"^[A-Z]{3}$")

    capital: str = Field(min_length=1)
    region: str = Field(min_length=1)

    # 인구는 음수가 될 수 없음
    population: int = Field(ge=0)

    # 위도와 경도 두 개의 값이 있어야 함
    latlng: list[float] = Field(
        min_length=2,
        max_length=2,
    )


class IpResponse(ApiBaseModel):
    """ip-api의 IP 기반 지역 정보 검증 모델"""

    # 정상 응답일 때 status 값은 success여야 함
    status: Literal["success"]

    # 문자열이 실제 IP 주소 형식인지 검사
    query: IPvAnyAddress

    country: str = Field(min_length=1)
    countryCode: str = Field(pattern=r"^[A-Z]{2}$")
    regionName: str = Field(min_length=1)
    city: str = Field(min_length=1)

    # IP 위치의 위도와 경도 범위를 검사
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    timezone: str = Field(min_length=1)
