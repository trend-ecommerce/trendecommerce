"""API Guardian - Camada de segurança e conformidade do TrendCommerce AI.

O Guardian funciona como uma camada de fiscalização das integrações,
verificando endpoints, credenciais e políticas de acesso às APIs.
"""

from .policy_engine import PolicyEngine, PolicyResult, PolicyAction
from .whitelist import APIWhitelist
from .checker import RequestChecker
from .credential_scanner import CredentialScanner

__all__ = [
    "PolicyEngine",
    "PolicyResult", 
    "PolicyAction",
    "APIWhitelist",
    "RequestChecker",
    "CredentialScanner",
]
