"""Script de Sincronização Massiva de Catálogo (Amazon & Mercado Livre).

Varre automaticamente as principais categorias do mercado e importa centenas
de produtos com históricos de vendas de 90 dias para a base preditiva do XGBoost.

Uso:
    python sync_categories.py
    python sync_categories.py --limit 3
"""

import sys
import argparse
from pathlib import Path

# Configurar encoding utf-8 para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.database.setup import get_db_manager
from src.collectors.category_harvester import harvest_all_top_categories


def main():
    parser = argparse.ArgumentParser(description="Sincronizador Massivo de Catálogo E-Commerce")
    parser.add_argument("--limit", type=int, default=2, help="Limite de variações por termo de busca")
    args = parser.parse_args()

    print("================================================================================")
    print("      🚀 TRENDCOMMERCE AI — SINCRONIZADOR MASSIVO DE CATÁLOGO MULTI-CANAL")
    print("      Importação Automática em Tempo Real (Amazon & Mercado Livre)")
    print("================================================================================\n")

    db_manager = get_db_manager()
    with db_manager.session() as session:
        print(f"📡 Iniciando varredura das principais categorias (limite: {args.limit} por termo)...")
        result = harvest_all_top_categories(session, limit_per_term=args.limit)
        
        print("\n✅ SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"📦 Total de Produtos Processados no Catálogo: {result['total_synced_products']}")
        print("\n📋 Amostra de Produtos Sincronizados:")
        for idx, title in enumerate(result['sample_products'], 1):
            print(f"  {idx:2d}. {title}")

    print("\n💡 Todos os produtos já estão disponíveis para predições de 7, 14 e 30 dias com XGBoost!")
    print("================================================================================")


if __name__ == "__main__":
    main()
