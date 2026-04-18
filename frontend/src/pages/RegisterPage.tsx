import { Link, useNavigate } from "react-router-dom";
import "../styles/console.css";

/**
 * 注册入口壳页。
 * 说明：当前仓库未接入真实鉴权 API，本页只冻结一期入口与页面边界。
 */
export function RegisterPage() {
  const navigate = useNavigate();

  return (
    <div className="console-shell login-shell">
      <div className="section-card login-card">
        <h2>创建账号</h2>
        <p>一期保留注册入口，当前仅提供前端页面壳，不接真实鉴权服务。</p>
        <div className="login-form">
          <input className="input" placeholder="用户名" style={{ width: "100%" }} />
          <input className="input" placeholder="手机号 / 邮箱" style={{ width: "100%" }} />
          <input className="input" placeholder="密码" type="password" style={{ width: "100%" }} />
          <input className="input" placeholder="确认密码" type="password" style={{ width: "100%" }} />
          <button className="btn-primary" style={{ width: "100%" }} onClick={() => navigate("/login")}>
            注册入口保留，返回登录
          </button>
        </div>
        <div className="login-footer">
          <Link to="/login">已有账号，去登录</Link>
          <Link to="/main-images">返回工作台</Link>
        </div>
      </div>
    </div>
  );
}
