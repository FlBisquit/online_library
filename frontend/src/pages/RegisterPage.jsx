import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { ErrorMessage } from "../components/ErrorMessage";

export const RegisterPage = () => {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({ email, password, fullName, phone });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2>Регистрация в библиотеке</h2>
        <ErrorMessage message={error} />
        <label>
          ФИО
          <input className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </label>
        <label>
          Email
          <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Пароль
          <input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <label>
          Телефон
          <input className="input" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? "Регистрация..." : "Зарегистрироваться"}
        </button>
      </form>
    </div>
  );
};
