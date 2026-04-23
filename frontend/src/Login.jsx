import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, setToken } from "./api";
import { parseJwt } from "./auth/auth";
import "./Login.css";

export default function Login() {
  const navigate = useNavigate();
  const { companySlug } = useParams();

  const isGroupLogin = companySlug === "group";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  function resetMessages() {
    setError("");
  }

  function goAfterLogin(accessToken) {
    const payload = parseJwt(accessToken);

    if (payload?.role === "GROUP_ADMIN") {
      navigate("/group/app", { replace: true });
      return;
    }

    navigate(`/${companySlug}/app`, { replace: true });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    resetMessages();

    if (!companySlug) return setError("URL inválida.");
    if (!email.trim()) return setError("Coloca o email.");
    if (!password.trim()) return setError("Coloca a password.");

    setLoading(true);
    try {
      const data = await api.login(email, password);
      setToken(data.access_token);
      goAfterLogin(data.access_token);
    } catch (err) {
      setError(err?.message || "Ocorreu um erro. Tenta novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon" aria-hidden="true">
            🔐
          </div>

          <h2 className="auth-title">{isGroupLogin ? "Login do Grupo" : "Login"}</h2>

          <p className="auth-subtitle">
            {isGroupLogin
              ? "Entra para ver os resultados do grupo."
              : "Entra para aceder ao painel."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <label className="field">
            <span className="label">Email</span>
            <input
              className="input"
              type="email"
              placeholder="exemplo@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              inputMode="email"
            />
          </label>

          <label className="field">
            <span className="label">Password</span>

            <div className="password-wrap">
              <input
                className="input"
                placeholder="••••••••"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />

              <button
                type="button"
                className="ghost"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Esconder password" : "Mostrar password"}
              >
                {showPassword ? "Ocultar" : "Mostrar"}
              </button>
            </div>
          </label>

          <button className="primary" type="submit" disabled={loading}>
            {loading ? "A processar..." : "Entrar"}
          </button>

          {error && <p className="msg error">{error}</p>}
        </form>
      </div>
    </div>
  );
}