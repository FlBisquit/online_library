import { useState } from "react";
import { useAuth } from "./auth/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { CatalogPage } from "./pages/CatalogPage";
import { MyLoansPage } from "./pages/MyLoansPage";
import { LibrarianPage } from "./pages/LibrarianPage";
import { AdminPage } from "./pages/AdminPage";

export const App = () => {
  const { user, initialized, logout } = useAuth();
  const [activeId, setActiveId] = useState("catalog");

  if (!initialized) {
    return <div className="page">Загрузка...</div>;
  }

  if (!user) {
    return <LoginPage />;
  }

  const isReader = (user.roles ?? []).includes("reader") || user.is_reader;
  const isLibrarian = (user.roles ?? []).includes("librarian") || user.is_librarian;
  const isAdmin = (user.roles ?? []).includes("admin") || user.is_admin;

  const tabs = [
    { id: "catalog", label: "Каталог", component: CatalogPage },
    ...(isReader ? [{ id: "loans", label: "Мои выдачи", component: MyLoansPage }] : []),
    ...(isLibrarian ? [{ id: "librarian", label: "Панель библиотекаря", component: LibrarianPage }] : []),
    ...(isAdmin ? [{ id: "admin", label: "Админка", component: AdminPage }] : []),
  ];

  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0];
  const ActiveComponent = activeTab?.component;

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Игнорируем ошибки выхода.
    }
  };

  return (
    <div className="app">
      <nav className="nav">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`nav-item ${activeTab.id === tab.id ? "active" : ""}`}
            onClick={() => setActiveId(tab.id)}
          >
            {tab.label}
          </button>
        ))}
        <button className="nav-item" onClick={handleLogout}>
          Выход
        </button>
      </nav>
      <div className="content">
        {ActiveComponent ? <ActiveComponent /> : <div className="page">Нет доступных разделов.</div>}
      </div>
    </div>
  );
};
