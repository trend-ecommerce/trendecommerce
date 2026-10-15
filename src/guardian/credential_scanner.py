"""Scanner de credenciais hardcoded no código-fonte.

Identifica padrões de credenciais expostas diretamente no código,
como API keys, secrets, tokens e senhas.
"""

import re
import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CredentialFinding:
    """Representa uma credencial encontrada no código."""
    file_path: str
    line_number: int
    variable_name: str
    pattern_matched: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    message: str


class CredentialScanner:
    """Scanner para detectar credenciais hardcoded.
    
    Analisa código Python em busca de padrões que indiquem
    credenciais expostas diretamente no código-fonte.
    """

    # Padrões de nomes de variáveis suspeitas
    SUSPICIOUS_PATTERNS = [
        r"(?i)(api[_-]?key)",
        r"(?i)(api[_-]?secret)",
        r"(?i)(client[_-]?id)",
        r"(?i)(client[_-]?secret)",
        r"(?i)(access[_-]?token)",
        r"(?i)(refresh[_-]?token)",
        r"(?i)(secret[_-]?key)",
        r"(?i)(private[_-]?key)",
        r"(?i)(password)",
        r"(?i)(passwd)",
        r"(?i)(auth[_-]?token)",
        r"(?i)(bearer[_-]?token)",
        r"(?i)(aws[_-]?key)",
        r"(?i)(database[_-]?url)",
        r"(?i)(db[_-]?password)",
    ]

    def __init__(self):
        self._findings: list[CredentialFinding] = []

    def scan_file(self, file_path: str) -> list[CredentialFinding]:
        """Escaneia um arquivo Python em busca de credenciais hardcoded.
        
        Args:
            file_path: Caminho do arquivo a ser escaneado
            
        Returns:
            Lista de credenciais encontradas
        """
        findings = []
        path = Path(file_path)
        
        if not path.exists() or not path.suffix == ".py":
            return findings
        
        content = path.read_text(encoding="utf-8")
        
        # Análise via AST
        findings.extend(self._scan_ast(content, file_path))
        
        # Análise via regex (backup)
        findings.extend(self._scan_regex(content, file_path))
        
        # Remover duplicatas
        seen = set()
        unique_findings = []
        for f in findings:
            key = (f.file_path, f.line_number, f.variable_name)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)
        
        self._findings.extend(unique_findings)
        return unique_findings

    def scan_directory(self, directory: str) -> list[CredentialFinding]:
        """Escaneia um diretório recursivamente."""
        findings = []
        path = Path(directory)
        
        for py_file in path.rglob("*.py"):
            findings.extend(self.scan_file(str(py_file)))
        
        return findings

    def _scan_ast(self, content: str, file_path: str) -> list[CredentialFinding]:
        """Analisa o AST do código buscando atribuições suspeitas."""
        findings = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return findings
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        var_name = target.id
                        if self._is_suspicious_name(var_name):
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                if len(node.value.value) > 0 and not node.value.value.startswith("${"):
                                    findings.append(CredentialFinding(
                                        file_path=file_path,
                                        line_number=node.lineno,
                                        variable_name=var_name,
                                        pattern_matched="AST string assignment",
                                        severity="HIGH",
                                        message=f"Credencial hardcoded detectada: '{var_name}' contém um valor string literal. Use variáveis de ambiente."
                                    ))
        
        return findings

    def _scan_regex(self, content: str, file_path: str) -> list[CredentialFinding]:
        """Analisa via regex buscando padrões suspeitos."""
        findings = []
        lines = content.split("\n")
        
        for line_num, line in enumerate(lines, 1):
            # Ignorar comentários
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            
            # Buscar padrões tipo: VARIABLE = "value"
            match = re.match(r'^\s*(\w+)\s*=\s*["\'](.+)["\']', line)
            if match:
                var_name = match.group(1)
                value = match.group(2)
                
                if self._is_suspicious_name(var_name) and len(value) > 3:
                    # Ignorar placeholders comuns
                    if value not in ("your-key-here", "placeholder", "TODO", "CHANGE_ME", ""):
                        findings.append(CredentialFinding(
                            file_path=file_path,
                            line_number=line_num,
                            variable_name=var_name,
                            pattern_matched="Regex pattern match",
                            severity="MEDIUM",
                            message=f"Possível credencial hardcoded: '{var_name}'. Verifique e use variáveis de ambiente."
                        ))
        
        return findings

    def _is_suspicious_name(self, name: str) -> bool:
        """Verifica se o nome da variável é suspeito."""
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.match(pattern, name):
                return True
        return False

    def get_all_findings(self) -> list[CredentialFinding]:
        """Retorna todas as credenciais encontradas."""
        return list(self._findings)

    def clear_findings(self):
        """Limpa os resultados anteriores."""
        self._findings.clear()
