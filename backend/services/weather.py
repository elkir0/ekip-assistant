import asyncio
import logging
from datetime import datetime
from typing import Any

import requests

from config import WEATHER_LAT, WEATHER_LON, WEATHER_CITY

logger = logging.getLogger(__name__)

# Open-Meteo — 100% gratuit, pas de clé API
BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> descriptions FR + icon keys
WMO_CODES = {
    0: ("ensoleille", "01d"),
    1: ("peu nuageux", "02d"),
    2: ("partiellement nuageux", "03d"),
    3: ("couvert", "04d"),
    45: ("brouillard", "50d"),
    48: ("brouillard givrant", "50d"),
    51: ("bruine legere", "09d"),
    53: ("bruine", "09d"),
    55: ("bruine forte", "09d"),
    61: ("pluie legere", "10d"),
    63: ("pluie", "10d"),
    65: ("forte pluie", "10d"),
    71: ("neige legere", "13d"),
    73: ("neige", "13d"),
    75: ("forte neige", "13d"),
    80: ("averses legeres", "09d"),
    81: ("averses", "09d"),
    82: ("fortes averses", "09d"),
    95: ("orage", "11d"),
    96: ("orage avec grele", "11d"),
    99: ("orage violent", "11d"),
}


class WeatherService:
    def __init__(self):
        self._cache: dict | None = None

    async def get_current(self) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, self._fetch)

            current = data["current"]
            daily = data["daily"]

            wmo = current.get("weather_code", 0)
            condition, icon = WMO_CODES.get(wmo, ("inconnu", "01d"))

            # Check if it's night
            hour = datetime.now().hour
            if hour < 6 or hour > 20:
                icon = icon.replace("d", "n")

            result = {
                "loaded": True,
                "city": WEATHER_CITY,
                "temp": round(current["temperature_2m"]),
                "feels_like": round(current["apparent_temperature"]),
                "humidity": round(current["relative_humidity_2m"]),
                "wind": round(current["wind_speed_10m"]),
                "condition": condition,
                "icon": icon,
                "forecast": self._parse_forecast(daily),
            }
            self._cache = result
            logger.info("[METEO] %s: %d°C, %s", WEATHER_CITY, result["temp"], condition)
            return result

        except Exception as e:
            logger.error("[METEO] Erreur: %s", e)
            if self._cache:
                return self._cache
            return self._mock_data()

    def _fetch(self) -> dict:
        resp = requests.get(
            BASE_URL,
            params={
                "latitude": WEATHER_LAT,
                "longitude": WEATHER_LON,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "timezone": "America/Guadeloupe",
                "forecast_days": 4,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def _parse_forecast(self, daily: dict) -> list[dict]:
        forecast = []
        # Skip today (index 0), take next 3 days
        for i in range(1, min(4, len(daily.get("time", [])))):
            date = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            wmo = daily["weather_code"][i]
            condition, icon = WMO_CODES.get(wmo, ("inconnu", "01d"))

            forecast.append({
                "day": date.strftime("%a"),
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
                "icon": icon,
                "condition": condition,
            })

        return forecast

    def format_spoken(self, data: dict) -> str:
        if not data.get("loaded"):
            return "Je n'ai pas pu recuperer la meteo."

        text = (
            f"A {data['city']}, il fait {data['temp']} degres, "
            f"{data['condition']}. "
            f"Humidite {data['humidity']}%, "
            f"vent {data['wind']} kilometres heure."
        )

        if data.get("forecast"):
            f = data["forecast"][0]
            text += f" Demain, entre {f['low']} et {f['high']} degres, {f['condition']}."

        return text

    def _mock_data(self) -> dict:
        return {
            "loaded": False,
            "city": WEATHER_CITY,
            "temp": 28,
            "feels_like": 32,
            "humidity": 75,
            "wind": 15,
            "condition": "partiellement nuageux",
            "icon": "02d",
            "forecast": [
                {"day": "Lun", "high": 30, "low": 24, "icon": "02d", "condition": "nuageux"},
                {"day": "Mar", "high": 29, "low": 23, "icon": "10d", "condition": "pluie legere"},
                {"day": "Mer", "high": 31, "low": 25, "icon": "01d", "condition": "ensoleille"},
            ],
        }
