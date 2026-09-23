import { type FormEvent, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import type {
  FieldErrors,
  ProposalCreate,
  ProposalResponse,
  ProposalStatus,
} from "../../api/types";
import { useDemoSession } from "../../app/DemoSession";

const initialValues: ProposalCreate = {
  idea: "",
  plan: "",
  duration: "",
  prototype_url: "",
};

const proposalStatusLabels: Record<ProposalStatus, string> = {
  pending: "На рассмотрении",
  selected: "Выбрано",
  rejected: "Отклонено",
};

type LoadState = "idle" | "loading" | "ready" | "error";

export function ProposalPanel({ taskId }: { taskId: string }) {
  const { api, selectedIdentity } = useDemoSession();
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [values, setValues] = useState<ProposalCreate>(initialValues);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submitLock = useRef(false);

  useEffect(() => {
    if (selectedIdentity?.role !== "team") {
      setLoadState("idle");
      setProposal(null);
      return;
    }

    let active = true;
    setLoadState("loading");
    setLoadError(null);

    void api
      .teamProposals()
      .then((response) => {
        if (!active) return;
        const currentProposal =
          response.items.find((item) => item.task_id === taskId) ?? null;
        setProposal(currentProposal);
        setLoadState("ready");
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setProposal(null);
        setLoadError(
          reason instanceof ApiError
            ? reason.message
            : "Не удалось проверить отправленные предложения",
        );
        setLoadState("error");
      });

    return () => {
      active = false;
    };
  }, [api, reloadKey, selectedIdentity, taskId]);

  if (selectedIdentity?.role !== "team") return null;

  if (loadState === "loading" || loadState === "idle") {
    return (
      <section className="proposal-panel" aria-label="Загрузка предложения" aria-busy="true">
        <div className="proposal-loading">
          <span />
          <span />
        </div>
      </section>
    );
  }

  if (loadState === "error") {
    return (
      <section className="proposal-panel" aria-labelledby="proposal-title">
        <div className="proposal-panel__heading">
          <h2 id="proposal-title">Предложить решение</h2>
        </div>
        <div className="proposal-load-error" role="alert">
          <h3>Не удалось проверить ваши предложения</h3>
          <p>{loadError}</p>
          <button type="button" onClick={() => setReloadKey((value) => value + 1)}>
            Повторить
          </button>
        </div>
      </section>
    );
  }

  if (proposal) {
    return (
      <section className="proposal-panel" aria-labelledby="proposal-title">
        <div className="proposal-panel__heading">
          <div>
            <h2 id="proposal-title">Ваше предложение</h2>
            <p>Предложение сохранено. Статус обновляется из backend.</p>
          </div>
          <span className={`proposal-status proposal-status--${proposal.status}`}>
            {proposalStatusLabels[proposal.status]}
          </span>
        </div>
        <dl className="proposal-summary">
          <div>
            <dt>Идея</dt>
            <dd>{proposal.idea}</dd>
          </div>
          <div>
            <dt>План</dt>
            <dd>{proposal.plan}</dd>
          </div>
          <div>
            <dt>Срок</dt>
            <dd>{proposal.duration}</dd>
          </div>
          <div>
            <dt>Прототип</dt>
            <dd>
              {proposal.prototype_url ? (
                <a href={proposal.prototype_url} target="_blank" rel="noreferrer">
                  Открыть ссылку
                </a>
              ) : (
                <span className="field-empty">Не указан</span>
              )}
            </dd>
          </div>
        </dl>
      </section>
    );
  }

  function updateField(field: keyof ProposalCreate, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    if (fieldErrors[field]) {
      setFieldErrors((current) => {
        const next = { ...current };
        delete next[field];
        return next;
      });
    }
  }

  async function submitProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitLock.current) return;

    const trimmedValues: ProposalCreate = {
      idea: values.idea.trim(),
      plan: values.plan.trim(),
      duration: values.duration.trim(),
      prototype_url: values.prototype_url.trim(),
    };
    const validationErrors: FieldErrors = {};
    if (!trimmedValues.idea) validationErrors.idea = "Опишите идею решения";
    if (!trimmedValues.plan) validationErrors.plan = "Добавьте план работы";
    if (!trimmedValues.duration) validationErrors.duration = "Укажите срок";

    if (Object.keys(validationErrors).length > 0) {
      setFieldErrors(validationErrors);
      setSubmitError(null);
      return;
    }
    submitLock.current = true;

    setIsSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});

    try {
      const createdProposal = await api.createProposal(taskId, trimmedValues);
      setProposal(createdProposal);
      setValues(trimmedValues);
    } catch (reason: unknown) {
      if (reason instanceof ApiError) {
        setSubmitError(reason.message);
        setFieldErrors(reason.fieldErrors);
      } else {
        setSubmitError("Не удалось отправить предложение. Повторите попытку.");
      }
    } finally {
      setIsSubmitting(false);
      submitLock.current = false;
    }
  }

  return (
    <section className="proposal-panel" aria-labelledby="proposal-title">
      <div className="proposal-panel__heading">
        <div>
          <h2 id="proposal-title">Предложить решение</h2>
          <p>Опишите подход команды. Бизнес вручную рассмотрит предложение.</p>
        </div>
      </div>

      <form className="proposal-form" onSubmit={submitProposal} noValidate>
        {submitError && (
          <div className="proposal-submit-error" role="alert">
            <strong>Предложение не отправлено</strong>
            <span>{submitError}</span>
          </div>
        )}

        <fieldset disabled={isSubmitting}>
          <label className="proposal-field proposal-field--wide">
            <span>Идея</span>
            <textarea
              id="proposal-idea"
              value={values.idea}
              onChange={(event) => updateField("idea", event.target.value)}
              rows={4}
              aria-invalid={Boolean(fieldErrors.idea)}
              aria-describedby={fieldErrors.idea ? "proposal-idea-error" : undefined}
              placeholder="Как команда предлагает решить задачу"
              required
            />
            {fieldErrors.idea && <small id="proposal-idea-error">{fieldErrors.idea}</small>}
          </label>

          <label className="proposal-field proposal-field--wide">
            <span>План</span>
            <textarea
              id="proposal-plan"
              value={values.plan}
              onChange={(event) => updateField("plan", event.target.value)}
              rows={5}
              aria-invalid={Boolean(fieldErrors.plan)}
              aria-describedby={fieldErrors.plan ? "proposal-plan-error" : undefined}
              placeholder="Основные шаги и ожидаемый результат каждого шага"
              required
            />
            {fieldErrors.plan && <small id="proposal-plan-error">{fieldErrors.plan}</small>}
          </label>

          <label className="proposal-field">
            <span>Срок</span>
            <input
              id="proposal-duration"
              value={values.duration}
              onChange={(event) => updateField("duration", event.target.value)}
              aria-invalid={Boolean(fieldErrors.duration)}
              aria-describedby={fieldErrors.duration ? "proposal-duration-error" : undefined}
              placeholder="Например, 3 недели"
              required
            />
            {fieldErrors.duration && (
              <small id="proposal-duration-error">{fieldErrors.duration}</small>
            )}
          </label>

          <label className="proposal-field">
            <span>Ссылка на прототип</span>
            <input
              id="proposal-prototype-url"
              type="url"
              value={values.prototype_url}
              onChange={(event) => updateField("prototype_url", event.target.value)}
              aria-invalid={Boolean(fieldErrors.prototype_url)}
              aria-describedby={fieldErrors.prototype_url ? "proposal-url-error" : undefined}
              placeholder="https://"
            />
            {fieldErrors.prototype_url && (
              <small id="proposal-url-error">{fieldErrors.prototype_url}</small>
            )}
          </label>
        </fieldset>

        <div className="proposal-form__actions">
          <p>Проверьте данные перед отправкой.</p>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Отправляем…" : "Отправить предложение"}
          </button>
        </div>
      </form>
    </section>
  );
}
