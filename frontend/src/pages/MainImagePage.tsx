import { useState } from "react";
import { http } from "../services/http";

/**
 * 主图生成页。
 * 设计意图：先实现最小可联调版本，提交 multipart 到后端 API。
 */
export function MainImagePage() {
  const [productName, setProductName] = useState("");
  const [whiteBg, setWhiteBg] = useState<File | null>(null);
  const [message, setMessage] = useState("未提交");

  async function submit() {
    if (!whiteBg) {
      setMessage("请先上传白底图");
      return;
    }
    const form = new FormData();
    form.append("product_name", productName);
    form.append("white_bg", whiteBg);
    const resp = await http.post("/image/generate-main", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    setMessage(`任务已完成：${resp.data.data.task_id}`);
  }

  return (
    <div>
      <h2>主图生成</h2>
      <input placeholder="商品标题" value={productName} onChange={(e) => setProductName(e.target.value)} />
      <input type="file" accept="image/*" onChange={(e) => setWhiteBg(e.target.files?.[0] ?? null)} />
      <button onClick={submit}>提交生成</button>
      <p>{message}</p>
    </div>
  );
}
