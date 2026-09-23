from __future__ import annotations

from .schemas import Rating, RatingCategory, TaskFields


RULES = (
    ("context_need", "Контекст и потребность", 20, ("context", "need")),
    ("data_materials", "Данные и материалы", 20, ("data_materials",)),
    ("expected_result", "Ожидаемый результат", 15, ("expected_result",)),
    ("success_criteria", "Измеримые критерии успеха", 15, ("success_criteria",)),
    ("constraints", "Ограничения", 10, ("constraints",)),
    ("users", "Пользователи", 10, ("users",)),
    ("contact_consultation", "Контакт, консультации и обратная связь", 10, ("contact", "consultation")),
)


def _words(value: str) -> list[str]:
    return [word for word in value.strip().split() if word]


def _has_measurement(value: str) -> bool:
    lowered = value.lower()
    markers = ("%", "руб", "₽", "час", "день", "недел", "месяц", "колич", "метрик", "kpi", "до ")
    return any(marker in lowered for marker in markers) and any(char.isdigit() for char in value)


def calculate_rating(fields: TaskFields, confirmed: bool = False) -> Rating:
    categories: list[RatingCategory] = []
    missing: list[str] = []
    total = 0
    for key, label, maximum, field_names in RULES:
        values = [getattr(fields, field_name) for field_name in field_names]
        present = [value.strip() for value in values if value and value.strip()]
        if key == "success_criteria":
            points = maximum if present and _has_measurement(present[0]) else 0
            basis = ["Есть измеримый критерий"] if points else ["Нужны число, срок или измеримая метрика"]
        elif len(field_names) == 1:
            points = maximum if present else 0
            basis = ["Поле заполнено"] if points else ["Поле пустое"]
        else:
            points = round(maximum * len(present) / len(field_names))
            basis = [f"Заполнено полей: {len(present)} из {len(field_names)}"]
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
