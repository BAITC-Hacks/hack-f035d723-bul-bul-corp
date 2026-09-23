import unittest
from itertools import combinations

from backend.rating import calculate_rating
from backend.schemas import TaskFields


class RatingTest(unittest.TestCase):
    FIELD_VALUES = {
        "context": "Заявки сейчас обрабатываются вручную",
        "need": "Сократить время обработки",
        "data_materials": "CSV с заявками и описание полей",
        "expected_result": "Работающий прототип",
        "success_criteria": "10 заявок за 7 дней",
        "constraints": "Без передачи персональных данных наружу",
        "users": "Операторы поддержки",
        "contact": "owner@example.com",
        "consultation": "Обратная связь в Telegram",
    }
    FIELD_WEIGHTS = {
        "context": ("context_need", 10),
        "need": ("context_need", 10),
        "data_materials": ("data_materials", 20),
        "expected_result": ("expected_result", 15),
        "success_criteria": ("success_criteria", 15),
        "constraints": ("constraints", 10),
        "users": ("users", 10),
        "contact": ("contact_consultation", 5),
        "consultation": ("contact_consultation", 5),
    }

    def score(self, **fields):
        return calculate_rating(TaskFields(**fields), confirmed=True)

    def test_measurement_accepts_supported_targets(self):
        criteria = (
            "10 заявок за 7 дней",
            "точность 90%",
            "Точность: не менее 90,5 %",
            "Время ответа не более 2 секунд",
            "Стоимость до 100 рублей",
            "0 ошибок",
            "Прототип готов за 7 дней",
            "Создать отчёт в течение 2 недель",
            "MVP к 01.06.2026",
            "accuracy >= 90%",
            "response time under 2 seconds",
            "Reduce costs by 10%",
            "100 requests in 2 minutes",
            "Deliver prototype within 14 days",
            "report by 2026-06-01",
        )
        for criterion in criteria:
            with self.subTest(criterion=criterion):
                rating = self.score(success_criteria=criterion)
                self.assertEqual(rating.total, 15)
                category = next(c for c in rating.categories if c.key == "success_criteria")
                self.assertNotIn(category.label, rating.missing)

    def test_measurement_rejects_identifiers_and_unmeasured_numbers(self):
        criteria = (
            "", " \t\n", "Улучшить качество", "kpi 1", "KPI 1%",
            "Метрика 20", "Количество 10", "10", "90%", "7 дней",
            "до 01.06.2026", "2026-06-01", "версия 2.0", "version 7",
            "Качество 10 из неизвестного", "10 произвольных вещей",
            "точность высокая, версия 90", "стоимость 10 рубиконов",
            "время ответа 2 часовни", "abc10 заявок", "v2.10 заявок",
            "accuracy 2 seconds", "revenue 3 days", "прототип до 2.0",
        )
        for criterion in criteria:
            with self.subTest(criterion=criterion):
                rating = self.score(success_criteria=criterion)
                self.assertEqual(rating.total, 0)
                category = next(c for c in rating.categories if c.key == "success_criteria")
                self.assertIn(category.label, rating.missing)

    def test_each_field_has_its_exact_weight(self):
        for field, (category_key, weight) in self.FIELD_WEIGHTS.items():
            with self.subTest(field=field):
                rating = self.score(**{field: self.FIELD_VALUES[field]})
                self.assertEqual(rating.total, weight)
                self.assertEqual(
                    {category.key: category.points for category in rating.categories if category.points},
                    {category_key: weight},
                )

    def test_maximum_is_100_with_fixed_category_caps(self):
        rating = self.score(**self.FIELD_VALUES)
        self.assertEqual(rating.total, 100)
        self.assertEqual(rating.level, "priority")
        self.assertEqual(rating.missing, [])
        self.assertEqual(
            {category.key: (category.points, category.max_points) for category in rating.categories},
            {
                "context_need": (20, 20), "data_materials": (20, 20),
                "expected_result": (15, 15), "success_criteria": (15, 15),
                "constraints": (10, 10), "users": (10, 10),
                "contact_consultation": (10, 10),
            },
        )

    def test_unconfirmed_fields_never_award_points(self):
        fields = TaskFields(**self.FIELD_VALUES)
        for rating in (calculate_rating(fields), calculate_rating(fields, confirmed=False)):
            self.assertEqual(rating.total, 0)
            self.assertEqual(rating.level, "draft")
            self.assertTrue(all(category.points == 0 for category in rating.categories))
            self.assertEqual(rating.missing, [])
        self.assertEqual(calculate_rating(fields, confirmed=True).total, 100)

    def test_whitespace_and_unrated_fields_do_not_score(self):
        rating = self.score(
            **{field: " \t\n\u00a0" for field in self.FIELD_VALUES},
            title="Известная компания", topic="AI",
        )
        self.assertEqual(rating.total, 0)
        self.assertEqual(set(rating.missing), {category.label for category in rating.categories})

    def test_simple_field_scores_do_not_depend_on_length(self):
        self.assertEqual(self.score(context="x").total, 10)
        self.assertEqual(self.score(context="x" * 10000).total, 10)

    def test_level_boundaries_for_every_reachable_total(self):
        fields_by_total = {}
        names = tuple(self.FIELD_VALUES)
        for count in range(len(names) + 1):
            for selected in combinations(names, count):
                total = sum(self.FIELD_WEIGHTS[name][1] for name in selected)
                fields_by_total.setdefault(total, {name: self.FIELD_VALUES[name] for name in selected})
        self.assertEqual(set(fields_by_total), set(range(0, 101, 5)))
        for total, fields in fields_by_total.items():
            with self.subTest(total=total):
                rating = self.score(**fields)
                expected_level = (
                    "draft" if total < 40 else "working" if total < 70
                    else "ready" if total < 90 else "priority"
                )
                self.assertEqual((rating.total, rating.level), (total, expected_level))
                self.assertEqual(sum(category.points for category in rating.categories), total)

    def test_deleting_each_scored_field_decreases_rating(self):
        for field, (category_key, weight) in self.FIELD_WEIGHTS.items():
            with self.subTest(field=field):
                fields = dict(self.FIELD_VALUES)
                fields[field] = ""
                rating = self.score(**fields)
                self.assertEqual(rating.total, 100 - weight)
                category = next(c for c in rating.categories if c.key == category_key)
                self.assertIn(category.label, rating.missing)

    def test_contact_requires_a_recognizable_channel(self):
        for contact in ("owner@example.com", "+7 (999) 123-45-67", "@owner", "https://example.com/contact"):
            with self.subTest(contact=contact):
                self.assertEqual(self.score(contact=contact).total, 5)
        for contact in ("", "Иван", "да", "телефон позже", "12345", "user@"):
            with self.subTest(contact=contact):
                self.assertEqual(self.score(contact=contact).total, 0)

    def test_consultation_requires_action_and_arrangement_without_refusal(self):
        for consultation in (
            "Обратная связь в Telegram", "Еженедельный созвон", "Готов отвечать на вопросы",
            "Консультации по запросу", "Feedback by email", "Weekly meetings",
            "Consultation via owner@example.com",
        ):
            with self.subTest(consultation=consultation):
                self.assertEqual(self.score(consultation=consultation).total, 5)
        for consultation in (
            "", "да", "Telegram", "Еженедельно", "Консультации", "Консультаций нет",
            "Не готов консультировать", "No weekly meetings", "Feedback not available",
        ):
            with self.subTest(consultation=consultation):
                self.assertEqual(self.score(consultation=consultation).total, 0)


if __name__ == "__main__":
    unittest.main()
