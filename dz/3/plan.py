"""Сохраняет план выполнения запроса в JSON-файл.

Запрос задаётся прямо в этом файле, а не через аргументы командной строки.
Поэтому кавычки, фигурные скобки и знак $ не проходят через оболочку, и
команда запуска одинаково работает в PowerShell, cmd.exe, Терминале macOS
и Linux.

    docker compose run --rm python work/praktikum-explain/plan.py
    docker compose run --rm python work/praktikum-explain/plan.py plan-2.json

Имя файла можно передать одним словом в конце команды — кавычки ему не
нужны. Если имя не передано, используется значение из DEFAULT_FILE.

Скрипт не создаёт и не удаляет индексы: он снимает план того состояния
коллекции, которое вы подготовили в оболочке или в Compass.
"""

import json
import sys
from pathlib import Path

from bson.json_util import RELAXED_JSON_OPTIONS, dumps
from pymongo import MongoClient

DB_NAME = "logs"
COLLECTION_NAME = "events"

# Тот же документ, что вы пишете в find({...}).
QUERY_FILTER = {
    "level": "error"
}

# Поле и направление сортировки: 1 — по возрастанию, -1 — по убыванию.
SORT_SPEC = [("duration_ms", -1)]

# Сколько документов вернуть. 0 — без ограничения.
LIMIT = 10

# Имя файла по умолчанию. Файл кладётся рядом со скриптом.
DEFAULT_FILE = "plan-1.json"

# ─────────────────────────────────────────────────────────────────────────
#  Ниже — служебная часть, менять её не требуется.
# ─────────────────────────────────────────────────────────────────────────


def fail(message):
    """Напечатать сообщение об ошибке в stderr и выйти с кодом 2."""
    print(message, file=sys.stderr)
    sys.exit(2)


def stage_chain(stage):
    """Собрать имена шагов плана от нижнего к верхнему, как у визуализатора."""
    names = []
    while stage:
        names.append(stage["stage"])
        stage = stage.get("inputStage")
    return names[::-1]


def parse_target(argv):
    """Вернуть имя выходного файла: из argv[1] или DEFAULT_FILE."""
    name = argv[1] if len(argv) > 1 else DEFAULT_FILE
    if not name.endswith(".json"):
        fail("Имя файла должно оканчиваться на .json, например plan-2.json")
    return name


def connect():
    """Подключиться к серверу, проверив доступность через ping."""
    cli = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    try:
        cli.admin.command("ping")
    except Exception:
        fail(
            "Сервер не отвечает. Поднимите стенд:  docker compose up -d\n"
            "и залейте данные:                     docker compose run --rm reset"
        )
    return cli


def get_collection(cli):
    """Вернуть коллекцию и убедиться, что она не пуста."""
    coll = cli[DB_NAME][COLLECTION_NAME]
    count = coll.count_documents({})
    if count == 0:
        fail("Коллекция %s.%s пуста. Данные: docker compose run --rm reset"
             % (DB_NAME, COLLECTION_NAME))
    return coll, count


def build_cursor(coll):
    """Собрать курсор с учётом фильтра, сортировки и предела."""
    cur = coll.find(QUERY_FILTER)
    if SORT_SPEC:
        cur = cur.sort(SORT_SPEC)
    if LIMIT:
        cur = cur.limit(LIMIT)
    return cur


def write_plan(plan, target):
    """Записать план в файл рядом со скриптом в формате, понятном визуализатору."""
    path = Path(__file__).resolve().parent / target
    # dumps из bson корректно сериализует даты и числовые типы BSON.
    path.write_text(dumps(plan, json_options=RELAXED_JSON_OPTIONS), encoding="utf-8")
    return path


def print_report(path, stats, indexes, total_docs):
    """Напечатать сводку: параметры запроса, статистику и список индексов."""
    steps = " → ".join(stage_chain(stats["executionStages"]))
    index_names = ", ".join(i["name"] for i in indexes)

    print("Запрос к %s.%s, всего документов в коллекции: %d"
          % (DB_NAME, COLLECTION_NAME, total_docs))
    print("  фильтр:                 %s" % json.dumps(QUERY_FILTER, ensure_ascii=False))
    print("  сортировка:             %s" % (SORT_SPEC or "нет"))
    print("  предел:                 %s" % (LIMIT or "нет"))
    print()
    print("  файл с планом:          %s" % path.name)
    print("  возвращено:             %d" % stats["nReturned"])
    print("  документов просмотрено: %d" % stats["totalDocsExamined"])
    print("  ключей просмотрено:     %d" % stats["totalKeysExamined"])
    print("  шаги плана:             %s" % steps)
    print("  индексы коллекции:      %s" % index_names)


def main():
    target = parse_target(sys.argv)
    cli = connect()
    coll, total_docs = get_collection(cli)

    plan = build_cursor(coll).explain()
    stats = plan["executionStats"]

    path = write_plan(plan, target)
    print_report(path, stats, coll.list_indexes(), total_docs)


if __name__ == "__main__":
    main()