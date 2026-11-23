import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { BooksAdminPage } from "./BooksAdminPage";
import { UsersAdminPage } from "./UsersAdminPage";
import { ActionLogPage } from "./ActionLogPage";
import { ReportPage } from "./ReportPage";

const TABS = [
  { id: "books", label: "Книги", component: BooksAdminPage },
  { id: "users", label: "Пользователи", component: UsersAdminPage },
  { id: "log", label: "Журнал", component: ActionLogPage },
  { id: "report", label: "Отчёт", component: ReportPage },
];

export const AdminPage = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState("books");
  const ActivePage = TABS.find((tab) => tab.id === activeTab)?.component ?? BooksAdminPage;

  return (
    <div className="page">
      <h2>Панель администратора</h2>
      {user && <div className="admin-user">{user.email}</div>}
      <div className="sub-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`nav-item ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <ActivePage />
    </div>
  );
};
