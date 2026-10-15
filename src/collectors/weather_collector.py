"""Coletor de Dados Climáticos e Sazonalidade de Temperatura.

Integra OpenWeatherMap / WeatherAPI com gerador de contexto climático
para identificar picos térmicos que influenciam categorias sazonais.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional
import requests

from .base_collector import BaseCollector, CollectorResult

logger = logging.getLogger(__name__)


class WeatherCollector(BaseCollector):
    """Coletor para dados meteorológicos e histórico térmico."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 5):
        super().__init__(name="weather_collector")
        self.api_key = api_key or os.getenv("OPENWEATHER_API_KEY")
        self.timeout = timeout
        self._is_authenticated = True

    def authenticate(self) -> bool:
        return True

    def validate_response(self, response: Any) -> bool:
        return isinstance(response, (list, dict))

    def fetch_current_temperature(self, city: str = "Sao Paulo,BR") -> dict[str, Any]:
        """Consulta clima atual para a região de referência."""
        if self.api_key:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"
            try:
                resp = requests.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    temp = data.get("main", {}).get("temp", 24.0)
                    humidity = data.get("main", {}).get("humidity", 65)
                    return {
                        "city": city,
                        "temperature": float(temp),
                        "humidity": float(humidity),
                        "source": "openweathermap"
                    }
            except Exception as e:
                logger.debug(f"Erro OpenWeatherMap: {e}")

        # Fallback de climatologia média do Sudeste/Brasil
        month = datetime.now().month
        base_temp = 27.0 if month in [12, 1, 2, 3] else (20.0 if month in [6, 7, 8] else 24.0)
        return {
            "city": city,
            "temperature": base_temp,
            "humidity": 68.0,
            "source": "climatology_fallback"
        }

    def collect(self, **kwargs) -> CollectorResult:
        data = self.fetch_current_temperature()
        return self._create_success_result([data])
