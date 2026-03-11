# 架构说明

## 一、当前项目形态
本项目当前仍采用 **Python 3.11 + Streamlit 单体应用** 形态，目标是在本地环境中验证电商自动生图流程的可行性。

需要特别说明的是：
- 第一阶段 **Mock MVP** 已经完成并归档
- 当前仓库已经进入第二阶段**真实 provider 接线阶段**
- 第二阶段的变化是“在既有骨架上接入真实 provider”，不是重做架构，也不是扩展到前后端分离系统

当前仍然坚持：
- 不做前后端分离
- 不接数据库
- 不做云部署
- 不接真实 OCR 运行时
- 不接真实 rembg 运行时
- 不做多模型 fallback

---

## 二、总体分层
项目按职责拆分为以下层次：

### 1. UI 层
位置：`src/ui/`  
职责：
- Streamlit 页面渲染
- 上传组件
- 参数表单
- 结果预览
- 下载按钮
- 页面状态管理

唯一页面入口为：
- `streamlit_app.py`

### 2. Workflow 层
位置：`src/workflows/`  
职责：
- LangGraph 状态定义
- 图结构定义
- 节点编排
- 节点执行顺序控制
- 中间结果流转

### 3. Domain 层
位置：`src/domain/`  
职责：
- 定义任务对象
- 定义商品分析结果
- 定义图组规划结果
- 定义文案结构
- 定义布局结构
- 定义生成结果与质检结果

所有工作流节点之间优先通过结构化 schema 进行交互。

### 4. Provider 层
位置：`src/providers/`  
职责：
- 文本模型 provider 接口
- 图片模型 provider 接口
- mock 实现
- 当前真实 provider 实现

当前仓库中：
- 商品分析视觉 provider 为 `NVIDIAVisionProductAnalysisProvider`
- 文本真实 provider 为 `NVIDIATextProvider`
- 图片真实 provider 为 `RunApiGeminiImageProvider`

provider 层负责封装真实模型调用，workflow 节点不直接处理底层 HTTP 细节。

### 5. Service 层
位置：`src/services/`  
职责：
- 本地文件存储
- 结果导出
- 图片后处理
- Pillow 文本渲染
- 商品分析辅助逻辑
- 图组规划辅助逻辑
- 质检逻辑
- OCR / rembg 占位服务

---

## 三、数据流
当前阶段的数据流如下：

1. 用户通过 Streamlit 页面上传商品图并填写参数  
2. 系统创建 `task_id`  
3. 原始输入写入 `outputs/tasks/{task_id}/inputs/`  
4. 工作流依次执行：
   - `ingest_assets`
   - `analyze_product`
   - `plan_shots`
   - `generate_copy`
   - `generate_layout`
   - `build_prompts`
   - `render_images`
   - `overlay_text`
   - `run_qc`
   - `finalize`
5. 每个节点按约定落盘 JSON 或图片产物  
6. Streamlit 页面读取结果目录并完成预览与下载

第二阶段的核心变化仅在于：
- `analyze_product` 支持从 mock 切换到真实视觉 provider
- 其余文本规划节点继续走真实文本 provider
- 输出目录结构与任务回放方式保持不变

---

## 四、当前输出产物
每个任务目录下至少包含：
- `task.json`
- `product_analysis.json`
- `shot_plan.json`
- `copy_plan.json`
- `layout_plan.json`
- `image_prompt_plan.json`
- `qc_report.json`
- `generated/`
- `final/`
- `previews/`
- `exports/`

---

## 五、当前阶段边界
当前架构仍刻意保持简单，原因如下：
- 保持本地流程闭环
- 保持节点契约稳定
- 保持输出目录结构稳定
- 让 mock / real provider 能在同一骨架内切换
- 避免在真实能力接入初期过度扩展基础设施

因此当前阶段仍然不引入：
- FastAPI
- 数据库
- 登录鉴权
- 消息队列
- 云服务部署
- 多模型复杂路由

---

## 六、当前阶段说明
当前仓库不是“只剩 mock”的状态，也不是“生产可用系统”的状态。

更准确的表达是：
- 第一阶段骨架已稳定
- 第二阶段已完成真实 provider 接线
- OCR、rembg、fallback 仍未进入当前范围
- 现阶段重点仍然是保持链路清晰、错误显式、产物可落盘和可回放

---

## 七、结论
当前架构仍适合作为本项目的稳定基线。  
第二阶段只是 provider 接线与模式切换，不应推翻现有 Streamlit 单体应用、任务目录结构与工作流骨架。

