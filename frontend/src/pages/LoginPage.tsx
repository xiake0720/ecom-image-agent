import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { extractApiErrorMessage } from "../services/apiError";
import "../styles/console.css";

/** 登录页：接入真实 v1 认证 API。 */
export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setErrorMessage("");
    try {
      await login({ email, password });
      const redirect = searchParams.get("redirect") || "/main-images";
      navigate(redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : "/main-images", { replace: true });
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="console-shell login-shell">
      <form className="section-card login-card" onSubmit={handleSubmit}>
        <h2>ECOM AI</h2>
        <p>登录电商图片生产工作台，任务历史和生成记录会按当前账号隔离。</p>
        <div className="login-form">
          <label className="login-field">
            邮箱
            <input
              className="input"
              placeholder="user@example.com"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="login-field">
            密码
            <input
              className="input"
              placeholder="至少 8 位"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>
          {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? "登录中..." : "登录"}
          </button>
        </div>
        <div className="login-footer">
          <Link to="/register">去注册</Link>
        </div>
      </form>
    </div>
  );
}
