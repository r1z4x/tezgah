"""Write the nightly stock feed for the warehouse (format: docs/FEED.md)."""
import json
from pathlib import Path

PRODUCTS = Path(__file__).resolve().parent.parent / "data" / "products.json"


def load_products(path=PRODUCTS):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def escape(field):
    return field.replace("\\", "\\\\").replace("|", "\\|")


def feed_line(product):
    return "%s|%d|%d|%s" % (escape(product["sku"]), product["qty"],
                            product["price_cents"], escape(product.get("name", "")))


def write_feed(products):
    return "".join(feed_line(p) + "\n" for p in products)
