export const templateCategories = ["全部模板", "主图模板", "详情长图模板", "我的模板", "系统模板"];

export const templateList = Array.from({ length: 9 }).map((_, idx) => ({
  id: `tpl-${idx + 1}`,
  name: idx % 2 === 0 ? `茶叶主图·高转化版 ${idx + 1}` : `茶叶详情长图·清晰参数版 ${idx + 1}`,
  platform: ["天猫", "京东", "拼多多"][idx % 3],
  type: idx % 2 === 0 ? "主图模板" : "详情长图模板",
  style: ["高端极简", "转化导向", "清晰参数型"][idx % 3],
  updatedAt: `2026-03-${String((idx % 9) + 11).padStart(2, "0")}`,
  usage: 160 + idx * 12,
  cover: `/mock/template-${(idx % 3) + 1}.svg`,
}));
