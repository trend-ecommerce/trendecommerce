"""Endpoints de gerenciamento e consulta de produtos."""

from fastapi import APIRouter
from src.database.setup import get_db_manager
from src.database.models import Product

router = APIRouter()


@router.get("/", summary="Listar Produtos Cadastrados")
def list_products():
    manager = get_db_manager()
    with manager.session() as session:
        products = session.query(Product).filter(Product.is_active == True).all()
        return [
            {
                "id": p.id,
                "title": p.title,
                "category": p.category,
                "price": p.price,
                "platform": p.platform
            }
            for p in products
        ]