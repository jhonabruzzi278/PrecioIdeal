import logging
import re
from functools import lru_cache
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://knasta.cl"
LOCALE = "es"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-CL,es;q=0.9",
}


@lru_cache(maxsize=1)
def get_flat_categories():
    return KnastaScraper().flatten_categories()


class KnastaScraper:
    def __init__(self):
        self._build_id = None

    def fetch_build_id(self):
        if self._build_id:
            return self._build_id
        response = requests.get(BASE_URL, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        match = re.search(r'"buildId":"([^"]+)"', response.text)
        if not match:
            raise RuntimeError("No se pudo obtener buildId de Knasta")
        self._build_id = match.group(1)
        return self._build_id

    def fetch_categories(self):
        response = requests.get(
            f"{BASE_URL}/api/categories",
            headers=DEFAULT_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("categories_tree", {})

    def flatten_categories(self, node=None, results=None):
        if results is None:
            results = []
        if node is None:
            node = self.fetch_categories()
        children = node.get("children") or []
        if not children:
            if node.get("category_id") and node.get("category_id") != "0":
                results.append(
                    {
                        "category_id": node["category_id"],
                        "category_name": node.get("category_name", ""),
                        "long_path": node.get("long_path", ""),
                        "slug": node.get("slug", ""),
                    }
                )
            return results
        for child in children:
            if not child.get("children"):
                if child.get("category_id"):
                    results.append(
                        {
                            "category_id": child["category_id"],
                            "category_name": child.get("category_name", ""),
                            "long_path": child.get("long_path", ""),
                            "slug": child.get("slug", ""),
                        }
                    )
            else:
                self.flatten_categories(child, results)
        return sorted(results, key=lambda item: item["long_path"].lower())

    def fetch_results(self, category_slug, page=1):
        build_id = self.fetch_build_id()
        slug_parts = [part for part in category_slug.split("/") if part]
        path = "/".join(slug_parts)
        url = f"{BASE_URL}/_next/data/{build_id}/{LOCALE}/results/{path}.json"
        params = [("slug", part) for part in slug_parts]
        if page > 1:
            params.append(("page", str(page)))
        response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("pageProps", {}).get("initialData", {})

    def get_total_pages(self, data):
        return min(data.get("total_pages", 1) or 1, 100)

    def parse_products(self, data):
        return data.get("products", []) or []

    def extract_pricing(self, product):
        from products.services.pricing import compute_knasta_pricing

        return compute_knasta_pricing(
            product.get("current_price"),
            product.get("last_variation_price"),
            product.get("price_internet"),
            product.get("price_card"),
            product.get("percent"),
        )

    def scrape_category(self, category_slug, progress_callback=None):
        seen_kids = set()
        consolidated = []

        if progress_callback:
            progress_callback(0, 1, "Conectando con Knasta...")

        first_data = self.fetch_results(category_slug, page=1)
        if not first_data:
            logger.warning("Sin datos para categoría %s", category_slug)
            return []

        total_pages = self.get_total_pages(first_data)
        logger.info("Categoría %s: %s páginas detectadas", category_slug, total_pages)

        for page in range(1, total_pages + 1):
            if progress_callback:
                progress_callback(
                    page,
                    total_pages,
                    f"Descargando página {page} de {total_pages}...",
                )
            data = first_data if page == 1 else self.fetch_results(category_slug, page=page)
            if not data:
                continue

            for raw_product in self.parse_products(data):
                normalized = self._normalize_product(raw_product)
                if not normalized:
                    continue
                kid = normalized["kid"]
                if kid in seen_kids:
                    continue
                seen_kids.add(kid)
                consolidated.append(normalized)

        return consolidated

    def _normalize_product(self, product):
        kid = product.get("kid")
        if not kid:
            return None

        pricing = self.extract_pricing(product)
        rating = product.get("rating_average")
        if rating is not None:
            try:
                rating = float(rating)
            except (TypeError, ValueError):
                rating = None

        reviews = product.get("rating_total") or 0
        try:
            reviews = int(reviews)
        except (TypeError, ValueError):
            reviews = 0

        return {
            "kid": str(kid),
            "product_id": str(product.get("product_id") or kid),
            "name": product.get("title") or "Sin nombre",
            "brand": product.get("brand") or "",
            "retail": product.get("retail") or "",
            "seller": product.get("retail_label") or "",
            "product_url": product.get("url") or "",
            "image_url": product.get("image") or product.get("thumbnail_image") or "",
            "rating": rating,
            "reviews": reviews,
            "price_best": pricing["price_best"],
            "price_internet": product.get("price_internet"),
            "price_card": product.get("price_card"),
            "reference_price": product.get("last_variation_price"),
            "best_variation_price": product.get("best_variation_price"),
            "discount_percent": pricing["discount_percent"],
            "discount_amount": pricing["discount_amount"],
            "is_best_price": bool(product.get("is_best_price")),
            "source": "knasta",
        }

    @staticmethod
    def results_url(category_slug):
        slug_parts = [part for part in category_slug.split("/") if part]
        query = urlencode([("slug", part) for part in slug_parts])
        return f"{BASE_URL}/results/{'/'.join(slug_parts)}?{query}"


@lru_cache(maxsize=1)
def get_flat_categories():
    return KnastaScraper().flatten_categories()
