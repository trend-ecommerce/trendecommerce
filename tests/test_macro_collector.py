import pytest
from src.collectors.macro_collector import MacroCollector


def test_macro_collector_initialization():
    collector = MacroCollector()
    assert collector.name == "macro_collector"
    assert collector.is_authenticated is True


def test_macro_collector_brasilapi_holidays():
    collector = MacroCollector()
    holidays = collector.fetch_holidays_brasilapi(2026)
    assert isinstance(holidays, list)
    assert len(holidays) >= 5
    assert any("Independência" in h["name"] or "Natal" in h["name"] for h in holidays)


def test_macro_collector_bcb_series():
    collector = MacroCollector()
    dolar = collector.fetch_bcb_series(10813, last_n=10)
    assert isinstance(dolar, list)
    assert len(dolar) == 10
    assert dolar[0]["value"] > 0


def test_macro_collector_unfied_collect():
    collector = MacroCollector()
    result = collector.collect(days=15)
    assert result.success is True
    assert len(result.data) == 1
    payload = result.data[0]
    assert "holidays" in payload
    assert "dolar_ptax" in payload
    assert "coingecko" in payload