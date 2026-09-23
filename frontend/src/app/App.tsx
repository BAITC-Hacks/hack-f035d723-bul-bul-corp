import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { CatalogPage } from "../features/catalog/CatalogPage";
import { TaskDetailsPage } from "../features/catalog/TaskDetailsPage";
import { useDemoSession } from "./DemoSession";

const navigation = [
  { to: "/catalog", label: "Каталог" },
  { to: "/constructor", label: "Конструктор" },
  { to: "/business", label: "Кабинет бизнеса" },
  { to: "/team", label: "Кабинет команды" },
] as const;

const routeContent = {
  catalog: {
    title: "Каталог",
    description: "Опубликованные задачи и предложения команд.",
  },
  constructor: {
    title: "Конструктор",
    description: "Описание, уточнения, подтверждение и публикация задачи.",
  },
  business: {
    title: "Кабинет бизнеса",
    description: "Черновики, опубликованные задачи и решения по предложениям.",
  },
  team: {
    title: "Кабинет команды",
    description: "Предложения, выбранные задачи и результаты этапа.",
  },
} as const;

export function App() {
  return (
    <div className="app-shell">
      <Header />
      <main className="main-content" id="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/catalog" replace />} />
          <Route path="/catalog" element={<CatalogPage />} />
          <Route path="/catalog/:taskId" element={<TaskDetailsPage />} />
          <Route path="/constructor" element={<SectionPage section="constructor" />} />
          <Route path="/business" element={<SectionPage section="business" />} />
          <Route path="/team" element={<SectionPage section="team" />} />
          <Route path="*" element={<Navigate to="/catalog" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function Header() {
  const {
    identities,
    selectedIdentity,
    state,
    error,
    selectIdentity,
    reload,
  } = useDemoSession();

  return (
    <header className="site-header">
      <a className="skip-link" href="#main-content">
        Перейти к содержимому
      </a>
      <div className="header-primary">
        <NavLink className="brand" to="/catalog" aria-label="AI Sana, каталог">
          <span className="brand-mark" aria-hidden="true">
            AI
          </span>
          <span className="brand-name">Sana</span>
          <span className="demo-flag">Деморежим</span>
        </NavLink>

        <div className="identity-panel" aria-live="polite">
          <label htmlFor="demo-identity">Демо-пользователь</label>
          {state === "error" ? (
            <div className="identity-error" role="alert">
              <span>{error}</span>
              <button type="button" onClick={reload}>
                Повторить
              </button>
            </div>
          ) : (
            <div className="identity-controls">
              <select
                id="demo-identity"
                value={selectedIdentity?.id ?? ""}
                onChange={(event) => selectIdentity(event.target.value)}
                disabled={state === "loading" || identities.length === 0}
              >
                {state === "loading" && <option value="">Загрузка…</option>}
                {state === "ready" && identities.length === 0 && (
                  <option value="">Нет демопользователей</option>
                )}
                {identities.map((identity) => (
                  <option key={identity.id} value={identity.id}>
                    {identity.name}
                  </option>
                ))}
              </select>
              {selectedIdentity && (
                <span className={`role-badge role-badge--${selectedIdentity.role}`}>
                  {selectedIdentity.role === "business" ? "Бизнес" : "Команда"}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <nav className="main-nav" aria-label="Основная навигация">
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  );
}

function SectionPage({ section }: { section: keyof typeof routeContent }) {
  const content = routeContent[section];

  return (
    <section className="section-page" aria-labelledby={`${section}-title`}>
      <div className="section-heading">
        <h1 id={`${section}-title`}>{content.title}</h1>
        <p>{content.description}</p>
      </div>
      <div className="section-rule" aria-hidden="true" />
    </section>
  );
}
