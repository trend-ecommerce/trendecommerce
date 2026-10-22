import pytest
from src.guardian.policy_engine import PolicyEngine, PolicyAction


class TestPolicyEngine:
    """Testes do motor de políticas."""

    def setup_method(self):
        self.engine = PolicyEngine(strict_mode=True)

    def test_allows_compliant_file(self, temp_python_file):
        """Permite arquivo em conformidade."""
        content = '''import os
import requests

api_key = os.getenv("API_KEY")
response = requests.get("https://api.mercadolibre.com/sites/MLB/search")
'''
        file_path = temp_python_file(content)
        result = self.engine.evaluate_file(file_path)
        assert result.is_allowed

    def test_blocks_unauthorized_api(self, temp_python_file):
        """Bloqueia API não autorizada."""
        content = '''import requests
response = requests.get("https://api.naoautorizada.com/dados")
'''
        file_path = temp_python_file(content)
        result = self.engine.evaluate_file(file_path)
        assert result.is_blocked

    def test_blocks_hardcoded_credentials(self, temp_python_file):
        """Bloqueia credenciais hardcoded."""
        content = '''API_KEY = "sk-1234567890"
'''
        file_path = temp_python_file(content)
        result = self.engine.evaluate_file(file_path)
        assert result.is_blocked

    def test_warns_in_non_strict_mode(self, temp_python_file):
        """Emite aviso em modo não-estrito."""
        engine = PolicyEngine(strict_mode=False)
        content = '''import requests
response = requests.get("https://api.naoautorizada.com/dados")
'''
        file_path = temp_python_file(content)
        result = engine.evaluate_file(file_path)
        assert result.action == PolicyAction.WARN

    def test_check_url_allowed(self):
        """Verifica URL permitida."""
        result = self.engine.check_url(
            "https://api.mercadolibre.com/sites/MLB/search"
        )
        assert result.is_allowed

    def test_check_url_blocked(self):
        """Verifica URL bloqueada."""
        result = self.engine.check_url("https://api.exemplo.com/dados")
        assert result.is_blocked

    def test_empty_file_allowed(self, temp_python_file):
        """Arquivo vazio é permitido."""
        file_path = temp_python_file("")
        result = self.engine.evaluate_file(file_path)
        assert result.is_allowed
