import { Link, useNavigate } from "react-router-dom";
import "../styles/console.css";

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <div className="console-shell login-shell">
      <div className="section-card login-card">
        <h2>ECOM AI</h2>
        <p>登录电商图片生产工作台</p>
        <div className="login-form">
          <input className="input" placeholder="用户名" style={{ width: "100%" }} />
          <input className="input" placeholder="密码" type="password" style={{ width: "100%" }} />
          <label style={{ fontSize: 13, color: "#475569", display: "flex", alignItems: "center", gap: 8 }}>
            <input type="checkbox" defaultChecked /> 记住登录状态
          </label>
          <button className="btn-primary" style={{ width: "100%" }} onClick={() => navigate("/main-images")}>
            登录
          </button>
        </div>
        <div className="login-footer">
          <a href="#">忘记密码</a>
          <Link to="/main-images">返回首页</Link>
        </div>
      </div>
    </div>
  );
}
