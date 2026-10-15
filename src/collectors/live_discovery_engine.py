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

# Tabela calibrada de Mediana e Quartis (IQR) por nicho de mercado brasileiro (BRL)
NICHE_PRICE_ESTIMATES = {
    # Acessórios de Celular & Informática (baixo valor agregado)
    "carregador iphone": {"category": "Tecnologia", "median": 89.90, "q1": 69.90, "q3": 129.90, "avg_daily": 60},
    "fonte carregador": {"category": "Tecnologia", "median": 79.90, "q1": 59.90, "q3": 119.90, "avg_daily": 55},
    "carregador": {"category": "Tecnologia", "median": 79.90, "q1": 49.90, "q3": 119.90, "avg_daily": 50},
    "cabo lightning": {"category": "Tecnologia", "median": 49.90, "q1": 29.90, "q3": 79.90, "avg_daily": 65},
    "cabo usb-c": {"category": "Tecnologia", "median": 39.90, "q1": 24.90, "q3": 69.90, "avg_daily": 70},
    "cabo": {"category": "Tecnologia", "median": 39.90, "q1": 20.00, "q3": 69.90, "avg_daily": 60},
    "capinha": {"category": "Tecnologia", "median": 39.90, "q1": 25.00, "q3": 69.00, "avg_daily": 80},
    "capa": {"category": "Tecnologia", "median": 45.00, "q1": 25.00, "q3": 79.00, "avg_daily": 70},
    "pelicula": {"category": "Tecnologia", "median": 29.90, "q1": 19.90, "q3": 49.90, "avg_daily": 75},
    "suporte celular": {"category": "Acessórios para Veículos", "median": 45.90, "q1": 35.00, "q3": 69.90, "avg_daily": 40},

    # Suplementos
    "creatina 300g": {"category": "Esportes e Fitness", "median": 69.90, "q1": 59.90, "q3": 79.90, "avg_daily": 85},
    "creatina max titanium": {"category": "Esportes e Fitness", "median": 69.90, "q1": 59.90, "q3": 79.90, "avg_daily": 85},
    "creatina monohidratada": {"category": "Esportes e Fitness", "median": 69.90, "q1": 59.90, "q3": 84.90, "avg_daily": 80},
    "creatina 1kg": {"category": "Esportes e Fitness", "median": 189.90, "q1": 159.90, "q3": 229.90, "avg_daily": 30},
    "creatina creapure": {"category": "Esportes e Fitness", "median": 119.90, "q1": 99.90, "q3": 149.90, "avg_daily": 40},
    "kit creatina": {"category": "Esportes e Fitness", "median": 139.90, "q1": 119.90, "q3": 179.90, "avg_daily": 35},
    "creatina": {"category": "Esportes e Fitness", "median": 69.90, "q1": 59.90, "q3": 79.90, "avg_daily": 80},
    "whey protein isolado": {"category": "Esportes e Fitness", "median": 169.90, "q1": 139.90, "q3": 219.90, "avg_daily": 35},
    "whey protein 900g": {"category": "Esportes e Fitness", "median": 109.90, "q1": 89.90, "q3": 139.90, "avg_daily": 50},
    "whey protein": {"category": "Esportes e Fitness", "median": 109.90, "q1": 89.90, "q3": 149.90, "avg_daily": 50},
    "whey": {"category": "Esportes e Fitness", "median": 109.90, "q1": 89.90, "q3": 149.90, "avg_daily": 50},
    "pre treino": {"category": "Esportes e Fitness", "median": 89.90, "q1": 69.90, "q3": 129.90, "avg_daily": 45},
    "suplemento": {"category": "Esportes e Fitness", "median": 79.90, "q1": 49.90, "q3": 129.90, "avg_daily": 45},

    # Placas de Vídeo / GPUs (Tecnologia)
    "rtx 5090": {"category": "Tecnologia", "median": 13999.00, "q1": 11999.00, "q3": 16999.00, "avg_daily": 5},
    "rtx 4090": {"category": "Tecnologia", "median": 12999.00, "q1": 10999.00, "q3": 14999.00, "avg_daily": 6},
    "rtx 5080": {"category": "Tecnologia", "median": 7999.00, "q1": 6999.00, "q3": 8999.00, "avg_daily": 8},
    "rtx 4080": {"category": "Tecnologia", "median": 7499.00, "q1": 6499.00, "q3": 8499.00, "avg_daily": 8},
    "rtx 5070 ti": {"category": "Tecnologia", "median": 4999.00, "q1": 4499.00, "q3": 5699.00, "avg_daily": 12},
    "rtx 5070": {"category": "Tecnologia", "median": 4299.00, "q1": 3799.00, "q3": 4799.00, "avg_daily": 14},
    "rtx 4070 ti": {"category": "Tecnologia", "median": 4799.00, "q1": 4299.00, "q3": 5299.00, "avg_daily": 12},
    "rtx 4070 super": {"category": "Tecnologia", "median": 4199.00, "q1": 3699.00, "q3": 4699.00, "avg_daily": 14},
    "rtx 4070": {"category": "Tecnologia", "median": 3899.00, "q1": 3399.00, "q3": 4399.00, "avg_daily": 15},
    "rtx 5060 ti": {"category": "Tecnologia", "median": 2999.00, "q1": 2699.00, "q3": 3499.00, "avg_daily": 18},
    "rtx 5060": {"category": "Tecnologia", "median": 2199.00, "q1": 1899.00, "q3": 2599.00, "avg_daily": 22},
    "rtx 4060 ti": {"category": "Tecnologia", "median": 2799.00, "q1": 2499.00, "q3": 3199.00, "avg_daily": 20},
    "rtx 4060": {"category": "Tecnologia", "median": 2099.00, "q1": 1799.00, "q3": 2399.00, "avg_daily": 25},
    "rtx 3060 ti": {"category": "Tecnologia", "median": 2099.00, "q1": 1799.00, "q3": 2399.00, "avg_daily": 18},
    "rtx 3060": {"category": "Tecnologia", "median": 1849.00, "q1": 1599.00, "q3": 2099.00, "avg_daily": 24},
    "rtx 3050": {"category": "Tecnologia", "median": 1349.00, "q1": 1149.00, "q3": 1549.00, "avg_daily": 22},
    "gtx 1660 super": {"category": "Tecnologia", "median": 1299.00, "q1": 1099.00, "q3": 1499.00, "avg_daily": 20},
    "gtx 1650": {"category": "Tecnologia", "median": 899.00, "q1": 749.00, "q3": 1049.00, "avg_daily": 18},
    "rx 7600": {"category": "Tecnologia", "median": 1799.00, "q1": 1549.00, "q3": 1999.00, "avg_daily": 16},
    "rx 6600": {"category": "Tecnologia", "median": 1399.00, "q1": 1199.00, "q3": 1599.00, "avg_daily": 20},
    "placa de video": {"category": "Tecnologia", "median": 2399.00, "q1": 1499.00, "q3": 3899.00, "avg_daily": 18},

    # Processadores / CPUs (Tecnologia)
    "ryzen 7 7800x3d": {"category": "Tecnologia", "median": 2899.00, "q1": 2599.00, "q3": 3299.00, "avg_daily": 15},
    "ryzen 7 5700x": {"category": "Tecnologia", "median": 1299.00, "q1": 1099.00, "q3": 1499.00, "avg_daily": 25},
    "ryzen 5 5600x": {"category": "Tecnologia", "median": 999.00, "q1": 849.00, "q3": 1199.00, "avg_daily": 28},
    "ryzen 5 5600g": {"category": "Tecnologia", "median": 899.00, "q1": 749.00, "q3": 1049.00, "avg_daily": 30},
    "ryzen 5 5600": {"category": "Tecnologia", "median": 849.00, "q1": 699.00, "q3": 999.00, "avg_daily": 32},
    "ryzen 5 5500": {"category": "Tecnologia", "median": 649.00, "q1": 549.00, "q3": 749.00, "avg_daily": 30},
    "core i7": {"category": "Tecnologia", "median": 2299.00, "q1": 1699.00, "q3": 2899.00, "avg_daily": 18},
    "core i5": {"category": "Tecnologia", "median": 1099.00, "q1": 799.00, "q3": 1499.00, "avg_daily": 25},
    "core i3": {"category": "Tecnologia", "median": 599.00, "q1": 449.00, "q3": 799.00, "avg_daily": 20},
    "processador": {"category": "Tecnologia", "median": 1199.00, "q1": 699.00, "q3": 2199.00, "avg_daily": 22},

    # Hardware & Componentes (Tecnologia)
    "placa mae": {"category": "Tecnologia", "median": 699.00, "q1": 449.00, "q3": 1199.00, "avg_daily": 22},
    "fonte atx": {"category": "Tecnologia", "median": 389.00, "q1": 249.00, "q3": 599.00, "avg_daily": 22},
    "gabinete gamer": {"category": "Tecnologia", "median": 299.00, "q1": 199.00, "q3": 499.00, "avg_daily": 20},
    "memoria ram 16gb": {"category": "Tecnologia", "median": 269.00, "q1": 199.00, "q3": 349.00, "avg_daily": 35},
    "memoria ram 8gb": {"category": "Tecnologia", "median": 149.00, "q1": 99.00, "q3": 199.00, "avg_daily": 40},
    "memoria ram": {"category": "Tecnologia", "median": 249.00, "q1": 149.00, "q3": 399.00, "avg_daily": 35},
    "water cooler": {"category": "Tecnologia", "median": 349.00, "q1": 249.00, "q3": 549.00, "avg_daily": 18},
    "air cooler": {"category": "Tecnologia", "median": 129.00, "q1": 79.00, "q3": 199.00, "avg_daily": 25},

    # Notebooks & PCs (Tecnologia)
    "macbook pro": {"category": "Tecnologia", "median": 12999.00, "q1": 9999.00, "q3": 17999.00, "avg_daily": 8},
    "macbook air": {"category": "Tecnologia", "median": 6899.00, "q1": 5999.00, "q3": 7999.00, "avg_daily": 12},
    "macbook": {"category": "Tecnologia", "median": 7499.00, "q1": 5999.00, "q3": 11999.00, "avg_daily": 10},
    "notebook gamer": {"category": "Tecnologia", "median": 4499.00, "q1": 3699.00, "q3": 5899.00, "avg_daily": 16},
    "pc gamer": {"category": "Tecnologia", "median": 3899.00, "q1": 2699.00, "q3": 5999.00, "avg_daily": 18},
    "computador": {"category": "Tecnologia", "median": 2499.00, "q1": 1599.00, "q3": 3999.00, "avg_daily": 16},
    "notebook dell": {"category": "Tecnologia", "median": 3299.00, "q1": 2499.00, "q3": 4299.00, "avg_daily": 20},
    "notebook lenovo": {"category": "Tecnologia", "median": 2699.00, "q1": 1999.00, "q3": 3499.00, "avg_daily": 22},
    "notebook acer": {"category": "Tecnologia", "median": 2999.00, "q1": 2199.00, "q3": 3999.00, "avg_daily": 20},
    "notebook": {"category": "Tecnologia", "median": 2699.00, "q1": 1899.00, "q3": 3999.00, "avg_daily": 20},
    "laptop": {"category": "Tecnologia", "median": 2699.00, "q1": 1899.00, "q3": 3999.00, "avg_daily": 20},

    # Monitores e periféricos (Tecnologia)
    "monitor 24": {"category": "Tecnologia", "median": 799.00, "q1": 699.00, "q3": 899.00, "avg_daily": 18},
    "monitor 27": {"category": "Tecnologia", "median": 1099.00, "q1": 899.00, "q3": 1399.00, "avg_daily": 15},
    "monitor 144hz": {"category": "Tecnologia", "median": 899.00, "q1": 799.00, "q3": 1199.00, "avg_daily": 20},
    "monitor gamer": {"category": "Tecnologia", "median": 899.00, "q1": 799.00, "q3": 1299.00, "avg_daily": 18},
    "monitor": {"category": "Tecnologia", "median": 799.00, "q1": 599.00, "q3": 1199.00, "avg_daily": 16},
    "teclado mecanico": {"category": "Tecnologia", "median": 199.90, "q1": 149.00, "q3": 279.00, "avg_daily": 28},
    "teclado": {"category": "Tecnologia", "median": 129.90, "q1": 69.00, "q3": 199.00, "avg_daily": 30},
    "mouse gamer": {"category": "Tecnologia", "median": 129.90, "q1": 79.00, "q3": 219.00, "avg_daily": 35},
    "mouse": {"category": "Tecnologia", "median": 79.90, "q1": 39.00, "q3": 149.00, "avg_daily": 40},
    "headset gamer": {"category": "Tecnologia", "median": 249.00, "q1": 149.00, "q3": 399.00, "avg_daily": 25},
    "headset": {"category": "Tecnologia", "median": 189.00, "q1": 99.00, "q3": 349.00, "avg_daily": 25},
    "ssd 1tb": {"category": "Tecnologia", "median": 389.00, "q1": 349.00, "q3": 449.00, "avg_daily": 35},
    "ssd 512gb": {"category": "Tecnologia", "median": 229.00, "q1": 189.00, "q3": 269.00, "avg_daily": 40},
    "ssd": {"category": "Tecnologia", "median": 289.00, "q1": 149.00, "q3": 429.00, "avg_daily": 35},

    # Smartphones & Informática (Tecnologia)
    "iphone 16 pro max": {"category": "Tecnologia", "median": 8999.00, "q1": 8499.00, "q3": 9999.00, "avg_daily": 10},
    "iphone 16 pro": {"category": "Tecnologia", "median": 7899.00, "q1": 7299.00, "q3": 8499.00, "avg_daily": 12},
    "iphone 16": {"category": "Tecnologia", "median": 5899.00, "q1": 5399.00, "q3": 6499.00, "avg_daily": 15},
    "iphone 15 pro max": {"category": "Tecnologia", "median": 7499.00, "q1": 6999.00, "q3": 7999.00, "avg_daily": 12},
    "iphone 15 pro": {"category": "Tecnologia", "median": 6499.00, "q1": 6199.00, "q3": 7199.00, "avg_daily": 14},
    "iphone 15": {"category": "Tecnologia", "median": 4899.00, "q1": 4599.00, "q3": 5199.00, "avg_daily": 18},
    "iphone 13": {"category": "Tecnologia", "median": 3599.00, "q1": 3299.00, "q3": 3799.00, "avg_daily": 22},
    "iphone 14": {"category": "Tecnologia", "median": 3999.00, "q1": 3799.00, "q3": 4299.00, "avg_daily": 18},
    "iphone": {"category": "Tecnologia", "median": 4899.00, "q1": 3299.00, "q3": 7499.00, "avg_daily": 18},
    "galaxy s24 ultra": {"category": "Tecnologia", "median": 6499.00, "q1": 5899.00, "q3": 6999.00, "avg_daily": 12},
    "galaxy s24": {"category": "Tecnologia", "median": 4299.00, "q1": 3899.00, "q3": 4699.00, "avg_daily": 16},
    "galaxy s23": {"category": "Tecnologia", "median": 3199.00, "q1": 2799.00, "q3": 3599.00, "avg_daily": 18},
    "motorola edge": {"category": "Tecnologia", "median": 2199.00, "q1": 1899.00, "q3": 2399.00, "avg_daily": 18},
    "samsung": {"category": "Tecnologia", "median": 1899.00, "q1": 890.00, "q3": 3490.00, "avg_daily": 25},
    "xiaomi": {"category": "Tecnologia", "median": 1499.00, "q1": 890.00, "q3": 1999.00, "avg_daily": 25},
    "smartphone": {"category": "Tecnologia", "median": 1899.00, "q1": 890.00, "q3": 3490.00, "avg_daily": 20},
    "celular": {"category": "Tecnologia", "median": 1899.00, "q1": 790.00, "q3": 3490.00, "avg_daily": 20},
    "ipad": {"category": "Tecnologia", "median": 4499.00, "q1": 3299.00, "q3": 6499.00, "avg_daily": 14},
    "tablet": {"category": "Tecnologia", "median": 1499.00, "q1": 899.00, "q3": 2899.00, "avg_daily": 18},

    # Consoles & Games (Tecnologia)
    "playstation 5 pro": {"category": "Tecnologia", "median": 6499.00, "q1": 5999.00, "q3": 6999.00, "avg_daily": 10},
    "playstation 5 slim": {"category": "Tecnologia", "median": 3699.00, "q1": 3499.00, "q3": 3899.00, "avg_daily": 15},
    "playstation 5": {"category": "Tecnologia", "median": 3699.00, "q1": 3499.00, "q3": 3899.00, "avg_daily": 15},
    "ps5": {"category": "Tecnologia", "median": 3699.00, "q1": 3499.00, "q3": 3899.00, "avg_daily": 15},
    "xbox series x": {"category": "Tecnologia", "median": 3999.00, "q1": 3799.00, "q3": 4299.00, "avg_daily": 10},
    "xbox series s": {"category": "Tecnologia", "median": 2499.00, "q1": 2299.00, "q3": 2599.00, "avg_daily": 16},
    "nintendo switch oled": {"category": "Tecnologia", "median": 2199.00, "q1": 1999.00, "q3": 2399.00, "avg_daily": 15},
    "nintendo switch": {"category": "Tecnologia", "median": 1999.00, "q1": 1799.00, "q3": 2149.00, "avg_daily": 15},
    "controle ps5": {"category": "Tecnologia", "median": 399.00, "q1": 369.00, "q3": 429.00, "avg_daily": 30},
    "controle xbox": {"category": "Tecnologia", "median": 389.00, "q1": 349.00, "q3": 419.00, "avg_daily": 28},
    "controle": {"category": "Tecnologia", "median": 299.00, "q1": 149.00, "q3": 419.00, "avg_daily": 30},

    # Smart TVs (Tecnologia)
    "smart tv 65": {"category": "Tecnologia", "median": 3999.00, "q1": 3299.00, "q3": 4999.00, "avg_daily": 12},
    "smart tv 55": {"category": "Tecnologia", "median": 2699.00, "q1": 2299.00, "q3": 3199.00, "avg_daily": 16},
    "smart tv 50": {"category": "Tecnologia", "median": 2199.00, "q1": 1899.00, "q3": 2499.00, "avg_daily": 18},
    "smart tv 43": {"category": "Tecnologia", "median": 1699.00, "q1": 1399.00, "q3": 1999.00, "avg_daily": 20},
    "smart tv 32": {"category": "Tecnologia", "median": 1099.00, "q1": 899.00, "q3": 1299.00, "avg_daily": 22},
    "smart tv": {"category": "Tecnologia", "median": 2199.00, "q1": 1299.00, "q3": 3499.00, "avg_daily": 16},
    "tv": {"category": "Tecnologia", "median": 2199.00, "q1": 1299.00, "q3": 3499.00, "avg_daily": 16},

    # Eletrodomésticos Grandes
    "geladeira frost free": {"category": "Eletrodomésticos", "median": 3499.00, "q1": 2799.00, "q3": 4599.00, "avg_daily": 10},
    "geladeira": {"category": "Eletrodomésticos", "median": 3299.00, "q1": 2399.00, "q3": 4699.00, "avg_daily": 10},
    "refrigerador": {"category": "Eletrodomésticos", "median": 3299.00, "q1": 2399.00, "q3": 4699.00, "avg_daily": 10},
    "lava e seca": {"category": "Eletrodomésticos", "median": 3299.00, "q1": 2699.00, "q3": 4199.00, "avg_daily": 12},
    "maquina de lavar": {"category": "Eletrodomésticos", "median": 2199.00, "q1": 1699.00, "q3": 2899.00, "avg_daily": 14},
    "lavadora de roupas": {"category": "Eletrodomésticos", "median": 2199.00, "q1": 1699.00, "q3": 2899.00, "avg_daily": 14},
    "ar condicionado inverter": {"category": "Eletrodomésticos", "median": 2399.00, "q1": 1899.00, "q3": 3199.00, "avg_daily": 14},
    "ar condicionado": {"category": "Eletrodomésticos", "median": 2199.00, "q1": 1699.00, "q3": 2999.00, "avg_daily": 14},
    "fogao 5 bocas": {"category": "Eletrodomésticos", "median": 1299.00, "q1": 999.00, "q3": 1699.00, "avg_daily": 16},
    "fogao 4 bocas": {"category": "Eletrodomésticos", "median": 899.00, "q1": 699.00, "q3": 1199.00, "avg_daily": 18},
    "cooktop": {"category": "Eletrodomésticos", "median": 549.00, "q1": 399.00, "q3": 799.00, "avg_daily": 20},
    "micro-ondas": {"category": "Eletrodomésticos", "median": 599.00, "q1": 469.00, "q3": 799.00, "avg_daily": 22},
    "microondas": {"category": "Eletrodomésticos", "median": 599.00, "q1": 469.00, "q3": 799.00, "avg_daily": 22},

    # Eletroportáteis
    "air fryer": {"category": "Eletrodomésticos", "median": 349.00, "q1": 269.00, "q3": 429.00, "avg_daily": 28},
    "fritadeira": {"category": "Eletrodomésticos", "median": 349.00, "q1": 269.00, "q3": 429.00, "avg_daily": 26},
    "aspirador robo": {"category": "Eletrodomésticos", "median": 699.00, "q1": 499.00, "q3": 899.00, "avg_daily": 18},
    "aspirador": {"category": "Eletrodomésticos", "median": 299.00, "q1": 149.00, "q3": 499.00, "avg_daily": 25},
    "cafeteira nespresso": {"category": "Eletrodomésticos", "median": 389.00, "q1": 349.00, "q3": 469.00, "avg_daily": 22},
    "cafeteira": {"category": "Eletrodomésticos", "median": 249.00, "q1": 119.00, "q3": 399.00, "avg_daily": 22},
    "liquidificador": {"category": "Eletrodomésticos", "median": 189.00, "q1": 99.00, "q3": 289.00, "avg_daily": 25},

    # Casa e Móveis
    "fechadura digital": {"category": "Casa e Móveis", "median": 499.00, "q1": 399.00, "q3": 649.00, "avg_daily": 16},
    "cadeira gamer": {"category": "Casa e Móveis", "median": 699.00, "q1": 499.00, "q3": 999.00, "avg_daily": 16},
    "cadeira de escritorio": {"category": "Casa e Móveis", "median": 499.00, "q1": 349.00, "q3": 799.00, "avg_daily": 15},
    "mesa escrivaninha": {"category": "Casa e Móveis", "median": 299.00, "q1": 199.00, "q3": 499.00, "avg_daily": 18},
    "camera de seguranca": {"category": "Tecnologia", "median": 179.90, "q1": 139.00, "q3": 239.00, "avg_daily": 25},
    "echo dot": {"category": "Tecnologia", "median": 349.00, "q1": 299.00, "q3": 379.00, "avg_daily": 35},
    "alexa": {"category": "Tecnologia", "median": 349.00, "q1": 299.00, "q3": 429.00, "avg_daily": 32},
    "lampada inteligente": {"category": "Tecnologia", "median": 49.90, "q1": 39.90, "q3": 69.90, "avg_daily": 45},

    # Beleza e Cuidado Pessoal
    "protetor solar": {"category": "Beleza e Cuidado Pessoal", "median": 84.90, "q1": 69.90, "q3": 94.90, "avg_daily": 40},
    "perfume sauvage": {"category": "Beleza e Cuidado Pessoal", "median": 649.00, "q1": 549.00, "q3": 749.00, "avg_daily": 15},
    "perfume importado": {"category": "Beleza e Cuidado Pessoal", "median": 549.00, "q1": 399.00, "q3": 799.00, "avg_daily": 18},
    "perfume": {"category": "Beleza e Cuidado Pessoal", "median": 289.00, "q1": 149.00, "q3": 449.00, "avg_daily": 22},
    "escova secadora": {"category": "Beleza e Cuidado Pessoal", "median": 169.00, "q1": 119.00, "q3": 229.00, "avg_daily": 25},
    "secador de cabelo": {"category": "Beleza e Cuidado Pessoal", "median": 249.00, "q1": 149.00, "q3": 349.00, "avg_daily": 20},
    "secador": {"category": "Beleza e Cuidado Pessoal", "median": 249.00, "q1": 149.00, "q3": 349.00, "avg_daily": 20},
    "maquina de cortar cabelo": {"category": "Beleza e Cuidado Pessoal", "median": 149.00, "q1": 89.00, "q3": 249.00, "avg_daily": 25},

    # Áudio (Tecnologia)
    "airpods max": {"category": "Tecnologia", "median": 4999.00, "q1": 4299.00, "q3": 5499.00, "avg_daily": 8},
    "airpods pro": {"category": "Tecnologia", "median": 1699.00, "q1": 1499.00, "q3": 1999.00, "avg_daily": 20},
    "airpods": {"category": "Tecnologia", "median": 999.00, "q1": 849.00, "q3": 1299.00, "avg_daily": 22},
    "caixa de som jbl": {"category": "Tecnologia", "median": 599.00, "q1": 499.00, "q3": 749.00, "avg_daily": 20},
    "caixa de som": {"category": "Tecnologia", "median": 299.00, "q1": 149.00, "q3": 699.00, "avg_daily": 20},
    "soundbar": {"category": "Tecnologia", "median": 699.00, "q1": 449.00, "q3": 1199.00, "avg_daily": 18},
    "fone bluetooth": {"category": "Tecnologia", "median": 179.00, "q1": 99.00, "q3": 299.00, "avg_daily": 35},
    "fone": {"category": "Tecnologia", "median": 149.00, "q1": 79.00, "q3": 279.00, "avg_daily": 35},

    # Ferramentas
    "lavadora de alta pressao": {"category": "Ferramentas", "median": 589.00, "q1": 449.00, "q3": 689.00, "avg_daily": 16},
    "parafusadeira": {"category": "Ferramentas", "median": 299.00, "q1": 199.00, "q3": 399.00, "avg_daily": 20},
    "furadeira": {"category": "Ferramentas", "median": 249.00, "q1": 179.00, "q3": 349.00, "avg_daily": 18},
    "jogo de ferramentas": {"category": "Ferramentas", "median": 199.90, "q1": 139.00, "q3": 249.00, "avg_daily": 25},
    "maleta de ferramentas": {"category": "Ferramentas", "median": 199.90, "q1": 139.00, "q3": 249.00, "avg_daily": 25},

    # Moda
    "camisa da jamaica": {"category": "Moda", "median": 139.90, "q1": 99.90, "q3": 179.90, "avg_daily": 15},
    "camisa do corinthians": {"category": "Moda", "median": 149.90, "q1": 99.90, "q3": 229.90, "avg_daily": 30},
    "camisa do flamengo": {"category": "Moda", "median": 149.90, "q1": 99.90, "q3": 229.90, "avg_daily": 30},
    "camisa do palmeiras": {"category": "Moda", "median": 149.90, "q1": 99.90, "q3": 229.90, "avg_daily": 25},
    "camisa de time": {"category": "Moda", "median": 149.90, "q1": 99.90, "q3": 229.90, "avg_daily": 20},
    "camisa futebol": {"category": "Moda", "median": 139.90, "q1": 89.90, "q3": 199.90, "avg_daily": 20},
    "camisa social": {"category": "Moda", "median": 119.90, "q1": 89.90, "q3": 159.90, "avg_daily": 18},
    "camisa": {"category": "Moda", "median": 89.90, "q1": 59.90, "q3": 139.90, "avg_daily": 16},
    "camiseta": {"category": "Moda", "median": 59.90, "q1": 39.90, "q3": 89.90, "avg_daily": 22},
    "havaianas": {"category": "Moda", "median": 44.90, "q1": 29.90, "q3": 59.90, "avg_daily": 50},
    "chinelo": {"category": "Moda", "median": 44.90, "q1": 25.00, "q3": 59.90, "avg_daily": 45},
    "tenis nike": {"category": "Moda", "median": 299.90, "q1": 229.00, "q3": 399.00, "avg_daily": 30},
    "tenis adidas": {"category": "Moda", "median": 279.90, "q1": 199.00, "q3": 369.00, "avg_daily": 28},
    "tenis": {"category": "Moda", "median": 249.90, "q1": 149.00, "q3": 369.00, "avg_daily": 30},
    "smartwatch": {"category": "Tecnologia", "median": 349.00, "q1": 199.00, "q3": 899.00, "avg_daily": 20},
    "livro": {"category": "Livros", "median": 49.90, "q1": 35.00, "q3": 79.90, "avg_daily": 25},
}

# Mapeamento oficial de Domínios do Mercado Livre para Benchmarks Estatísticos
DOMAIN_BENCHMARKS = {
    # Hardware & Componentes
    "MLB-GRAPHICS_CARDS": {"category": "Tecnologia", "median": 2499.00, "q1": 1499.00, "q3": 3899.00, "avg_daily": 15},
    "MLB-PROCESSORS": {"category": "Tecnologia", "median": 1199.00, "q1": 699.00, "q3": 2299.00, "avg_daily": 18},
    "MLB-MOTHERBOARDS": {"category": "Tecnologia", "median": 699.00, "q1": 499.00, "q3": 1199.00, "avg_daily": 20},
    "MLB-COMPUTER_POWER_SUPPLIES": {"category": "Tecnologia", "median": 389.00, "q1": 249.00, "q3": 599.00, "avg_daily": 22},
    "MLB-COMPUTER_CASES": {"category": "Tecnologia", "median": 299.00, "q1": 199.00, "q3": 499.00, "avg_daily": 20},
    "MLB-RAM_MEMORY_MODULES": {"category": "Tecnologia", "median": 249.00, "q1": 169.00, "q3": 399.00, "avg_daily": 35},
    "MLB-SOLID_STATE_DRIVES": {"category": "Tecnologia", "median": 299.00, "q1": 189.00, "q3": 449.00, "avg_daily": 40},
    
    # Eletrônicos & Computadores
    "MLB-COMPUTERS": {"category": "Tecnologia", "median": 2899.00, "q1": 1899.00, "q3": 4499.00, "avg_daily": 15},
    "MLB-DESKTOP_COMPUTERS": {"category": "Tecnologia", "median": 2899.00, "q1": 1899.00, "q3": 4499.00, "avg_daily": 15},
    "MLB-NOTEBOOKS": {"category": "Tecnologia", "median": 3499.00, "q1": 2399.00, "q3": 5499.00, "avg_daily": 12},
    "MLB-MONITORS": {"category": "Tecnologia", "median": 899.00, "q1": 699.00, "q3": 1299.00, "avg_daily": 18},
    "MLB-TELEVISIONS": {"category": "Tecnologia", "median": 2199.00, "q1": 1499.00, "q3": 3499.00, "avg_daily": 16},
    "MLB-TABLETS": {"category": "Tecnologia", "median": 1899.00, "q1": 1199.00, "q3": 3499.00, "avg_daily": 16},
    "MLB-SMARTWATCHES": {"category": "Tecnologia", "median": 499.00, "q1": 249.00, "q3": 1499.00, "avg_daily": 22},
    "MLB-CELLPHONES": {"category": "Tecnologia", "median": 3599.00, "q1": 1899.00, "q3": 6499.00, "avg_daily": 20},
    "MLB-HEADPHONES": {"category": "Tecnologia", "median": 189.00, "q1": 99.00, "q3": 349.00, "avg_daily": 30},
    "MLB-VIDEO_GAME_CONSOLES": {"category": "Tecnologia", "median": 3699.00, "q1": 2299.00, "q3": 3999.00, "avg_daily": 15},
    "MLB-GAME_CONTROLLERS": {"category": "Tecnologia", "median": 389.00, "q1": 199.00, "q3": 429.00, "avg_daily": 28},

    # Acessórios de Celular
    "MLB-MOBILE_DEVICE_CHARGERS": {"category": "Tecnologia", "median": 89.90, "q1": 59.90, "q3": 139.90, "avg_daily": 55},
    "MLB-CELL_PHONE_CABLES": {"category": "Tecnologia", "median": 39.90, "q1": 24.90, "q3": 69.90, "avg_daily": 65},
    "MLB-CELL_PHONE_COVERS": {"category": "Tecnologia", "median": 39.90, "q1": 25.00, "q3": 69.90, "avg_daily": 75},
    "MLB-SCREEN_PROTECTORS": {"category": "Tecnologia", "median": 29.90, "q1": 19.90, "q3": 49.90, "avg_daily": 70},

    # Eletrodomésticos
    "MLB-REFRIGERATORS": {"category": "Eletrodomésticos", "median": 3499.00, "q1": 2499.00, "q3": 4899.00, "avg_daily": 10},
    "MLB-WASHING_MACHINES": {"category": "Eletrodomésticos", "median": 2499.00, "q1": 1799.00, "q3": 3299.00, "avg_daily": 12},
    "MLB-AIR_CONDITIONERS": {"category": "Eletrodomésticos", "median": 2299.00, "q1": 1699.00, "q3": 3199.00, "avg_daily": 14},
    "MLB-DEEP_FRYERS": {"category": "Eletrodomésticos", "median": 349.00, "q1": 269.00, "q3": 449.00, "avg_daily": 28},
    "MLB-VACUUM_CLEANERS": {"category": "Eletrodomésticos", "median": 699.00, "q1": 299.00, "q3": 899.00, "avg_daily": 20},

    # Moda & Outros
    "MLB-FOOTWEAR": {"category": "Moda", "median": 149.90, "q1": 44.90, "q3": 289.00, "avg_daily": 40},
    "MLB-FOOTBALL_SHIRTS": {"category": "Moda", "median": 149.90, "q1": 99.90, "q3": 229.90, "avg_daily": 20},
    "MLB-SUPPLEMENTS": {"category": "Esportes e Fitness", "median": 69.90, "q1": 59.90, "q3": 89.90, "avg_daily": 75},
    "MLB-PERFUMES": {"category": "Beleza e Cuidado Pessoal", "median": 279.00, "q1": 149.00, "q3": 499.00, "avg_daily": 25},
    "MLB-TIRES": {"category": "Acessórios para Veículos", "median": 369.00, "q1": 289.00, "q3": 489.00, "avg_daily": 20},
}