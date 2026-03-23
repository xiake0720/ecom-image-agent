"""任务参数表单。"""

from __future__ import annotations

import streamlit as st

from src.core.config import get_settings
from src.core.constants import ASPECT_RATIO_OPTIONS, IMAGE_SIZE_OPTIONS, PLATFORM_OPTIONS


def render_task_form() -> dict[str, object]:
    """渲染精简后的必要入参。"""

    settings = get_settings()
    st.subheader("必要参数")
    brand_name = st.text_input("品牌名", value="示例品牌")
    product_name = st.text_input("商品名", value="示例茶礼")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=0, disabled=len(PLATFORM_OPTIONS) == 1)
    shot_count = st.number_input("生成张数", min_value=1, max_value=8, value=settings.default_shot_count, step=1)
    aspect_ratio = st.selectbox("比例", ASPECT_RATIO_OPTIONS, index=ASPECT_RATIO_OPTIONS.index(settings.default_image_aspect_ratio))
    image_size = st.selectbox("分辨率", IMAGE_SIZE_OPTIONS, index=IMAGE_SIZE_OPTIONS.index(settings.default_image_size))
    return {
        "brand_name": brand_name.strip(),
        "product_name": product_name.strip(),
        "platform": platform,
        "shot_count": int(shot_count),
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
    }
