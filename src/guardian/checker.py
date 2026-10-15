"""Checker de requisições HTTP.

Monitora chamadas feitas através de bibliotecas HTTP (requests, httpx,
aiohttp, urllib) e verifica se estão em conformidade com a whitelist.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .whitelist import APIWhitelist


@dataclass
class HTTPCallInfo:
    """Informações sobre uma chamada HTTP detectada."""
    file_path: str
    line_number: int
    library: str  # requests, httpx, aiohttp, urllib
    method: str   # GET, POST, PUT, DELETE
    url: str
    is_dynamic_url: bool = False


@dataclass  
class CheckResult:
    """Resultado da verificação de uma chamada HTTP."""
    call_info: HTTPCallInfo
    is_allowed: bool
    reason: str


class RequestChecker:
    """Verifica chamadas HTTP no código-fonte.
    
    Analisa arquivos Python para detectar requisições HTTP
    e verificar se estão na whitelist do API Guardian.
    """

    # Mapeamento de funções de bibliotecas HTTP
    HTTP_LIBRARIES = {
        "requests": {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "delete": "DELETE",
            "patch": "PATCH",
            "head": "HEAD",
            "options": "OPTIONS",
        },
        "httpx": {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "delete": "DELETE",
            "patch": "PATCH",
            "head": "HEAD",
            "options": "OPTIONS",
        },
        "aiohttp": {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "delete": "DELETE",
            "patch": "PATCH",
        },
        "urllib": {
            "urlopen": "GET",
            "Request": "GET",
        },
    }

    def __init__(self, whitelist: Optional[APIWhitelist] = None):
        self.whitelist = whitelist or APIWhitelist()

    def check_file(self, file_path: str) -> list[CheckResult]:
        """Verifica todas as chamadas HTTP em um arquivo.
        
        Args:
            file_path: Caminho do arquivo Python
            
        Returns:
            Lista de resultados da verificação
        """
        calls = self.detect_http_calls(file_path)
        results = []
        
        for call in calls:
            if call.is_dynamic_url:
                results.append(CheckResult(
                    call_info=call,
                    is_allowed=False,
                    reason="URL dinâmica detectada - não é possível verificar na whitelist. Revisão manual necessária."
                ))
            elif self.whitelist.is_allowed(call.url, call.method):
                results.append(CheckResult(
                    call_info=call,
                    is_allowed=True,
                    reason=f"Endpoint autorizado na whitelist"
                ))
            else:
                results.append(CheckResult(
                    call_info=call,
                    is_allowed=False,
                    reason=f"BLOQUEADO: endpoint '{call.url}' não está na whitelist"
                ))
        
        return results

    def check_directory(self, directory: str) -> list[CheckResult]:
        """Verifica todas as chamadas HTTP em um diretório."""
        results = []
        path = Path(directory)
        
        for py_file in path.rglob("*.py"):
            results.extend(self.check_file(str(py_file)))
        
        return results

    def detect_http_calls(self, file_path: str) -> list[HTTPCallInfo]:
        """Detecta chamadas HTTP em um arquivo Python."""
        calls = []
        path = Path(file_path)
        
        if not path.exists() or path.suffix != ".py":
            return calls
        
        content = path.read_text(encoding="utf-8")
        
        # Análise via AST
        calls.extend(self._detect_via_ast(content, file_path))
        
        # Análise via regex (complementar)
        calls.extend(self._detect_via_regex(content, file_path))
        
        # Remover duplicatas por linha
        seen = set()
        unique = []
        for c in calls:
            key = (c.file_path, c.line_number)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        
        return unique

    def _detect_via_ast(self, content: str, file_path: str) -> list[HTTPCallInfo]:
        """Detecta chamadas HTTP via análise AST."""
        calls = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return calls
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_info = self._analyze_call_node(node, file_path)
                if call_info:
                    calls.append(call_info)
        
        return calls

    def _analyze_call_node(self, node: ast.Call, file_path: str) -> Optional[HTTPCallInfo]:
        """Analisa um nó de chamada do AST."""
        # Padrão: requests.get("url")
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                lib_name = node.func.value.id
                method_name = node.func.attr
                
                if lib_name in self.HTTP_LIBRARIES:
                    methods = self.HTTP_LIBRARIES[lib_name]
                    if method_name in methods:
                        url, is_dynamic = self._extract_url(node)
                        return HTTPCallInfo(
                            file_path=file_path,
                            line_number=node.lineno,
                            library=lib_name,
                            method=methods[method_name],
                            url=url,
                            is_dynamic_url=is_dynamic
                        )
        
        return None

    def _extract_url(self, node: ast.Call) -> tuple[str, bool]:
        """Extrai a URL de um nó de chamada."""
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                return first_arg.value, False
            elif isinstance(first_arg, ast.JoinedStr):  # f-string
                return "<f-string dinâmica>", True
            elif isinstance(first_arg, ast.Name):
                return f"<variável: {first_arg.id}>", True
        return "<URL não detectada>", True

    def _detect_via_regex(self, content: str, file_path: str) -> list[HTTPCallInfo]:
        """Detecta chamadas HTTP via regex."""
        calls = []
        lines = content.split("\n")
        
        patterns = [
            (r'requests\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']",', "requests"),
            (r'httpx\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']*)["\']",', "httpx"),
        ]
        
        for line_num, line in enumerate(lines, 1):
            for pattern, lib in patterns:
                match = re.search(pattern, line)
                if match:
                    method = match.group(1).upper()
                    url = match.group(2)
                    calls.append(HTTPCallInfo(
                        file_path=file_path,
                        line_number=line_num,
                        library=lib,
                        method=method,
                        url=url,
                        is_dynamic_url=False
                    ))
        
        return calls
