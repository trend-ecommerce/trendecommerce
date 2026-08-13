from datetime import datetime


class DataTransformer:
    @staticmethod
    def transform_ml_item(item: dict, site_id: str = "MLB") -> dict:
        """Transforms a raw Mercado Livre item dictionary into database entities."""
        category_id = item.get("category_id") or "MLB_GENERAL"
        product_id = item.get("id")
        title = item.get("title", "")
        permalink = item.get("permalink", "")
        price = float(item.get("price", 0.0))
        original_price = float(item.get("original_price")) if item.get("original_price") is not None else price
        currency_id = item.get("currency_id", "BRL")
        available_quantity = int(item.get("available_quantity", 0))

        seller = item.get("seller", {})
        seller_id = str(seller.get("id")) if isinstance(seller, dict) and seller.get("id") else None

        attributes = item.get("attributes", [])
        brand = None
        if isinstance(attributes, list):
            for attr in attributes:
                if isinstance(attr, dict) and attr.get("id") == "BRAND":
                    brand = attr.get("value_name")
                    break

        product_dim = {
            "product_id": product_id,
            "site_id": site_id,
            "title": title,
            "category_id": category_id,
            "brand": brand,
            "seller_id": seller_id,
            "permalink": permalink,
            "currency_id": currency_id
        }

        price_entry = {
            "product_id": product_id,
            "price": price,
            "original_price": original_price,
            "currency_id": currency_id,
            "available_quantity": available_quantity,
            "collected_at": datetime.utcnow()
        }

        return {
            "product": product_dim,
            "price_history": price_entry
        }

    @staticmethod
    def transform_amazon_item(item: dict) -> dict:
        """Transforms a raw Amazon SP-API catalog item into database entities."""
        asin = item.get("asin")
        summaries = item.get("summaries", [])
        title = summaries[0].get("itemName", asin) if summaries and isinstance(summaries, list) else asin

        brand = None
        if summaries and isinstance(summaries, list) and "brand" in summaries[0]:
            brand = summaries[0].get("brand")

        product_dim = {
            "product_id": asin,
            "site_id": "AMAZON_US",
            "title": title,
            "category_id": "AMAZON_GENERAL",
            "brand": brand,
            "seller_id": "AMAZON",
            "permalink": f"https://www.amazon.com/dp/{asin}",
            "currency_id": "USD"
        }

        price_entry = {
            "product_id": asin,
            "price": 0.0,
            "original_price": 0.0,
            "currency_id": "USD",
            "available_quantity": 1,
            "collected_at": datetime.utcnow()
        }

        return {
            "product": product_dim,
            "price_history": price_entry
        }
