from contextlib import contextmanager
import json
import os
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from backend import ai
from backend.schemas import Answer, TaskFields


def completion(content, *, finish_reason="stop", refusal=None):
    return {
        "id": "mock-completion",
        "object": "chat.completion",
        "created": 0,
        "model": "mock-model",
        "choices": [{
            "index": 0,
            "finish_reason": finish_reason,
            "message": {"role": "assistant", "content": content, "refusal": refusal},
        }],
    }


class AiTest(unittest.TestCase):
    KNOWN_FIELDS = {
        "title": "Маршрутизация обращений", "topic": "Поддержка",
        "context": "Обращения передаются вручную", "need": "Ускорить маршрутизацию",
        "users": "Операторы", "data_materials": "Синтетические обращения в CSV",
        "constraints": "Без передачи персональных данных",
        "expected_result": "Прототип маршрутизации", "success_criteria": "Точность 90%",
        "contact": "demo@example.com", "consultation": "Еженедельный созвон",
    }

    def setUp(self):
        self.env = patch.dict(os.environ, {
            "AI_API_KEY": "", "OPENAI_API_KEY": "", "AI_TIMEOUT_SECONDS": "15",
            "AI_BASE_URL": "https://ai.invalid/v1", "AI_MODEL": "mock-model",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        token = ai.last_source.set("fallback")
        self.addCleanup(ai.last_source.reset, token)

    @contextmanager
    def provider(self, body=None, *, status=200, timeout=False):
        requests = []

        def respond(request):
            requests.append(request)
            if timeout:
                raise httpx.ReadTimeout("private upstream detail", request=request)
            return httpx.Response(status, json=body)

        clients = []

        def client_factory(**kwargs):
            client = OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))
            clients.append(client)
            return client

        # This inert SDK credential is only sent to MockTransport, never a network.
        with patch.dict(os.environ, {"AI_API_KEY": "mock-only"}), patch.object(ai, "OpenAI", side_effect=client_factory):
            yield requests
        self.assertTrue(all(client.is_closed() for client in clients))

    def test_only_missing_constraints_get_relevant_distinct_questions(self):
        fields = TaskFields(**{**self.KNOWN_FIELDS, "constraints": ""})
        result = ai.questions(fields)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)
        self.assertEqual(set(result), {ai.FIELD_QUESTIONS["constraints"], *ai.CLARIFICATIONS["constraints"]})
        self.assertEqual(ai.last_source.get(), "fallback")

    def test_complete_card_gets_substantive_clarifications(self):
        fields = TaskFields(**self.KNOWN_FIELDS)
        questions = ai.questions(fields)
        self.assertGreaterEqual(len(questions), 3)
        self.assertEqual(len(set(questions)), len(questions))
        self.assertTrue(all(ai._question_field(question) not in ('title', 'topic') for question in questions))
        # A complete card must never re-ask basics, even if the provider ignores
        # its schema; valid clarifications must remain usable as OpenAI output.
        basics = [ai.FIELD_QUESTIONS[name] for name in ("data_materials", "users", "expected_result")]
        with self.provider(completion(json.dumps({"questions": basics}))):
            self.assertEqual(ai.questions(fields), questions)
            self.assertEqual(ai.last_source.get(), "fallback")
        clarifications = [ai.CLARIFICATIONS[name][1] for name in ("data_materials", "users", "success_criteria")]
        with self.provider(completion(json.dumps({"questions": clarifications}))):
            self.assertEqual(ai.questions(fields), clarifications)
            self.assertEqual(ai.last_source.get(), "openai")

    def test_every_missing_field_can_be_asked_without_reasking_known_basics(self):
        for missing in ai.FIELDS:
            with self.subTest(missing=missing):
                fields = TaskFields(**{**self.KNOWN_FIELDS, missing: ""})
                result = ai.questions(fields)
                self.assertIn(ai.FIELD_QUESTIONS[missing], result)
                for known in ai.FIELDS:
                    if known != missing:
                        self.assertNotIn(ai.FIELD_QUESTIONS[known], result)

    def test_canonical_answers_fill_all_fields_and_keep_whole_assertions(self):
        expected = {name: f"Факт для {name}; только после согласования." for name in ai.FIELDS}
        answers = [Answer(question=ai.FIELD_QUESTIONS[name], answer=fact) for name, fact in expected.items()]
        result = ai.compose(TaskFields(), answers)
        self.assertEqual(result.model_dump(), expected)

    def test_free_questions_do_not_confuse_deadlines_results_and_users(self):
        result = ai.compose(TaskFields(), [
            Answer(question="Какой контакт?", answer="mail@example.com"),
            Answer(question="Доступна консультация?", answer="Нет, эксперт недоступен."),
            Answer(question="Какой срок?", answer="До 1 ноября."),
            Answer(question="Какой результат?", answer="Отчёт в PDF."),
        ])
        self.assertEqual(result.contact, "mail@example.com")
        self.assertEqual(result.consultation, "Нет, эксперт недоступен.")
        self.assertEqual(result.constraints, "До 1 ноября.")
        self.assertEqual(result.expected_result, "Отчёт в PDF.")
        self.assertEqual(result.success_criteria, "")
        self.assertEqual(result.users, "")

    def test_local_compose_preserves_existing_and_combines_full_answers(self):
        result = ai.compose(TaskFields(title="Original title"), [
            Answer(question=ai.FIELD_QUESTIONS["title"], answer="Replacement title"),
            Answer(question=ai.FIELD_QUESTIONS["constraints"], answer="Бюджет не согласован."),
            Answer(question=ai.CLARIFICATIONS["constraints"][0], answer="Данные нельзя передавать наружу."),
            Answer(question="Неясный вопрос?", answer="Неизвестный факт."),
        ])
        self.assertEqual(result.title, "Original title\nReplacement title")
        self.assertEqual(result.constraints, "Бюджет не согласован.\nДанные нельзя передавать наружу.")
        self.assertEqual(result.context, "")

    def test_clarification_retains_old_facts_and_deduplicates_retries(self):
        fields = TaskFields(constraints="Бюджет не согласован.")
        answers = [Answer(question=ai.CLARIFICATIONS["constraints"][0],
                          answer="Данные нельзя передавать наружу.\nДоступ только после согласования.")]
        expected = fields.constraints + "\n" + answers[0].answer
        result = ai.compose(fields, answers)
        self.assertEqual(result.constraints, expected)
        self.assertEqual(ai.compose(result, answers).constraints, expected)

    def test_provider_and_timeout_preserve_clarification_on_filled_field(self):
        fields = TaskFields(users="Операторы")
        answer = Answer(question=ai.CLARIFICATIONS["users"][0], answer="Первую проверку проведут два старших оператора.")
        expected = fields.model_dump()
        expected["users"] += "\n" + answer.answer
        with self.provider(completion(json.dumps(expected, ensure_ascii=False))):
            self.assertEqual(ai.compose(fields, [answer]).model_dump(), expected)
            self.assertEqual(ai.last_source.get(), "openai")
        # A valid-looking model answer that drops clarification is not accepted.
        with self.provider(completion(fields.model_dump_json())):
            self.assertEqual(ai.compose(fields, [answer]).model_dump(), expected)
            self.assertEqual(ai.last_source.get(), "fallback")
        with self.provider(timeout=True):
            self.assertEqual(ai.compose(fields, [answer]).model_dump(), expected)

    def test_provider_cannot_erase_uncertainty_when_adding_known_facts(self):
        fields = TaskFields(data_materials="Пока неизвестно", contact="Не знаю")
        answer = Answer(question=ai.FIELD_QUESTIONS["data_materials"],
                        answer="Есть синтетические CSV; доступ только после согласования.")
        expected = fields.model_dump()
        expected["data_materials"] += "\n" + answer.answer
        for mutation in ({"data_materials": answer.answer}, {"contact": ""}):
            with self.subTest(mutation=mutation):
                value = {**expected, **mutation}
                with self.provider(completion(json.dumps(value, ensure_ascii=False))):
                    self.assertEqual(ai.compose(fields, [answer]).model_dump(), expected)
                    self.assertEqual(ai.last_source.get(), "fallback")
        with self.provider(completion(json.dumps(expected, ensure_ascii=False))):
            self.assertEqual(ai.compose(fields, [answer]).model_dump(), expected)
            self.assertEqual(ai.last_source.get(), "openai")

    def test_provider_accepts_distinct_missing_field_questions(self):
        selected = [ai.FIELD_QUESTIONS[name] for name in ("context", "need", "users")]
        with self.provider(completion(json.dumps({"questions": selected}))) as requests:
            self.assertEqual(ai.questions(TaskFields()), selected)
            self.assertEqual(ai.last_source.get(), "openai")
            self.assertEqual(len(requests), 1)
        # Source belongs to this invocation, not the previous successful request.
        ai.compose(TaskFields(), [])
        self.assertEqual(ai.last_source.get(), "fallback")

    def test_provider_rejects_duplicates_even_with_three_distinct_questions(self):
        selected = [ai.FIELD_QUESTIONS[name] for name in ("context", "need", "users")]
        invalid = [selected[0], selected[0], *selected]
        fallback = ai.questions(TaskFields())
        with self.provider(completion(json.dumps({"questions": invalid}))):
            self.assertEqual(ai.questions(TaskFields()), fallback)
            self.assertEqual(ai.last_source.get(), "fallback")

    def test_provider_cannot_return_entire_catalog_or_hide_truncation_as_openai(self):
        fields = TaskFields(context="Обращения распределяются вручную.", need="Ускорить распределение.")
        selected = [ai.FIELD_QUESTIONS[name] for name in (
            "data_materials", "users", "expected_result", "success_criteria",
            "constraints", "contact", "consultation",
        )]
        with self.provider(completion(json.dumps({"questions": selected}))):
            result = ai.questions(fields)
            self.assertEqual(ai.last_source.get(), "fallback")
            self.assertEqual(len(result), 5)
            self.assertEqual(len(set(result)), 5)
            for name in ("data_materials", "users", "expected_result", "success_criteria"):
                self.assertIn(ai.FIELD_QUESTIONS[name], result)
        with self.provider(completion(json.dumps({"questions": selected[:5]}))):
            self.assertEqual(ai.questions(fields), selected[:5])
            self.assertEqual(ai.last_source.get(), "openai")

    def test_provider_cannot_reask_known_basics_or_skip_only_missing_field(self):
        fields = TaskFields(**{**self.KNOWN_FIELDS, "constraints": ""})
        invalid = [ai.FIELD_QUESTIONS[name] for name in ("context", "need", "users")]
        fallback = ai.questions(fields)
        with self.provider(completion(json.dumps({"questions": invalid}))):
            self.assertEqual(ai.questions(fields), fallback)
            self.assertEqual(ai.last_source.get(), "fallback")

    def test_questions_prioritize_unknown_facts_over_title_and_topic(self):
        fields = TaskFields(**{name: "Не знаю" for name in ai.FIELDS})
        result = ai.questions(fields)
        for name in ("data_materials", "users", "expected_result", "success_criteria"):
            self.assertIn(ai.FIELD_QUESTIONS[name], result)
        cosmetic = [*ai.CLARIFICATIONS["title"], ai.FIELD_QUESTIONS["topic"]]
        with self.provider(completion(json.dumps({"questions": cosmetic}))):
            self.assertEqual(ai.questions(fields), result)
            self.assertEqual(ai.last_source.get(), "fallback")
        valid = [ai.FIELD_QUESTIONS[name] for name in ("data_materials", "users", "expected_result")]
        with self.provider(completion(json.dumps({"questions": valid}))):
            self.assertEqual(ai.questions(fields), valid)
            self.assertEqual(ai.last_source.get(), "openai")

    def test_unmeasured_criterion_is_missing_even_when_nonempty(self):
        fields = TaskFields(**{**self.KNOWN_FIELDS, "success_criteria": "Улучшить качество"})
        result = ai.questions(fields)
        self.assertIn(ai.FIELD_QUESTIONS["success_criteria"], result)
        self.assertNotIn(ai.FIELD_QUESTIONS["users"], result)

    def test_provider_extracts_valid_full_card_without_changing_original(self):
        fields = TaskFields(title="  Original  ", context="Initial description")
        value = fields.model_dump()
        value.update(contact="mail@example.com", consultation="Только письменно по пятницам.")
        answers = [Answer(question=ai.FIELD_QUESTIONS[name], answer=value[name]) for name in ("contact", "consultation")]
        with self.provider(completion(json.dumps(value, ensure_ascii=False))):
            self.assertEqual(ai.compose(fields, answers).model_dump(), value)
            self.assertEqual(ai.last_source.get(), "openai")

    def test_provider_rejects_negation_loss_fabrication_overwrite_and_wrong_field(self):
        fields = TaskFields(title="Original")
        answer = Answer(question=ai.FIELD_QUESTIONS["data_materials"], answer="Данные не доступны; доступ только после согласования.")
        for mutation in (
            {"data_materials": "доступны"},
            {"data_materials": "доступ только после согласования."},
            {"data_materials": "Есть CSV на 1000 строк."},
            {"title": "New title"},
            {"success_criteria": answer.answer},
            {"contact": fields.title},
        ):
            with self.subTest(mutation=mutation):
                value = fields.model_dump()
                value.update(mutation)
                with self.provider(completion(json.dumps(value, ensure_ascii=False))):
                    result = ai.compose(fields, [answer])
                    self.assertEqual(result.title, fields.title)
                    self.assertEqual(result.data_materials, answer.answer)
                    self.assertEqual(result.contact, "")
                    self.assertEqual(result.success_criteria, "")
                    self.assertEqual(ai.last_source.get(), "fallback")

    def test_provider_rejects_incomplete_extra_or_nonstring_card_fields(self):
        answer = Answer(question=ai.FIELD_QUESTIONS["contact"], answer="mail@example.com")
        for value in ({"contact": answer.answer}, {**TaskFields().model_dump(), "extra": "fact"}, {**TaskFields().model_dump(), "contact": None}):
            with self.subTest(value=value), self.provider(completion(json.dumps(value))):
                self.assertEqual(ai.compose(TaskFields(), [answer]).contact, answer.answer)
                self.assertEqual(ai.last_source.get(), "fallback")

    def test_malformed_refused_and_truncated_responses_fall_back(self):
        malformed = [
            {}, {"choices": None}, {"choices": []}, {"choices": [None]},
            {"choices": [{"finish_reason": "stop", "message": None}]},
            completion(None), completion(42), completion("not JSON"), completion("[]"),
            completion('{"questions":[],"questions":[]}'),
            completion("{}", finish_reason="length"),
            completion("{}", finish_reason="content_filter"),
            completion("{}", refusal="Cannot comply"),
        ]
        fallback = ai.questions(TaskFields())
        for body in malformed:
            with self.subTest(body=body), self.provider(body):
                self.assertEqual(ai.questions(TaskFields()), fallback)
                self.assertEqual(ai.last_source.get(), "fallback")

    def test_auth_rate_limit_server_errors_and_timeout_fall_back_without_retries(self):
        answer = Answer(question=ai.FIELD_QUESTIONS["contact"], answer="mail@example.com")
        for status, timeout in ((401, False), (429, False), (500, False), (200, True)):
            with self.subTest(status=status, timeout=timeout):
                with self.provider({"error": {"message": "private upstream detail"}}, status=status, timeout=timeout) as requests:
                    self.assertEqual(ai.compose(TaskFields(), [answer]).contact, answer.answer)
                    self.assertEqual(ai.last_source.get(), "fallback")
                    self.assertEqual(len(requests), 1)


if __name__ == "__main__":
    unittest.main()
