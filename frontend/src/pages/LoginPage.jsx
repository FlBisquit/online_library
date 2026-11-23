import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ErrorMessage } from "../components/ErrorMessage";
import { RegisterPage } from "./RegisterPage";

export const LoginPage = () => {
  const { login } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    setError(null);
  };

  if (mode === "register") {
    return <RegisterPage />;
  }

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2>Вход в библиотеку</h2>
        <ErrorMessage message={error} />
        <label>
          Email
          <input
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </label>
        <label>
          Пароль
          <input
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? "Вход..." : "Войти"}
        </button>
        <button type="button" className="btn" onClick={() => switchMode("register")}>
          Нет аккаунта? Зарегистрироваться
        </button>
      </form>
    </div>
  );
};
