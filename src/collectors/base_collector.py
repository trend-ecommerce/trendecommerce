"""Classe base abstrata para todos os coletores de dados.

Define a interface padrão que todos os coletores devem implementar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CollectorResult:
    """Resultado de uma coleta de dados."""
    source: str
    data: list[dict[str, Any]]
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True
    error_message: Optional[str] = None
    records_count: int = 0

    def __post_init__(self):
        self.records_count = len(self.data)


class BaseCollector(ABC):
    """Classe base para coletores de dados.
    
    Todos os coletores (Amazon, Mercado Livre, Google Trends)
    devem herdar desta classe e implementar os métodos abstratos.
    """

    def __init__(self, name: str):
        self.name = name
        self._is_authenticated = False

    @abstractmethod
    def authenticate(self) -> bool:
        """Realiza autenticação com a API.
        
        Returns:
            True se a autenticação foi bem-sucedida
        """
        pass

    @abstractmethod
    def collect(self, **kwargs) -> CollectorResult:
        """Executa a coleta de dados.
        
        Returns:
            Resultado da coleta
        """
        pass

    @abstractmethod
    def validate_response(self, response: Any) -> bool:
        """Valida a resposta da API.
        
        Args:
            response: Resposta recebida da API
            
        Returns:
            True se a resposta é válida
        """
        pass

    @property
    def is_authenticated(self) -> bool:
        """Verifica se o coletor está autenticado."""
        return self._is_authenticated

    def _create_error_result(self, error_message: str) -> CollectorResult:
        """Cria um resultado de erro."""
        return CollectorResult(
            source=self.name,
            data=[],
            success=False,
            error_message=error_message
        )

    def _create_success_result(self, data: list[dict]) -> CollectorResult:
        """Cria um resultado de sucesso."""
        return CollectorResult(
            source=self.name,
            data=data,
            success=True
        )
