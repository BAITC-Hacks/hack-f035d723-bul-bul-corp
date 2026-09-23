import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import type { RatingLevel, TaskResponse } from "../../api/types";
import { useDemoSession } from "../../app/DemoSession";

const ratingLabels: Record<RatingLevel, string> = {
  draft: "Черновик",
  working: "Рабочая",
  ready: "Готовая",
  priority: "Приоритетная",
};
const ratingLevelLookup: Record<string, true> = {
  draft: true,
  working: true,
  ready: true,
  priority: true,
};


type RatingFilter = RatingLevel | "";
type RatingSort = "desc" | "asc";

export function CatalogPage() {
  const { api, selectedIdentity, state: sessionState } = useDemoSession();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<TaskResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!selectedIdentity) {
      setItems([]);
      setIsLoading(sessionState === "loading");
      return;
    }

    let active = true;
    setIsLoading(true);
    setError(null);
    void api
      .catalog()
      .then((response) => {
        if (!active) return;
        setItems(response.items.filter((task) => task.published));
        setIsLoading(false);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setItems([]);
        setError(
          reason instanceof ApiError
            ? reason.message
            : "Не удалось загрузить каталог",
        );
        setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [api, reloadKey, selectedIdentity, sessionState]);

  const topic = searchParams.get("topic") ?? "";
  const levelValue = searchParams.get("level") ?? "";
  const level: RatingFilter = isRatingLevel(levelValue) ? levelValue : "";
  const sort: RatingSort = searchParams.get("sort") === "asc" ? "asc" : "desc";

  const topics = useMemo(
    () =>
      Array.from(
        new Set(items.map((task) => task.topic.trim()).filter(Boolean)),
      ).sort((left, right) => left.localeCompare(right, "ru")),
    [items],
  );

  const visibleItems = useMemo(() => {
    const filtered = items.filter((task) => {
      const matchesTopic = topic === "" || task.topic === topic;
      const matchesLevel = level === "" || task.rating.level === level;
      return matchesTopic && matchesLevel;
    });

    return filtered.sort((left, right) => {
      const difference = left.rating.total - right.rating.total;
      return sort === "asc" ? difference : -difference;
    });
  }, [items, level, sort, topic]);

  const hasFilters = topic !== "" || level !== "" || sort !== "desc";

  function updateFilter(name: "topic" | "level" | "sort", value: string) {
    const next = new URLSearchParams(searchParams);
    const isDefault = value === "" || (name === "sort" && value === "desc");
    if (isDefault) next.delete(name);
    else next.set(name, value);
    setSearchParams(next, { replace: true });
  }

  return (
    <section className="catalog-page" aria-labelledby="catalog-title">
      <div className="catalog-heading">
        <div>
          <h1 id="catalog-title">Каталог задач</h1>
          <p>Опубликованные задачи бизнеса, открытые для предложений команд.</p>
        </div>
        {!isLoading && !error && (
          <p className="catalog-count" aria-live="polite">
            Найдено: <strong>{visibleItems.length}</strong>
          </p>
        )}
      </div>

      <div className="catalog-filters" aria-label="Фильтры каталога">
        <label>
          <span>Тема</span>
          <select
            value={topic}
            onChange={(event) => updateFilter("topic", event.target.value)}
            disabled={isLoading || topics.length === 0}
          >
            <option value="">Все темы</option>
            {topics.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span>Готовность</span>
          <select
            value={level}
            onChange={(event) => updateFilter("level", event.target.value)}
            disabled={isLoading}
          >
            <option value="">Все уровни</option>
            <option value="draft">Черновик, 0–39</option>
            <option value="working">Рабочая, 40–69</option>
            <option value="ready">Готовая, 70–89</option>
            <option value="priority">Приоритетная, 90–100</option>
          </select>
        </label>

        <label>
          <span>Сортировка</span>
          <select
            value={sort}
            onChange={(event) => updateFilter("sort", event.target.value)}
            disabled={isLoading}
          >
            <option value="desc">Сначала высокий рейтинг</option>
            <option value="asc">Сначала низкий рейтинг</option>
          </select>
        </label>

        <button
          className="filter-reset"
          type="button"
          onClick={() => setSearchParams({}, { replace: true })}
          disabled={!hasFilters || isLoading}
        >
          Сбросить фильтры
        </button>
      </div>

      {isLoading ? (
        <CatalogLoading />
      ) : error ? (
        <div className="catalog-message catalog-message--error" role="alert">
          <h2>Каталог не загрузился</h2>
          <p>{error}</p>
          <button type="button" onClick={() => setReloadKey((value) => value + 1)}>
            Повторить загрузку
          </button>
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="catalog-message">
          <h2>{items.length === 0 ? "Опубликованных задач пока нет" : "По этим фильтрам задач нет"}</h2>
          <p>
            {items.length === 0
              ? "Когда бизнес опубликует задачу, она появится в этом списке."
              : "Сбросьте фильтры или выберите другие значения."}
          </p>
          {items.length > 0 && (
            <button type="button" onClick={() => setSearchParams({}, { replace: true })}>
              Сбросить фильтры
            </button>
          )}
        </div>
      ) : (
        <div className="task-list" aria-label="Опубликованные задачи">
          {visibleItems.map((task) => (
            <article className="task-row" key={task.id}>
              <div className="task-row__main">
                <div className="task-row__meta">
                  <span>{task.topic || "Тема не указана"}</span>
                  <span className={`readiness readiness--${task.rating.level}`}>
                    {ratingLabels[task.rating.level]}
                  </span>
                </div>
                <h2>
                  <Link to={`/catalog/${encodeURIComponent(task.id)}${location.search}`}>
                    {task.title || "Задача без названия"}
                  </Link>
                </h2>
                <p>{task.need || "Потребность не указана"}</p>
              </div>
              <div className="task-score" aria-label={`Рейтинг ${task.rating.total} из 100`}>
                <strong>{task.rating.total}</strong>
                <span>из 100</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function CatalogLoading() {
  return (
    <div className="catalog-loading" aria-label="Загрузка каталога" aria-busy="true">
      {[0, 1, 2].map((item) => (
        <div className="catalog-loading__row" key={item}>
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}

function isRatingLevel(value: string): value is RatingLevel {
  return value in ratingLevelLookup;
}
