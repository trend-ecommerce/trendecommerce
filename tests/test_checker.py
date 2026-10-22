import pytest
from src.guardian.checker import RequestChecker
from src.guardian.whitelist import APIWhitelist


class TestRequestChecker:
    """Testes do checker de requisições."""

    def setup_method(self):
        self.checker = RequestChecker()

    def test_guarded_call_detection(self, temp_python_file):
        """Detecta chamadas HTTP protegidas."""
        content = '''import requests
response = requests.get("https://api.exemplo.com/dados")
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) > 0
        assert any(not r.is_allowed for r in results)

    def test_allowed_amazon_call(self, temp_python_file):
        """Verifica que chamada autorizada da Amazon é permitida."""
        content = '''import requests
response = requests.get("https://sellingpartnerapi-na.amazon.com/catalog/2022-04-01/items")
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) > 0
        assert all(r.is_allowed for r in results)

    def test_allowed_mercadolivre_call(self, temp_python_file):
        """Verifica que chamada do Mercado Livre é permitida."""
        content = '''import requests
response = requests.get("https://api.mercadolibre.com/sites/MLB/search")
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) > 0
        assert all(r.is_allowed for r in results)

    def test_blocked_unknown_api(self, temp_python_file):
        """Verifica bloqueio de API desconhecida."""
        content = '''import requests
response = requests.get("https://api.desconhecida.com/data")
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) > 0
        assert any(not r.is_allowed for r in results)

    def test_detects_httpx_calls(self, temp_python_file):
        """Detecta chamadas via httpx."""
        content = '''import httpx
response = httpx.get("https://api.exemplo.com/dados")
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) > 0

    def test_no_calls_in_clean_file(self, temp_python_file):
        """Não detecta chamadas em arquivo sem HTTP."""
        content = '''x = 1
y = 2
print(x + y)
'''
        file_path = temp_python_file(content)
        results = self.checker.check_file(file_path)
        assert len(results) == 0