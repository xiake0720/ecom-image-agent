import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { extractApiErrorMessage } from "../services/apiError";
import "../styles/console.css";

/** 注册页：创建真实账号并立即进入登录态。 */
export function RegisterPage() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [nickname, setNickname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrorMessage("");
    if (password !== confirmPassword) {
      setErrorMessage("两次输入的密码不一致");
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, password, nickname: nickname || undefined });
      navigate("/main-images", { replace: true });
    } catch (error) {
      setErrorMessage(extractApiErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="console-shell login-shell">
      <form className="section-card login-card" onSubmit={handleSubmit}>
        <h2>创建账号</h2>
        <p>注册后即可创建主图 / 详情图任务，并在历史任务中按账号查看。</p>
        <div className="login-form">
          <label className="login-field">
            昵称
            <input
              className="input"
              placeholder="可选"
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              maxLength={100}
            />
          </label>
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
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>
          <label className="login-field">
            确认密码
            <input
              className="input"
              placeholder="再次输入密码"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>
          {errorMessage ? <p className="form-error">{errorMessage}</p> : null}
          <button className="btn-primary" type="submit" disabled={submitting}>
            {submitting ? "注册中..." : "注册并进入工作台"}
          </button>
        </div>
        <div className="login-footer">
          <Link to="/login">已有账号，去登录</Link>
        </div>
      </form>
    </div>
  );
}
