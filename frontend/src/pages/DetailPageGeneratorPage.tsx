import { useState } from "react";
import { http } from "../services/http";

/**
 * 详情页生成页。
 * 输入：平台+风格+文案。
 * 输出：后端返回的模块化 JSON 预览。
 */
export function DetailPageGeneratorPage() {
  const [title, setTitle] = useState("");
  const [platform, setPlatform] = useState("tmall");
  const [style, setStyle] = useState("premium");
  const [preview, setPreview] = useState<string>("");

  async function generate() {
    const resp = await http.post("/detail/generate", {
      title,
      platform,
      style,
      selling_points: ["高山原料", "回甘持久", "礼赠体面"],
    });
    setPreview(JSON.stringify(resp.data.data.preview_data, null, 2));
  }

  return (
    <div>
      <h2>详情页生成</h2>
      <input placeholder="商品标题" value={title} onChange={(e) => setTitle(e.target.value)} />
      <select value={platform} onChange={(e) => setPlatform(e.target.value)}>
        <option value="tmall">天猫</option>
        <option value="pinduoduo">拼多多</option>
      </select>
      <select value={style} onChange={(e) => setStyle(e.target.value)}>
        <option value="premium">高端</option>
        <option value="value">性价比</option>
      </select>
      <button onClick={generate}>生成详情页结构</button>
      <pre>{preview}</pre>
    </div>
  );
}
