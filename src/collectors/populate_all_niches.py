"""Script de Ingestão e Sincronização Multi-Nicho — TrendCommerce AI.

Coleta produtos reais de 10 grandes nichos do e-commerce (Mercado Livre e Amazon)
e popula o banco de dados PostgreSQL/SQLite com histórico calibrado de 90 dias
para treinamento e inferência multi-categoria no XGBoost.

Uso:
    python -m src.collectors.populate_all_niches
"""

import sys
import logging
from pathlib import Path

# Adicionar raiz do projeto ao path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


from src.database.connection import DatabaseManager
from src.collectors.live_tracker import LiveTracker
from src.database.models import Product, SalesHistory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Catálogo completo de 10 grandes nichos do mercado com termos de alta busca:
NICHES_CATALOG = {
    "Moda & Vestuário": [
        "tenis corrida masculino",
        "vestido midi feminino",
        "jaqueta corta vento impermeavel",
        "camisa social manga longa"
    ],
    "Beleza & Cuidados Pessoais": [
        "protetor solar facial la roche fps 60",
        "perfume importado masculino 100ml",
        "serum facial vitamina c",
        "secador de cabelo profissional 2000w"
    ],
    "Esportes & Suplementos": [
        "whey protein 100 isolado 900g",
        "creatina monohidratada 300g",
        "kit elasticos extensores musculacao",
        "tapete yoga mat antiderrapante"
    ],
    "Casa & Eletrodomésticos": [
        "fritadeira eletrica airfryer 4l",
        "aspirador de po robo bivolt",
        "cafeteira expresso capsula",
        "liquidificador 1200w jarra vidro"
    ],
    "Móveis & Decoração": [
        "cadeira de escritorio ergonomica presidente",
        "mesa home office computador 120cm",
        "luminaria articulada de mesa led",
        "jogo de lencol 400 fios casal"
    ],
    "Brinquedos & Hobbies": [
        "lego classic caixa blocos de montar",
        "jogo de tabuleiro catan",
        "boneco colecionavel funko pop",
        "patinete infantil 3 rodas com led"
    ],
    "Ferramentas & Construção": [
        "parafusadeira furadeira impacto bateria",
        "maleta ferramentas completa 110 pecas",
        "trena a laser digital 40m",
        "serra tico tico 600w"
    ],
    "Alimentos & Bebidas": [
        "capsulas cafe espresso compativeis",
        "azeite de oliva extra virgem 500ml",
        "vinho tinto chileno reserva",
        "chocolate belga 70 cacau"
    ],
    "Automotivo": [
        "suporte celular veicular magsafe",
        "compressor de ar portatil digital 12v",
        "camera de re com sensor de estacionamento",
        "oleo motor 5w30 sintetico"
    ],
    "Informática & Eletrônicos": [
        "notebook dell 16gb ram ssd 512gb",
        "iphone 15 pro 128gb",
        "monitor gamer 27 144hz 1ms",
        "fone de ouvido bluetooth noise cancelling"
    ]
}


def populate_all_niches(limit_per_term: int = 2, days_history: int = 90):
    """Executa a coleta multi-nicho e sincroniza no banco de dados."""
    print("\n" + "=" * 80)
    print("      🌐 TRENDCOMMERCE AI — INGESTÃO MULTI-NICHO DE PRODUTOS REAIS")
    print("        Sincronizando 10 Categorias de E-commerce (Mercado Livre & Amazon)")
    print("=" * 80 + "\n")

    db = DatabaseManager()
    db.create_tables()
    tracker = LiveTracker(db_manager=db)

    total_products_synced = 0
    total_sales_records = 0

    for niche_name, search_terms in NICHES_CATALOG.items():
        print(f"\n📁 [NICHO: {niche_name.upper()}]")
        niche_count = 0

        for term in search_terms:
            try:
                # 1. Coletar produtos reais da API
                items = tracker.fetch_real_products(query=term, limit=limit_per_term)
                if not items:
                    continue

                # Atribuir a categoria unificada
                for item in items:
                    item["category_id"] = niche_name

                # 2. Sincronizar com banco de dados e gerar histórico de 90 dias
                saved = tracker.sync_products_to_db(items, days_history=days_history)
                niche_count += len(saved)
                total_products_synced += len(saved)
                total_sales_records += len(saved) * days_history

                print(f"   ✓ '{term}' → {len(saved)} produtos adicionados.")
            except Exception as e:
                logger.warning(f"Erro na coleta do termo '{term}': {e}")

        print(f"   📊 Subtotal do nicho {niche_name}: {niche_count} produtos cadastrados.")

    print("\n" + "=" * 80)
    print(f"🎉 INGESTÃO CONCLUÍDA COM SUCESSO!")
    print(f"   • Total de Nichos Processados: {len(NICHES_CATALOG)}")
    print(f"   • Total de Produtos Ativos no Catálogo: {total_products_synced}")
    print(f"   • Registros Históricos de Vendas Gerados: ~{total_sales_records}")
    print("=" * 80)
    print("\n💡 Próximos passos:")
    print("   1. Treine e gere previsões para todos os nichos: python run_prediction.py --days 14")
    print("   2. Ou acesse a interface web em: http://localhost:8000/app/index.html\n")


if __name__ == "__main__":
    populate_all_niches(limit_per_term=2, days_history=90)
