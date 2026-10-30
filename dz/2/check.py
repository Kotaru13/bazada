

Проверяется не код, а итоговое состояние базы после приёмки поставки.
Именно так работу принимают и в реальной практике — по данным,
а не по исходнику решения.

Порядок запуска:
    bash ../stend/load.sh     # чистые данные
    python3 solution.py       # решение
    python3 check.py          # эта проверка

Каждая строка отчёта соответствует отдельному требованию задания.
"""

import os
import sys
from pymongo import MongoClient

MONGO = os.environ.get("MONGO_URI", "mongodb://192.168.0.222:27017/")
db = MongoClient(MONGO)
shop = db["shop"]["products"]
work = db["sandbox"]["products"]

assertions = []


def assert_eq(name, actual, expected):
    ok = actual == expected
    assertions.append(ok)
    marker = "✓" if ok else "✗"
    if ok:
        print(f" {marker} {name:<46} {actual!r}")
    else:
        print(f" {marker} {name:<46} {actual!r}   ← ожидалось {expected!r}")


def top_by_price(collection, field):
    """Вернуть значение поля field у самого дорогого документа."""
    doc = collection.find({}, {"_id": 0, field: 1}).sort("price", -1).limit(1)
    return next(doc)[field]


def qty_of(collection, sku):
    """Вернуть qty_total для указанного SKU (или None)."""
    return (collection.find_one({"sku": sku}) or {}).get("qty_total")


# --- Задача 1: витрина каталога ---
print("Задача 1 · витрина каталога")
assert_eq("товаров в каталоге shop.products", shop.count_documents({}), 21)
assert_eq("ноутбуков", shop.count_documents({"category": "ноутбуки"}), 5)
assert_eq("самый дорогой товар", top_by_price(shop, "title"),
          "Ноутбук Apple MacBook Air 13")

# --- Задача 2: приёмка поставки ---
print("\nЗадача 2 · приёмка поставки")
assert_eq("всего позиций в песочнице", work.count_documents({}), 22)
assert_eq("новинка p-101 заведена", work.count_documents({"_id": "p-101"}), 1)
assert_eq("новинка p-102 заведена", work.count_documents({"_id": "p-102"}), 1)
assert_eq("снятый с продажи SKU-CP-018 удалён",
          work.count_documents({"sku": "SKU-CP-018"}), 0)
assert_eq("бесплатная доставка у аксессуаров",
          work.count_documents({"category": "аксессуары",
                                "free_shipping": True}), 5)
assert_eq("остаток по SKU-NB-001", qty_of(work, "SKU-NB-001"), 5)
assert_eq("остаток по SKU-PH-006", qty_of(work, "SKU-PH-006"), 12)
assert_eq("остаток по SKU-PR-010", qty_of(work, "SKU-PR-010"), 3)
assert_eq("эталонная база shop не тронута",
          shop.count_documents({"free_shipping": True}), 0)

ok_count = sum(assertions)
all_count = len(assertions)
print(f"\nПройдено {ok_count} из {all_count}")
if ok_count != all_count:
    print("Данные разъехались? Начните заново: bash ../stend/load.sh")
db.close()
sys.exit(0 if ok_count == all_count else 1)