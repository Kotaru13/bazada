import os
from pymongo import MongoClient
from pymongo.errors import BulkWriteError


MONGO = os.environ.get("MONGO_URI", "mongodb://192.168.0.222:27017/")
db = MongoClient(MONGO)
catalog = db["shop"]["products"]
work = db["sandbox"]["products"]

PAGE_FIELDS = {"_id": 0, "sku": 1, "title": 1, "price": 1, "rating": 1}



def fetch_page(category=None, page=1, per_page=5,
               sort_field="price", desc=True):
    """Вернуть (документы страницы, общее число подходящих документов)."""
    flt = {"category": category} if category else {}
    total = catalog.count_documents(flt)
    order = [(sort_field, -1 if desc else 1), ("sku", 1)]
    docs = (catalog
            .find(flt, PAGE_FIELDS)
            .sort(order)
            .skip((page - 1) * per_page)
            .limit(per_page))
    return list(docs), total


def print_rows(rows, with_rating=True):
    for row in rows:
        line = f"  {row['price']:>7} ₽  {row['title']:<32}"
        if with_rating:
            line += f" рейтинг {row['rating']}"
        print(line)


def show_catalog():
    print("=" * 62)
    print("ЗАДАЧА 1 · витрина каталога")
    print("=" * 62)

    laptops, laptops_total = fetch_page(category="ноутбуки", per_page=3)
    pages = (laptops_total + 2) // 3
    print(f"\nНоутбуки, страница 1 из {pages} (всего {laptops_total}):")
    print_rows(laptops)

    laptops2, _ = fetch_page(category="ноутбуки", page=2, per_page=3)
    print("\nСтраница 2:")
    print_rows(laptops2)

    top5, all_total = fetch_page(per_page=5)
    print(f"\nВесь каталог, топ-5 по цене (всего {all_total}):")
    print_rows(top5, with_rating=False)

    empty, still_total = fetch_page(category="ноутбуки", page=9, per_page=3)
    print(f"\nСтраница 9 из существующих {pages}: найдено {len(empty)} товаров, "
          f"total по-прежнему {still_total}")
    return all_total



DELIVERY = {
    "SKU-NB-001": 5,
    "SKU-PH-006": 12,
    "SKU-PR-010": 3,
}

FRESH_ITEMS = [
    {"_id": "p-101", "sku": "SKU-AC-101", "title": "Подставка для ноутбука",
     "brand": "OEM", "category": "аксессуары", "price": 2490, "reviews": 0},
    {"_id": "p-102", "sku": "SKU-AC-102", "title": "Чехол для планшета",
     "brand": "OEM", "category": "аксессуары", "price": 1890, "reviews": 0},
]

RETIRED_SKUS = ["SKU-CP-018"]


def apply_delivery(rows):
    """Прибавить количества из поставки к qty_total. Вернуть число изменённых."""
    changed = 0
    for sku, amount in rows.items():
        res = work.update_one({"sku": sku}, {"$inc": {"qty_total": amount}})
        if res.matched_count == 0:
            print(f"  ВНИМАНИЕ: артикул {sku} не найден в каталоге")
        changed += res.modified_count
    return changed


def insert_fresh(items):
    """Вставить новинки, пропуская уже существующие. Вернуть число добавленных."""
    try:
        res = work.insert_many(items, ordered=False)
        return len(res.inserted_ids)
    except BulkWriteError as err:
        skipped = len(err.details["writeErrors"])
        print(f"  {skipped} позиций уже были в каталоге — пропущены")
        return len(items) - skipped


def retire(skus):
    """Удалить снятые с продажи артикулы, показав, что попадает под удаление."""
    flt = {"sku": {"$in": skus}}
    hit = work.count_documents(flt)
    print(f"\n  под снятие с продажи попало: {hit}")
    for doc in work.find(flt, {"_id": 1, "title": 1, "price": 1}):
        print(f"    {doc}")
    return work.delete_many(flt).deleted_count


def enable_free_shipping(category):
    """Проставить free_shipping всем товарам категории. Вернуть число изменённых."""
    flt = {"category": category}
    print(f"\n  бесплатная доставка коснётся: {work.count_documents(flt)} товаров")
    return work.update_many(flt, {"$set": {"free_shipping": True}}).modified_count


def receive_supply():
    print("\n" + "=" * 62)
    print("ЗАДАЧА 2 · приёмка поставки")
    print("=" * 62)

    summary = {
        "остатки обновлены": apply_delivery(DELIVERY),
        "новых позиций": insert_fresh(FRESH_ITEMS),
        "снято с продажи": retire(RETIRED_SKUS),
        "бесплатная доставка": enable_free_shipping("аксессуары"),
    }
    summary["итого в каталоге"] = work.count_documents({})

    print("\nОтчёт о приёмке:")
    for name, value in summary.items():
        print(f"  {name:<24} {value}")
    return summary


if __name__ == "__main__":
    show_catalog()
    receive_supply()
    db.close()