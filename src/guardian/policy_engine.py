"""Policy Engine do API Guardian.

Motor de políticas que combina verificação de whitelist,
detecção de credenciais e análise de requisições HTTP
para determinar se o código está em conformidade.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime

from .whitelist import APIWhitelist
from .checker import RequestChecker, CheckResult
from .credential_scanner import CredentialScanner, CredentialFinding


class PolicyAction(Enum):
    """Ação determinada pela política."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    WARN = "WARN"


@dataclass
class PolicyResult:
    """Resultado da avaliação de política."""
    action: PolicyAction
    message: str
    details: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def is_allowed(self) -> bool:
        return self.action == PolicyAction.ALLOW

    @property
    def is_blocked(self) -> bool:
        return self.action == PolicyAction.BLOCK


@dataclass
class AuditReport:
    """Relatório completo de auditoria."""
    timestamp: str
    files_scanned: int
    http_calls_found: int
    allowed_calls: int
    blocked_calls: int
    credentials_found: int
    policy_results: list[PolicyResult]
    check_results: list[CheckResult]
    credential_findings: list[CredentialFinding]
    overall_action: PolicyAction


class PolicyEngine:
    """Motor de políticas do API Guardian.
    
    Combina todas as verificações de segurança e conformidade
    para determinar se o código está de acordo com as regras
    definidas para o TrendCommerce AI.
    
    Fluxo:
        REQUISIÇÃO → IDENTIFICAÇÃO → VALIDAÇÃO DA URL →
        VALIDAÇÃO DA API → VALIDAÇÃO DAS CREDENCIAIS →
        VALIDAÇÃO DA POLÍTICA → ALLOW / BLOCK
    """

    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
        self.whitelist = APIWhitelist()
        self.checker = RequestChecker(self.whitelist)
        self.credential_scanner = CredentialScanner()

    def evaluate_file(self, file_path: str) -> PolicyResult:
        """Avalia um arquivo de acordo com as políticas.
        
        Args:
            file_path: Caminho do arquivo Python
            
        Returns:
            Resultado da política
        """
        details = []
        has_violations = False
        
        # 1. Verificar chamadas HTTP
        check_results = self.checker.check_file(file_path)
        blocked_calls = [r for r in check_results if not r.is_allowed]
        
        if blocked_calls:
            has_violations = True
            for result in blocked_calls:
                details.append(
                    f"[BLOCKED] {result.call_info.library}.{result.call_info.method.lower()}() "
                    f"linha {result.call_info.line_number}: {result.reason}"
                )
        
        allowed_calls = [r for r in check_results if r.is_allowed]
        for result in allowed_calls:
            details.append(
                f"[ALLOWED] {result.call_info.library}.{result.call_info.method.lower()}() "
                f"linha {result.call_info.line_number}: {result.reason}"
            )
        
        # 2. Verificar credenciais hardcoded
        credential_findings = self.credential_scanner.scan_file(file_path)
        
        if credential_findings:
            has_violations = True
            for finding in credential_findings:
                details.append(
                    f"[CREDENTIAL] {finding.severity} - linha {finding.line_number}: "
                    f"{finding.message}"
                )
        
        # 3. Determinar ação
        if has_violations:
            if self.strict_mode:
                return PolicyResult(
                    action=PolicyAction.BLOCK,
                    message=f"Violações encontradas em {file_path}",
                    details=details
                )
            else:
                return PolicyResult(
                    action=PolicyAction.WARN,
                    message=f"Avisos encontrados em {file_path}",
                    details=details
                )
        
        return PolicyResult(
            action=PolicyAction.ALLOW,
            message=f"Arquivo {file_path} está em conformidade",
            details=details
        )

    def evaluate_directory(self, directory: str) -> AuditReport:
        """Avalia um diretório completo.
        
        Args:
            directory: Caminho do diretório
            
        Returns:
            Relatório de auditoria completo
        """
        path = Path(directory)
        policy_results = []
        all_check_results = []
        all_credential_findings = []
        files_scanned = 0
        
        for py_file in path.rglob("*.py"):
            files_scanned += 1
            
            # Verificar chamadas HTTP
            check_results = self.checker.check_file(str(py_file))
            all_check_results.extend(check_results)
            
            # Verificar credenciais
            credential_findings = self.credential_scanner.scan_file(str(py_file))
            all_credential_findings.extend(credential_findings)
            
            # Avaliar política
            policy_result = self.evaluate_file(str(py_file))
            policy_results.append(policy_result)
        
        # Determinar ação geral
        has_blocks = any(r.action == PolicyAction.BLOCK for r in policy_results)
        overall_action = PolicyAction.BLOCK if has_blocks else PolicyAction.ALLOW
        
        allowed_count = sum(1 for r in all_check_results if r.is_allowed)
        blocked_count = sum(1 for r in all_check_results if not r.is_allowed)
        
        return AuditReport(
            timestamp=datetime.now().isoformat(),
            files_scanned=files_scanned,
            http_calls_found=len(all_check_results),
            allowed_calls=allowed_count,
            blocked_calls=blocked_count,
            credentials_found=len(all_credential_findings),
            policy_results=policy_results,
            check_results=all_check_results,
            credential_findings=all_credential_findings,
            overall_action=overall_action
        )

    def check_url(self, url: str, method: str = "GET") -> PolicyResult:
        """Verifica rapidamente se uma URL é permitida."""
        if self.whitelist.is_allowed(url, method):
            endpoint = self.whitelist.get_endpoint_info(url)
            return PolicyResult(
                action=PolicyAction.ALLOW,
                message=f"URL autorizada: {endpoint.name if endpoint else url}"
            )
        return PolicyResult(
            action=PolicyAction.BLOCK,
            message=f"URL bloqueada: {url} não está na whitelist"
        )
