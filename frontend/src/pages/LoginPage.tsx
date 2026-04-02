import { Link, useNavigate } from "react-router-dom";
import "../styles/console.css";

export function LoginPage() {
  const navigate = useNavigate();
  return (
    <div className="console-shell" style={{ display: "grid", placeItems: "center" }}>
      <div className="section-card" style={{ width: 420, padding: 28 }}>
        <h2 style={{ margin: 0 }}>ECOM AI</h2>
        <p style={{ color: "#64748b" }}>登录电商图片生产工作台</p>
        <input className="input" placeholder="用户名" style={{ width: "100%", marginBottom: 10 }} />
        <input className="input" placeholder="密码" type="password" style={{ width: "100%", marginBottom: 12 }} />
        <label style={{ fontSize: 13, color: "#475569", display: "block", marginBottom: 12 }}>
          <input type="checkbox" defaultChecked /> 记住登录状态
        </label>
        <button className="btn-primary" style={{ width: "100%" }} onClick={() => navigate("/main-images")}>登录</button>
        <div style={{ marginTop: 12, display: "flex", justifyContent: "space-between", fontSize: 13 }}>
          <a href="#">忘记密码</a>
          <Link to="/main-images">返回首页</Link>
        </div>
      </div>
    </div>
  );
}
