import pytest
from src.collectors.base_collector import CollectorResult
from src.collectors.google_trends_collector import GoogleTrendsCollector


class TestCollectorResult:
    """Testes do resultado de coleta."""

    def test_success_result(self):
        result = CollectorResult(
            source="test",
            data=[{"id": 1}, {"id": 2}],
            success=True,
        )
        assert result.records_count == 2
        assert result.success is True

    def test_error_result(self):
        result = CollectorResult(
            source="test",
            data=[],
            success=False,
            error_message="Connection error",
        )
        assert result.records_count == 0
        assert result.success is False


class TestGoogleTrendsCollector:
    """Testes do coletor Google Trends (dados simulados)."""

    def setup_method(self):
        self.collector = GoogleTrendsCollector()
        self.collector.authenticate()

    def test_authenticate(self):
        assert self.collector.is_authenticated is True

    def test_collect_mock_data(self):
        result = self.collector.collect(
            use_mock=True,
            keywords=["notebook"],
            start_date="2026-08-01",
            end_date="2026-08-10",
        )
        assert result.success is True
        assert result.records_count > 0

    def test_collect_without_source(self):
        result = self.collector.collect(use_mock=False)
        assert result.success is False