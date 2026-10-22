import pytest
from src.collectors.live_tracker import LiveTracker
from src.database.connection import DatabaseManager
from src.database.models import Base, Product, SalesHistory


@pytest.fixture
def temp_db(tmp_path):
    """Banco temporário para testar LiveTracker."""
    db_file = tmp_path / "test_tracker.db"
    manager = DatabaseManager(database_url=f"sqlite:///{db_file}")
    Base.metadata.create_all(manager.engine)
    return manager


class TestLiveTracker:
    """Testes do LiveTracker."""

    def test_sync_products_to_db(self, temp_db):
        """Verifica sincronização de produtos e criação de histórico no banco."""
        tracker = LiveTracker(db_manager=temp_db)
        
        mock_items = [
            {
                "product_id": "MLB999111",
                "title": "Produto Teste ML",
                "price": 199.90,
                "currency": "BRL",
                "category_id": "MLB123",
                "sold_quantity": 80,
                "available_quantity": 25,
                "condition": "new",
                "permalink": "https://mercadolivre.com/test",
            }
        ]
        
        saved = tracker.sync_products_to_db(mock_items, days_history=30)
        assert len(saved) == 1
        
        with temp_db.session() as session:
            p = session.query(Product).filter_by(external_id="MLB999111").first()
            assert p is not None
            assert p.title == "Produto Teste ML"
            
            sales_count = session.query(SalesHistory).filter_by(product_id=p.id).count()
            assert sales_count == 30

    def test_record_daily_snapshot(self, temp_db):
        """Verifica gravação de snapshot diário e cálculo de delta."""
        tracker = LiveTracker(db_manager=temp_db)
        
        # Inserir produto base
        mock_items = [
            {
                "product_id": "MLB888222",
                "title": "Produto Snapshot Teste",
                "price": 50.0,
                "sold_quantity": 100,
                "available_quantity": 50,
            }
        ]
        tracker.sync_products_to_db(mock_items, days_history=5)
        
        with temp_db.session() as session:
            p = session.query(Product).filter_by(external_id="MLB888222").first()
            prod_id = p.id
            
        delta = tracker.record_daily_snapshot(
            product_id=prod_id,
            current_sold_quantity=110,
            price=50.0
        )
        
        assert delta is not None
        assert delta >= 0