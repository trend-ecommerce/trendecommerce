```bash
# Caminho no novo repositório:
# src/collectors/live_discovery_engine.py
```

```python
"""Motor de Descoberta e Coleta em Tempo Real — Amazon e Mercado Livre.

Implementa a Estratégia de Mediana de Mercado em Tempo Real com Filtro de Outliers (IQR):
1. Normalização e correção fonética de termos de busca.
2. Consulta às APIs oficiais em tempo real (Amazon Suggestions & Mercado Livre Domain Discovery).
3. Classificação semântica por PLN para diferenciar produtos principais de acessórios (ex: Carregador vs iPhone).
4. Cálculo da Mediana Estatística de Mercado delimitada pelo Intervalo Interquartil (IQR [Q1, Q3]).
5. Eliminação de outliers (preços bizarros ou combos/kits inconsistentes).
6. Geração de série histórica coerente de 90 dias para alimentar o modelo preditivo XGBoost.
"""

import os
import re
import unicodedata
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from src.database.models import Product, SalesHistory

logger = logging.getLogger(__name__)


# Dicionário de correção de erros comuns de digitação e variações fonéticas
COMMON_TYPO_CORRECTIONS = {
    "havainas": "havaianas",
    "havaiana": "havaianas",
    "havaianna": "havaianas",
    "havaiano": "havaianas",
    "chinela": "chinelo",
    "sandalia": "sandália",
    "tenis": "tênis",
    "celular": "smartphone",
    "sansung": "samsung",
    "samssung": "samsung",
    "xiaomy": "xiaomi",
    "xaomi": "xiaomi",
    "fone": "fone de ouvido",
    "airfryer": "air fryer",
    "airfrier": "air fryer",
    "fritadeira": "air fryer",
    "notbook": "notebook",
    "notebuk": "notebook",
    "computador": "computador",
    "branca": "branca",
    "preta": "preta",
    "azul": "azul",
}

# Tabela calibrada de Mediana e Quartis (IQR) por nicho de mercado brasileiro (BRL)
# Lista Oficial de Categorias do Mercado Livre Brasil
OFFICIAL_MERCADOLIVRE_CATEGORIES = [
    "Tecnologia",
    "Eletrodomésticos",
    "Esportes e Fitness",
    "Casa e Móveis",
    "Ferramentas",
    "Construção",
    "Beleza e Cuidado Pessoal",
    "Moda",
    "Saúde",
    "Acessórios para Veículos",
    "Supermercado",
    "Bebês",
    "Brinquedos",
    "Livros",
    "Pet Shop",
    "Indústria e Comércio",
    "Para seu Negócio",
    "Veículos"
]

CATEGORY_NORMALIZE_MAP = {
    # Tecnologia
    "informática": "Tecnologia",
    "informatica": "Tecnologia",
    "celulares": "Tecnologia",
    "celulares e telefones": "Tecnologia",
    "games": "Tecnologia",
    "consoles de videogames": "Tecnologia",
    "gamepads e joysticks": "Tecnologia",
    "áudio": "Tecnologia",
    "audio": "Tecnologia",
    "eletrônicos": "Tecnologia",
    "eletronicos": "Tecnologia",
    "eletrônicos, áudio e vídeo": "Tecnologia",
    "casa inteligente": "Tecnologia",
    "câmeras de segurança": "Tecnologia",
    "cameras de seguranca": "Tecnologia",
    "câmeras e acessórios": "Tecnologia",
    "hds e ssds": "Tecnologia",
    "teclados para computadores": "Tecnologia",
    "monitores": "Tecnologia",
    "periféricos": "Tecnologia",
    "perifericos": "Tecnologia",
    "armazenamento": "Tecnologia",
    "acessórios para celulares": "Tecnologia",
    "cabos e adaptadores": "Tecnologia",
    "capas para celulares": "Tecnologia",
    "protetores de tela": "Tecnologia",
    "acessórios gamer": "Tecnologia",
    "televisores": "Tecnologia",
    "lâmpadas": "Tecnologia",
    "lampadas": "Tecnologia",
    "carregadores": "Tecnologia",

    # Eletrodomésticos
    "eletroportáteis": "Eletrodomésticos",
    "eletroportateis": "Eletrodomésticos",
    "eletrodomésticos": "Eletrodomésticos",
    "eletrodomesticos": "Eletrodomésticos",
    "liquidificadores": "Eletrodomésticos",

    # Esportes e Fitness
    "esportes & fitness": "Esportes e Fitness",
    "esportes e fitness": "Esportes e Fitness",
    "suplementos": "Esportes e Fitness",
    "moda esportiva": "Esportes e Fitness",

    # Moda
    "moda & vestuário": "Moda",
    "moda & vestuario": "Moda",
    "moda & calçados": "Moda",
    "moda & calcados": "Moda",
    "moda": "Moda",
    "calçados": "Moda",
    "calcados": "Moda",

    # Beleza e Cuidado Pessoal
    "beleza & cosméticos": "Beleza e Cuidado Pessoal",
    "beleza & cosmeticos": "Beleza e Cuidado Pessoal",
    "beleza e cuidado pessoal": "Beleza e Cuidado Pessoal",
    "protetores solares": "Beleza e Cuidado Pessoal",
    "secadores de cabelo": "Beleza e Cuidado Pessoal",

    # Casa e Móveis
    "móveis & casa": "Casa e Móveis",
    "moveis & casa": "Casa e Móveis",
    "casa e móveis": "Casa e Móveis",
    "casa e moveis": "Casa e Móveis",
    "fechaduras elétricas": "Casa e Móveis",
    "fechaduras eletricas": "Casa e Móveis",
    "acessórios e suportes": "Casa e Móveis",

    # Ferramentas
    "ferramentas": "Ferramentas",
    "ferramentas & casa": "Ferramentas",
    "kits de ferramentas combinadas": "Ferramentas",
    "lavadoras de alta pressão": "Ferramentas",
    "lavadoras de alta pressao": "Ferramentas",

    # Supermercado
    "alimentos & bebidas": "Supermercado",
    "alimentos e bebidas": "Supermercado",
    "supermercado": "Supermercado",

    # Acessórios para Veículos
    "automotivo": "Acessórios para Veículos",
    "acessórios para veículos": "Acessórios para Veículos",
    "acessorios para veiculos": "Acessórios para Veículos",

    # Livros
    "livros": "Livros",

    # Saúde
    "saúde": "Saúde",
    "saude": "Saúde",

    # Pet Shop
    "pet shop": "Pet Shop",

    # Construção
    "construção": "Construção",
    "construcao": "Construção",

    # Bebês
    "bebês": "Bebês",
    "bebes": "Bebês",

    # Brinquedos
    "brinquedos": "Brinquedos",

    # Indústria e Comércio
    "indústria e comércio": "Indústria e Comércio",
    "industria e comercio": "Indústria e Comércio",

    # Para seu Negócio
    "para seu negócio": "Para seu Negócio",
    "para seu negocio": "Para seu Negócio",

    # Veículos
    "veículos": "Veículos",
    "veiculos": "Veículos"
}

def normalize_category(raw: Optional[str]) -> str:
    """Normaliza qualquer termo de categoria para a árvore oficial do Mercado Livre."""
    if not raw:
        return "Tecnologia"
    cleaned = raw.strip().lower()
    return CATEGORY_NORMALIZE_MAP.get(cleaned, raw.strip().title())