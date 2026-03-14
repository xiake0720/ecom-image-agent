from __future__ import annotations

import streamlit as st

from src.core.config import get_settings
from src.core.constants import DEFAULT_COPY_TONE, DEFAULT_SHOT_COUNT, OUTPUT_SIZE_OPTIONS, PLATFORM_OPTIONS


def render_task_form() -> dict[str, object]:
    settings = get_settings()
    debug_mode = str(settings.env or "dev").strip().lower() in {"dev", "debug", "local"}

    brand_name = st.text_input("品牌名", value="阅千峰")
    product_name = st.text_input("产品名", value="凤凰单丛")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=0)
    output_size = st.selectbox("尺寸", OUTPUT_SIZE_OPTIONS, index=0)
    shot_count = st.slider("张数", min_value=1, max_value=6, value=DEFAULT_SHOT_COUNT)
    copy_tone = st.text_input("文案风格", value=DEFAULT_COPY_TONE)

    st.caption("运行控制")
    cache_enabled = st.checkbox("启用缓存", value=bool(settings.enable_node_cache))
    ignore_cache = st.checkbox("忽略缓存强制重跑", value=debug_mode)
    if cache_enabled and not ignore_cache:
        st.warning("当前启用缓存且未忽略缓存，本次调试可能命中旧结果。")
    elif ignore_cache:
        st.info("当前将忽略节点缓存，适合调试 provider / prompt / 贴字变更。")

    with st.expander("高级选项", expanded=False):
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
        "prompt_build_mode": prompt_build_mode,
        "analyze_max_reference_images": analyze_max_reference_images,
        "render_max_reference_images": render_max_reference_images,
    }
