import pytest
from src.guardian.credential_scanner import CredentialScanner


class TestCredentialScanner:
    """Testes de detecção de credenciais hardcoded."""

    def setup_method(self):
        self.scanner = CredentialScanner()

    def test_detects_hardcoded_api_key(self, temp_python_file):
        """Detecta API_KEY hardcoded."""
        content = 'API_KEY = "sk-1234567890abcdef"'
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) > 0
        assert any("API_KEY" in f.variable_name for f in findings)

    def test_detects_client_secret(self, temp_python_file):
        """Detecta client_secret hardcoded."""
        content = 'client_secret = "minha-chave-secreta"'
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) > 0

    def test_detects_password(self, temp_python_file):
        """Detecta password hardcoded."""
        content = 'password = "senha_super_secreta_123"'
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) > 0

    def test_ignores_env_variable_usage(self, temp_python_file):
        """Não detecta uso de variáveis de ambiente."""
        content = '''import os
api_key = os.getenv("API_KEY")
'''
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) == 0

    def test_ignores_comments(self, temp_python_file):
        """Ignora credenciais em comentários."""
        content = '# API_KEY = "sk-12345"\nx = 1'
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) == 0

    def test_detects_multiple_credentials(self, temp_python_file):
        """Detecta múltiplas credenciais."""
        content = '''API_KEY = "key-123"
client_secret = "secret-456"
password = "pass-789"
'''
        file_path = temp_python_file(content)
        findings = self.scanner.scan_file(file_path)
        assert len(findings) >= 3

    def test_scan_nonexistent_file(self):
        """Retorna vazio para arquivo inexistente."""
        findings = self.scanner.scan_file("/nonexistent/file.py")
        assert len(findings) == 0

    def test_scan_non_python_file(self, tmp_path):
        """Retorna vazio para arquivo não-Python."""
        file_path = tmp_path / "data.txt"
        file_path.write_text('API_KEY = "test"')
        findings = self.scanner.scan_file(str(file_path))
        assert len(findings) == 0