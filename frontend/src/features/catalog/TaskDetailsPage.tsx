import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import type { RatingLevel, TaskFields, TaskResponse } from "../../api/types";
import { useDemoSession } from "../../app/DemoSession";
import { ProposalPanel } from "../proposals/ProposalPanel";

const ratingLabels: Record<RatingLevel, string> = {
  draft: "Черновик",
  working: "Рабочая",
  ready: "Готовая",
  priority: "Приоритетная",
};

const taskFields: ReadonlyArray<{ key: keyof TaskFields; label: string }> = [
  { key: "title", label: "Название" },
  { key: "topic", label: "Тема" },
  { key: "context", label: "Контекст" },
  { key: "need", label: "Потребность" },
  { key: "users", label: "Пользователи" },
  { key: "data_materials", label: "Данные и материалы" },
  { key: "constraints", label: "Ограничения" },
  { key: "expected_result", label: "Ожидаемый результат" },
  { key: "success_criteria", label: "Критерии успеха" },
  { key: "contact", label: "Контакт" },
  { key: "consultation", label: "Консультации и обратная связь" },
];

export function TaskDetailsPage() {
  const { taskId } = useParams();
  const location = useLocation();
  const { api, selectedIdentity, state: sessionState } = useDemoSession();
  const [task, setTask] = useState<TaskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const backLink = `/catalog${location.search}`;

  useEffect(() => {
    if (!selectedIdentity || !taskId) {
      setTask(null);
      setIsLoading(sessionState === "loading");
      setNotFound(Boolean(selectedIdentity && !taskId));
      return;
    }

    let active = true;
    setIsLoading(true);
    setError(null);
    setNotFound(false);

    // The catalog endpoint always returns the published snapshot. GET /api/tasks/{id}
    // returns the owner's editable version and could expose unconfirmed changes here.
    void api
      .catalog()
      .then((response) => {
        if (!active) return;
        const publishedTask =
          response.items.find((item) => item.id === taskId && item.published) ?? null;
        setTask(publishedTask);
        setNotFound(publishedTask === null);
        setIsLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setTask(null);
        setError(
          reason instanceof ApiError
            ? reason.message
            : "Не удалось загрузить задачу",
        );
        setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [api, reloadKey, selectedIdentity, sessionState, taskId]);

  if (isLoading) {
    return (
      <section className="task-details" aria-label="Загрузка задачи" aria-busy="true">
        <Link className="back-link" to={backLink}>Назад в каталог</Link>
        <div className="details-loading">
          <span />
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="task-details">
        <Link className="back-link" to={backLink}>Назад в каталог</Link>
        <div className="catalog-message catalog-message--error" role="alert">
          <h1>Задача не загрузилась</h1>
          <p>{error}</p>
          <button type="button" onClick={() => setReloadKey((value) => value + 1)}>
            Повторить загрузку
          </button>
        </div>
      </section>
    );
  }

  if (notFound || !task) {
    return (
      <section className="task-details">
        <Link className="back-link" to={backLink}>Назад в каталог</Link>
        <div className="catalog-message">
          <h1>Опубликованная задача не найдена</h1>
          <p>Возможно, задачу сняли с публикации или ссылка устарела.</p>
        </div>
      </section>
    );
  }

  return (
    <article className="task-details" aria-labelledby="task-title">
      <Link className="back-link" to={backLink}>Назад в каталог</Link>

      <header className="task-details__header">
        <div>
          <div className="task-row__meta">
            <span>{task.topic || "Тема не указана"}</span>
            <span className={`readiness readiness--${task.rating.level}`}>
              {ratingLabels[task.rating.level]}
            </span>
          </div>
          <h1 id="task-title">{task.title || "Задача без названия"}</h1>
          <p>{task.need || "Потребность не указана"}</p>
        </div>
        <div className="details-score" aria-label={`Рейтинг ${task.rating.total} из 100`}>
          <strong>{task.rating.total}</strong>
          <span>из 100</span>
        </div>
      </header>

      {selectedIdentity?.role === "team" && <p><a className="button primary" href="#proposal">Предложить решение</a></p>}
      <div className="task-details__layout">
        <section className="task-fields" aria-labelledby="task-fields-title">
          <h2 id="task-fields-title">Подтверждённая карточка</h2>
          <dl>
            {taskFields.map((field) => (
              <div key={field.key}>
                <dt>{field.label}</dt>
                <dd className={task[field.key] ? undefined : "field-empty"}>
                  {task[field.key] || "Не указано"}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <aside className="rating-details" aria-labelledby="rating-title">
          <div className="rating-details__heading">
            <h2 id="rating-title">Расшифровка рейтинга</h2>
            <strong>{task.rating.total}/100</strong>
          </div>
          <div className="rating-categories">
            {task.rating.categories.map((category) => (
              <section key={category.key}>
                <div>
                  <h3>{category.label}</h3>
                  <strong>{category.points}/{category.max_points}</strong>
                </div>
                {category.basis.length > 0 && (
                  <ul>
                    {category.basis.map((basis) => <li key={basis}>{basis}</li>)}
                  </ul>
                )}
              </section>
            ))}
          </div>
          {task.rating.missing.length > 0 && (
            <section className="rating-missing">
              <h3>Что можно дополнить</h3>
              <ul>
                {task.rating.missing.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
          )}
        </aside>
      </div>
      <ProposalPanel key={selectedIdentity?.id+task.id} taskId={task.id} />
    </article>
  );
}
