from __future__ import annotations

import streamlit as st

from src.core.constants import DEFAULT_COPY_TONE, DEFAULT_SHOT_COUNT, OUTPUT_SIZE_OPTIONS, PLATFORM_OPTIONS


def render_task_form() -> dict[str, object]:
    brand_name = st.text_input("品牌名", value="山野茶事")
    product_name = st.text_input("产品名", value="高山绿茶")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=0)
    output_size = st.selectbox("尺寸", OUTPUT_SIZE_OPTIONS, index=0)
    shot_count = st.slider("张数", min_value=1, max_value=6, value=DEFAULT_SHOT_COUNT)
    copy_tone = st.text_input("文案风格", value=DEFAULT_COPY_TONE)
    return {
        "brand_name": brand_name.strip(),
        "product_name": product_name.strip(),
        "platform": platform,
        "output_size": output_size,
        "shot_count": shot_count,
        "copy_tone": copy_tone.strip(),
    }

