import os
import json
from datetime import datetime, timezone
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://192.168.0.222:27017/"))
db = client["sandbox"]

with open("stocktake.json", encoding="utf-8") as f:
    stocktake = json.load(f)
for item in stocktake:
    item["_id"] = item["sku"]
try:
    db.stocktake.insert_many(stocktake, ordered=False)
    print("Пересчет загружен")
except BulkWriteError:
    print("Пересчет уже был загружен")

warehouse = list(db.warehouse.find({}, {"sku":1, "qty_accounted":1}))
counted = {i["sku"]: i["counted"] for i in stocktake}

matches = [w for w in warehouse if counted.get(w["sku"]) == w["qty_accounted"]]
shorts = [w for w in warehouse if counted.get(w["sku"], w["qty_accounted"]) < w["qty_accounted"]]
overs = [w for w in warehouse if counted.get(w["sku"], w["qty_accounted"]) > w["qty_accounted"]]

print(f"Сошлось: {len(matches)}, Недостача: {len(shorts)}, Излишек: {len(overs)}")

ops = [UpdateOne({"sku": w["sku"]}, {"$set": {"qty_accounted": counted[w["sku"]], "last_stocktake": datetime.now(timezone.utc)}}) 
       for w in warehouse if counted.get(w["sku"]) is not None and w["sku"] not in [m["sku"] for m in matches]]
if ops:
    print(f"Обновлено учетных остатков: {db.warehouse.bulk_write(ops).modified_count}")

zero_skus = [sku for sku, count in counted.items() if count == 0]
if zero_skus:
    print(f"Помечено пустых полок: {db.warehouse.update_many({'sku': {'$in': zero_skus}}, {'$set': {'available': False}}).modified_count}")
    db.warehouse.update_many({"sku": {"$nin": zero_skus}}, {"$unset": {"available": ""}})

date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
log = {
    "date": date_str, "positions": len(warehouse), "mismatches": len(shorts) + len(overs),
    "shortage_qty": sum(w["qty_accounted"] - counted[w["sku"]] for w in shorts)
}
db.stocktake_log.update_one({"date": date_str}, {"$set": log}, upsert=True)
print("Журнал обновлен")