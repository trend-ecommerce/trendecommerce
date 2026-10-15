"""Coletor e Sincronizador de Categorias do Mercado Livre e Amazon — TrendCommerce AI.

Varre os principais nichos de mercado, descobre produtos populares em tempo real
e os importa massivamente para a base de dados preditiva.
"""

import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.database.models import Product
from src.collectors.live_discovery_engine import live_discovery

logger = logging.getLogger(__name__)

TOP_MARKET_SEEDS = [
    # Celulares
    "iPhone 15 Pro Max", "Samsung Galaxy S24 Ultra", "Xiaomi Redmi Note 13", "Motorola Edge 50",
    # Games
    "PlayStation 5 Slim", "Xbox Series X", "Nintendo Switch OLED", "Controle PS5 DualSense", "Headset Gamer HyperX",
    # Informática
    "Notebook Dell Inspiron", "MacBook Air M2", "SSD 1TB Kingston NV2", "Monitor Gamer 24 AOC", "Teclado Mecanico Redragon",
    # Eletroportáteis
    "Fritadeira Air Fryer Mondial 5L", "Cafeteira Nespresso Essenza", "Aspirador Robo WAP", "Liquidificador Osterizer",
    # Áudio
    "Apple AirPods Pro 2", "Fone Bluetooth JBL Tune 520", "Echo Dot 5ª Geração Alexa", "Caixa de Som JBL Flip 6",
    # Casa Inteligente
    "Fechadura Digital Intelbras", "Lampada Inteligente Positivo", "Camera de Seguranca Wi-Fi",
    # Fitness & Saúde
    "Creatina Monohidratada 300g Max Titanium", "Whey Protein 100% Growth", "Tenis Nike Revolution 7", "Smartwatch Galaxy Watch 6",
    # Beleza & Cuidado
    "Perfume Sauvage Dior", "Protetor Solar La Roche-Posay Anthelios", "Secador de Cabelo Taiff 2000W",
    # Ferramentas
    "Parafusadeira e Furadeira de Impacto Bosch", "Jogo de Ferramentas Tramontina 110 Pecas", "Lavadora de Alta Pressao Karcher"
]


def harvest_all_top_categories(db: Session, limit_per_term: int = 2) -> Dict[str, Any]:
    """Varre todos os termos semente de mercado e sincroniza o catálogo com a base local."""
    total_added = 0
    synced_titles = []

    for term in TOP_MARKET_SEEDS:
        try:
            prods = live_discovery.discover_and_import(term, db, max_items=limit_per_term)
            for p in prods:
                if p.title not in synced_titles:
                    synced_titles.append(p.title)
                    total_added += 1
        except Exception as e:
            logger.error(f"Erro ao colher termo '{term}': {e}")

    return {
        "status": "success",
        "total_synced_products": total_added,
        "sample_products": synced_titles[:10]
    }
