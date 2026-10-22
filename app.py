from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
SCHEDULE_PATH = BASE_DIR / "schedule.json"
with SCHEDULE_PATH.open("r", encoding="utf-8") as fh:
    SCHEDULE = json.load(fh)

MOSCOW = ZoneInfo("Europe/Moscow")
ANCHOR_MONDAY = date(2026, 9, 7)  # неделя, начинающаяся 7 сентября, размечена как верхняя
WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
WEEKDAY_ALIASES = {
    0: ["понедельник", "понед", "пн"],
    1: ["вторник", "втор", "вт"],
    2: ["среда", "среду", "сред", "ср"],
    3: ["четверг", "четвергу", "четв", "чт"],
    4: ["пятница", "пятницу", "пятн", "пт"],
    5: ["суббота", "субботу", "суб", "сб"],
    6: ["воскресенье", "воскресенье", "вс"],
}


def week_type_for(day: date) -> str:
    monday = day - timedelta(days=day.weekday())
    week_index = (monday - ANCHOR_MONDAY).days // 7
    return "upper" if week_index % 2 == 0 else "lower"


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def parse_weekday(text: str) -> int | None:
    padded = f" {text.lower()} "
    for idx, aliases in WEEKDAY_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![а-яё]){re.escape(alias)}(?![а-яё])", padded):
                return idx
    return None


def date_from_query(text: str, today: date) -> date:
    q = text.lower().replace("ё", "е")

    # Явная дата: 22.10 или 22.10.2026.
    match = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", q)
    if match:
        dd, mm, yyyy = match.groups()
        year = int(yyyy) if yyyy else today.year
        if year < 100:
            year += 2000
        try:
            return date(year, int(mm), int(dd))
        except ValueError:
            pass

    if "послезавтра" in q:
        return today + timedelta(days=2)
    if "завтра" in q:
        return today + timedelta(days=1)
    if "вчера" in q:
        return today - timedelta(days=1)

    requested_type = "upper" if "верх" in q else ("lower" if "ниж" in q else None)
    weekday = parse_weekday(q)
    if weekday is not None:
        if requested_type:
            target_monday = monday_of(today)
            if week_type_for(today) != requested_type:
                target_monday += timedelta(days=7)
            return target_monday + timedelta(days=weekday)
        offset = (weekday - today.weekday()) % 7
        return today + timedelta(days=offset)

    if requested_type:
        target_monday = monday_of(today)
        if week_type_for(today) != requested_type:
            target_monday += timedelta(days=7)
        return target_monday

    return today


def is_active(event: dict, day: date) -> bool:
    if event.get("day") != day.weekday():
        return False
    iso = day.isoformat()
    if "dates" in event:
        if iso not in event["dates"]:
            return False
    else:
        if day < date.fromisoformat(event["start_date"]) or day > date.fromisoformat(event["end_date"]):
            return False
    if event.get("week_type") and event["week_type"] != week_type_for(day):
        return False
    return True


def lessons_for(day: date, subgroup: str | None = None) -> list[dict]:
    result = [item for item in SCHEDULE if is_active(item, day)]
    if subgroup:
        result = [item for item in result if item.get("subgroup") in (None, subgroup)]
    return sorted(result, key=lambda x: (x["start"], x.get("subgroup", "0"), x["subject"]))


def format_date(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year} года"


def format_lesson(event: dict, compact: bool = False) -> str:
    label = f"{event['start']}–{event['end']}: {event['subject']}"
    if event.get("kind"):
        label += f" ({event['kind']})"
    if event.get("subgroup"):
        label += f", {event['subgroup']}-я подгруппа"
    if not compact:
        if event.get("room"):
            label += f"; {event['room']}"
        if event.get("address"):
            label += f", {event['address']}"
        if event.get("teacher"):
            label += f"; преподаватель — {event['teacher']}"
    return label


def day_reply(day: date, subgroup: str | None = None, compact: bool = False, first_only: bool = False) -> str:
    lessons = lessons_for(day, subgroup)
    heading = f"{WEEKDAYS[day.weekday()].capitalize()}, {format_date(day)}."
    if not lessons:
        return heading + " По загруженному расписанию занятий нет. Проверь актуальную версию на сайте РГГМУ: расписание может меняться."
    if first_only:
        first = lessons[0]
        return heading + f" Первая пара: {format_lesson(first, compact=True)}."
    lines = [heading]
    for event in lessons:
        lines.append(format_lesson(event, compact=compact) + ".")
    return " ".join(lines)


def full_week_reply(monday: date, subgroup: str | None = None) -> str:
    requested_type = "верхняя" if week_type_for(monday) == "upper" else "нижняя"
    chunks = [f"Расписание группы ПО-Б26 на {requested_type} неделю, начиная с {format_date(monday)}."]
    # Sunday intentionally omitted: regular timetable is laid out Monday–Saturday.
    for offset in range(6):
        day = monday + timedelta(days=offset)
        lessons = lessons_for(day, subgroup)
        if not lessons:
            chunks.append(f"{WEEKDAYS[offset].capitalize()}: занятий нет.")
            continue
        seen = set()
        compact_events = []
        for event in lessons:
            val = format_lesson(event, compact=True)
            if val not in seen:
                seen.add(val)
                compact_events.append(val)
        chunks.append(f"{WEEKDAYS[offset].capitalize()}: " + "; ".join(compact_events) + ".")
    chunks.append("Пары и аудитории могут измениться — перед выходом сверяйся с сайтом РГГМУ.")
    return " ".join(chunks)


def handle_alice_event(payload: dict) -> dict:
    req = payload.get("request") or {}
    utterance = (req.get("original_utterance") or req.get("command") or "").strip()
    q = utterance.lower().replace("ё", "е")
    today = datetime.now(MOSCOW).date()

    subgroup = None
    if re.search(r"(первая|1-я|1\s*подгруппа)", q):
        subgroup = "1"
    elif re.search(r"(вторая|2-я|2\s*подгруппа)", q):
        subgroup = "2"

    if not q or q in {"начать", "помощь", "что ты умеешь"}:
        answer = "Привет! Я подсказываю расписание группы ПО-Б26. Спроси: «Какое расписание сегодня?», «Какие пары завтра?» или «Расписание на верхнюю неделю». Для лабораторных могу показать занятия первой или второй подгруппы."
    else:
        weekday = parse_weekday(q)
        asks_full_week = "недел" in q and weekday is None and any(word in q for word in ("верх", "ниж", "всю", "вся", "все пары"))
        asks_all_week = ("всю неделю" in q or "на неделю" in q or "все дни недели" in q) and weekday is None
        if asks_full_week or asks_all_week:
            target = date_from_query(q, today)
            monday = monday_of(target)
            answer = full_week_reply(monday, subgroup)
        else:
            target = date_from_query(q, today)
            first_only = "первая пара" in q or "во сколько начинается первая" in q
            answer = day_reply(target, subgroup, first_only=first_only)
            if not any(word in q for word in ("распис", "пары", "занят", "какая пара", "какие пары", "во сколько", "урок")) and parse_weekday(q) is None:
                answer = "Я умею подсказывать расписание группы ПО-Б26. Спроси: «Какое расписание на сегодня?», «Что в четверг?» или «Расписание на верхнюю неделю»."

    return {
        "response": {"text": answer[:6000], "end_session": False},
        "version": "1.0"
    }


def application(environ, start_response):
    """Dependency-free WSGI entry point for Yandex Dialogs webhooks."""
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    if method == "GET":
        payload = {"status": "ok", "skill": "Расписание РГГМУ — ПО-Б26", "schedule_entries": len(SCHEDULE)}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]
    if method != "POST" or path not in ("/", ""):
        body = json.dumps({"error": "Not found"}, ensure_ascii=False).encode("utf-8")
        start_response("404 Not Found", [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
        return [body]
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
        raw = environ["wsgi.input"].read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(payload, dict):
            payload = {}
        result = handle_alice_event(payload)
        status = "200 OK"
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        result = {"response": {"text": "Не удалось прочитать запрос. Спроси: «Какое расписание на сегодня?». ", "end_session": False}, "version": "1.0"}
        status = "200 OK"
    body = json.dumps(result, ensure_ascii=False).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


# Gunicorn-compatible application object; no third-party runtime dependency is required.
app = application


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    port = int(os.getenv("PORT", "8080"))
    with make_server("0.0.0.0", port, application) as server:
        print(f"Schedule skill webhook listening on http://127.0.0.1:{port}/")
        server.serve_forever()
