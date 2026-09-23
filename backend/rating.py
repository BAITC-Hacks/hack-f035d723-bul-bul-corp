from __future__ import annotations

import re

from .schemas import Rating, RatingCategory, TaskFields


# Simple fields score for non-whitespace text, not length or inferred quality.
# Compound weights are explicit: context/need 10 each, contact/consultation 5 each.
RULES = (
    ("context_need", "Контекст и потребность", (("context", 10), ("need", 10))),
    ("data_materials", "Данные и материалы", (("data_materials", 20),)),
    ("expected_result", "Ожидаемый результат", (("expected_result", 15),)),
    ("success_criteria", "Измеримые критерии успеха", (("success_criteria", 15),)),
    ("constraints", "Ограничения", (("constraints", 10),)),
    ("users", "Пользователи", (("users", 10),)),
    ("contact_consultation", "Контакт, консультации и обратная связь", (("contact", 5), ("consultation", 5))),
)

FIELD_LABELS = {
    "context": "Контекст",
    "need": "Потребность",
    "data_materials": "Данные и материалы",
    "expected_result": "Ожидаемый результат",
    "success_criteria": "Критерии успеха",
    "constraints": "Ограничения",
    "users": "Пользователи",
    "contact": "Контакт",
    "consultation": "Консультации и обратная связь",
}

# Finite lexical rules, not semantic validation. A number alone, KPI identifier,
# date, version, or bare duration is not an acceptance criterion.
NUMBER = r"(?<![\w.,/-])\d+(?:[.,]\d+)?"
DURATION = r"(?:секунд(?:а|ы|у)?|минут(?:а|ы|у)?|час(?:а|ов)?|день|дня|дней|недел(?:я|и|ю|ь)|месяц(?:а|ев)?|seconds?|minutes?|hours?|days?|weeks?|months?|ms|мс)\b"
PERCENT = r"%(?!\w)"
CURRENCY = r"(?:₽|\$|руб(?:лей|ля|ль)?\b\.?|usd\b|eur\b)"
RATE_METRIC = r"(?:точност[ьи]|конверси[яию]|доля|процент|ошиб(?:ок|ки|ка)|accuracy|conversion|error rate)"
TIME_METRIC = r"(?:latency|response time|processing time|время (?:ответа|обработки)|скорость обработки)"
MONEY_METRIC = r"(?:выручк[аиу]|стоимост[ьи]|затрат[ыа]?|расход(?:ы|ов)?|revenue|costs?)"
BOUND = r"(?:не (?:менее|более|ниже|выше)|как минимум|как максимум|минимум|максимум|до|от|на|менее|более|ниже|выше|составляет|at least|at most|no more than|no less than|under|over|below|above|within|of|is|to|by|>=|<=|>|<|=|≥|≤)"
TARGET_NUMBER = rf"\s*:?\s*(?:{BOUND}\s*)?{NUMBER}\s*"
METRIC_TARGET = re.compile(
    rf"\b(?:{RATE_METRIC}{TARGET_NUMBER}{PERCENT}|"
    rf"{TIME_METRIC}{TARGET_NUMBER}(?:{DURATION}|{PERCENT})|"
    rf"{MONEY_METRIC}{TARGET_NUMBER}(?:{CURRENCY}|{PERCENT}))",
    re.IGNORECASE,
)
COUNT_TARGET = re.compile(
    rf"{NUMBER}\s+(?:заяв(?:ок|ки|ка)|заказ(?:ов|а)?|клиент(?:ов|а)?|"
    r"пользовател(?:ей|я|ь)|лид(?:ов|а)?|ошиб(?:ок|ки|ка)|документ(?:ов|а)?|"
    r"запис(?:ей|и|ь)|тест(?:ов|а)?|запрос(?:ов|а)?|"
    r"applications?|orders?|customers?|users?|leads?|errors?|documents?|records?|tests?|requests?|tickets?)\b",
    re.IGNORECASE,
)
DELIVERABLE = r"(?:прототип(?:а|ы|ов)?|отч[её]т(?:а|ы|ов)?|дашборд(?:а|ы|ов)?|сервис(?:а|ы|ов)?|модел[ьи]|интеграци[яию]|mvp|prototype|report|dashboard|service|model|integration)"
CALENDAR_DATE = r"(?:\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])|(?:0?[1-9]|[12]\d|3[01])[./](?:0?[1-9]|1[0-2])(?:[./]\d{4})?)(?![\w./-])"
DELIVERY_TARGET = re.compile(
    rf"\b{DELIVERABLE}\s+(?:(?:готов\w*|работает|готовность|ready|delivered)\s+)?"
    rf"(?:(?:за|через|в течение|within|in)\s+{NUMBER}\s*{DURATION}|"
    rf"(?:до|к|by)\s+{CALENDAR_DATE})",
    re.IGNORECASE,
)
CONTACT_CHANNEL = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b|"
    r"(?<!\w)@[a-z0-9_]+\b|"
    r"\bhttps?://[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?|"
    r"(?<!\w)\+?\d(?:[\s()-]*\d){9,14}(?![\w\d])",
    re.IGNORECASE,
)
CONSULTATION_ACTION = re.compile(
    r"\b(?:консультаци\w*|консультир\w*|обратная связь|обратную связь|"
    r"созвон\w*|встреч\w*|отвеча\w*|ответ\w* на вопросы|"
    r"consultations?|consulting|feedback|calls?|meetings?|answer questions)\b",
    re.IGNORECASE,
)
CONSULTATION_ARRANGEMENT = re.compile(
    r"\b(?:ежеднев\w*|еженедел\w*|ежемесяч\w*|по (?:запросу|пятницам|понедельникам|вторникам|средам|четвергам)|"
    r"раз в (?:день|неделю|месяц)|готов\w*|доступ\w*|"
    r"telegram|телеграм\w*|email|e-mail|почт\w*|чат\w*|zoom|зум|teams|"
    r"daily|weekly|monthly|on request|available|ready)\b",
    re.IGNORECASE,
)
CONSULTATION_UNAVAILABLE = re.compile(
    r"\b(?:нет|невозмож\w*|недоступ\w*|отказ\w*|"
    r"не (?:готов\w*|буд\w*|провод\w*|предостав\w*|планир\w*|мож\w*)|"
    r"без консультаци\w*|no|not|unavailable)\b",
    re.IGNORECASE,
)


def _measurement_reason(value: str) -> str | None:
    for pattern, reason in (
        (METRIC_TARGET, "Указаны метрика, числовая цель и единица измерения"),
        (COUNT_TARGET, "Указано числовое количество заявок, пользователей или других поддерживаемых объектов"),
        (DELIVERY_TARGET, "Указаны результат и числовой срок его получения"),
    ):
        match = pattern.search(value)
        if match:
            return f"{reason}: «{match.group(0)}»"
    return None


def _field_reason(field_name: str, value: str) -> tuple[bool, str]:
    label = FIELD_LABELS[field_name]
    if not value:
        return False, f"{label}: поле пустое"
    if field_name == "success_criteria":
        reason = _measurement_reason(value)
        return bool(reason), reason or (
            "Критерии успеха: нужны метрика с числовой целью и единицей, "
            "количество поддерживаемых объектов или результат со сроком; "
            "отдельные числа, KPI, даты и версии не засчитываются"
        )
    if field_name == "contact":
        if CONTACT_CHANNEL.search(value):
            return True, "Контакт: найден email, телефон, @идентификатор или HTTP(S)-адрес"
        return False, "Контакт: нужен email, телефон, @идентификатор или HTTP(S)-адрес; имя само по себе не засчитывается"
    if field_name == "consultation":
        if (
            not CONSULTATION_UNAVAILABLE.search(value)
            and CONSULTATION_ACTION.search(value)
            and (CONSULTATION_ARRANGEMENT.search(value) or CONTACT_CHANNEL.search(value))
        ):
            return True, "Консультации: указаны вид обратной связи и канал, периодичность или доступность"
        return False, "Консультации: нужны вид обратной связи и канал, периодичность или доступность без явного отказа"
    return True, f"{label}: поле заполнено"


def calculate_rating(fields: TaskFields, confirmed: bool = False) -> Rating:
    categories: list[RatingCategory] = []
    missing: list[str] = []
    total = 0
    for key, label, field_rules in RULES:
        maximum = sum(weight for _, weight in field_rules)
        points = 0
        basis: list[str] = []
        for field_name, weight in field_rules:
            value = " ".join(getattr(fields, field_name).split())
            accepted, reason = _field_reason(field_name, value)
            if accepted:
                points += weight
            awarded = weight if accepted and confirmed else 0
            basis.append(f"{reason} ({awarded}/{weight})")
        if not confirmed:
            basis.append("Баллы не начислены: поля ещё не подтверждены")
        total += points
        if points < maximum:
            missing.append(label)
        categories.append(RatingCategory(key=key, label=label, points=points if confirmed else 0, max_points=maximum, basis=basis))
    scored_total = total if confirmed else 0
    if scored_total < 40:
        level = "draft"
    elif scored_total < 70:
        level = "working"
    elif scored_total < 90:
        level = "ready"
    else:
        level = "priority"
    return Rating(total=scored_total, level=level, categories=categories, missing=missing)
