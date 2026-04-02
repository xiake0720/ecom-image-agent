export const assetCategories = ["全部资源", "商品白底图", "商品参考图", "背景参考图", "主图结果", "详情长图结果", "收藏素材", "最近上传"];

export const assetStats = [
  { label: "总资源数", value: "2,641" },
  { label: "主图结果数", value: "1,128" },
  { label: "背景图数", value: "486" },
  { label: "最近新增", value: "76" },
];

export const assetsMock = Array.from({ length: 12 }).map((_, idx) => ({
  id: `asset-${idx}`,
  name: `tea_asset_${idx + 1}.png`,
  size: idx % 2 === 0 ? "1080x1440" : "750x3000",
  date: `2026-03-${String((idx % 8) + 18).padStart(2, "0")}`,
  tags: idx % 2 === 0 ? "主图, 茶叶" : "详情, 参数",
  source: idx % 2 === 0 ? "主图任务" : "详情任务",
  category: assetCategories[idx % assetCategories.length],
  cover: `/mock/asset-${(idx % 4) + 1}.svg`,
}));
