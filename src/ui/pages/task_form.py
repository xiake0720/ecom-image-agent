"""任务参数表单页。

文件位置：
- `src/ui/pages/task_form.py`

核心职责：
- 收集品牌、产品、平台、尺寸、张数、文案风格等基础参数
<<<<<<< HEAD
- 收集 workflow 版本、overlay fallback、缓存和参考图数量等运行控制参数
=======
- 收集缓存、prompt 构建模式、参考图数量等调试参数

主要调用方：
- `src/ui/pages/home.py`
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
"""

from __future__ import annotations

import streamlit as st

from src.core.config import get_settings
<<<<<<< HEAD
from src.core.constants import DEFAULT_COPY_TONE, OUTPUT_SIZE_OPTIONS, PLATFORM_OPTIONS
=======
from src.core.constants import DEFAULT_COPY_TONE, DEFAULT_SHOT_COUNT, OUTPUT_SIZE_OPTIONS, PLATFORM_OPTIONS
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c


def render_task_form() -> dict[str, object]:
    """渲染任务表单并返回 workflow 初始参数。"""
    settings = get_settings()
    debug_mode = str(settings.env or "dev").strip().lower() in {"dev", "debug", "local"}
<<<<<<< HEAD
    default_platform = settings.default_platform if settings.default_platform in PLATFORM_OPTIONS else PLATFORM_OPTIONS[0]

    brand_name = st.text_input("品牌名", value="阅千峰")
    product_name = st.text_input("产品名", value="凤凰单丛")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=PLATFORM_OPTIONS.index(default_platform))
    output_size = st.selectbox("尺寸", OUTPUT_SIZE_OPTIONS, index=0)
    shot_count = st.slider("张数", min_value=1, max_value=8, value=max(1, min(8, int(settings.default_shot_count))))
=======

    brand_name = st.text_input("品牌名", value="阅千峰")
    product_name = st.text_input("产品名", value="凤尾单丛")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=0)
    output_size = st.selectbox("尺寸", OUTPUT_SIZE_OPTIONS, index=0)
    shot_count = st.slider("张数", min_value=1, max_value=6, value=DEFAULT_SHOT_COUNT)
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
    copy_tone = st.text_input("文案风格", value=DEFAULT_COPY_TONE)

    st.caption("运行控制")
    cache_enabled = st.checkbox("启用缓存", value=bool(settings.enable_node_cache))
    ignore_cache = st.checkbox("忽略缓存强制重跑", value=debug_mode)
    if cache_enabled and not ignore_cache:
        st.warning("当前启用缓存且未忽略缓存，本次调试可能命中旧结果。")
    elif ignore_cache:
        st.info("当前将忽略节点缓存，适合调试 provider / prompt / 贴字变更。")

    with st.expander("高级选项", expanded=False):
<<<<<<< HEAD
        workflow_version = st.selectbox(
            "Workflow 版本",
            options=["v2", "v1"],
            index=0 if str(settings.workflow_version or "v2").strip().lower() == "v2" else 1,
            help="v2 为新三步链路，v1 为历史链路兼容模式。",
        )
        enable_overlay_fallback = st.checkbox(
            "启用 overlay fallback",
            value=bool(settings.enable_overlay_fallback),
            help="v2 下优先图内直接带字，单张失败时允许改走 Pillow 后贴字兜底。",
        )
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        prompt_build_mode = st.selectbox(
            "Prompt 生成模式",
            options=["per_shot", "batch"],
            index=0 if settings.resolve_prompt_build_mode() == "per_shot" else 1,
            help="per_shot 逐张生成质量更稳，batch 一次生成整组更省成本。",
        )
        analyze_max_reference_images = st.selectbox(
            "视觉分析参考图数量",
            options=[1, 2],
            index=0 if settings.analyze_max_reference_images <= 1 else 1,
            help="默认优先 1 张主 product 图，可选再带 1 张 detail 图。",
        )
        render_max_reference_images = st.selectbox(
            "生图参考图数量",
            options=[1, 2],
            index=0 if settings.render_max_reference_images <= 1 else 1,
            help="默认优先 1 张主参考图，可选再带 1 张 detail 图。",
        )

    return {
        "brand_name": brand_name.strip(),
        "product_name": product_name.strip(),
        "platform": platform,
        "output_size": output_size,
        "shot_count": shot_count,
        "copy_tone": copy_tone.strip(),
        "cache_enabled": cache_enabled,
        "ignore_cache": ignore_cache,
<<<<<<< HEAD
        "workflow_version": workflow_version,
        "enable_overlay_fallback": enable_overlay_fallback,
=======
>>>>>>> e13a90721840a4fdd5e08d65fcd4e41b9f8a738c
        "prompt_build_mode": prompt_build_mode,
        "analyze_max_reference_images": analyze_max_reference_images,
        "render_max_reference_images": render_max_reference_images,
    }
