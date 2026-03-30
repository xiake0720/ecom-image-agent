"""任务参数表单。

文件位置：
- `src/ui/pages/task_form.py`

职责：
- 渲染面向最终用户的极简输入表单
- 只暴露整套图生成所需的高层参数
- 不再暴露逐张图文案与复杂元素配置
"""

from __future__ import annotations

import streamlit as st

from src.core.config import get_settings
from src.core.constants import ASPECT_RATIO_OPTIONS, IMAGE_SIZE_OPTIONS

STYLE_TYPE_OPTIONS = [
    "高端极简",
    "东方雅致",
    "国风高级",
    "自然生活方式",
    "深色茶席",
    "浅色奶油系",
    "礼赠商务",
]


def render_task_form() -> dict[str, object]:
    """渲染整套图生成所需的最小高层输入。"""

    settings = get_settings()

    st.subheader("基础参数")
    col_left, col_right = st.columns(2)
    with col_left:
        brand_name = st.text_input("品牌名", value="", placeholder="可选，例如：示例品牌")
    with col_right:
        product_name = st.text_input("商品名", value="", placeholder="可选，例如：高山乌龙茶礼")

    style_type = st.selectbox(
        "整体风格类型",
        STYLE_TYPE_OPTIONS,
        index=0,
        help="这是整套 8 张图的统一风格方向，系统会基于它自动规划每张图。",
    )
    style_notes = st.text_area(
        "风格补充说明",
        value="",
        height=90,
        max_chars=80,
        placeholder="可选，例如：更高级、更克制、暖调一点、不要太暗、少装饰、通透干净",
        help="只需一句简短补充说明，系统会自动转成整套图的风格控制策略。",
    )

    with st.expander("高级设置", expanded=False):
        shot_count = st.number_input(
            "生成张数",
            min_value=1,
            max_value=8,
            value=settings.default_shot_count,
            step=1,
            help="默认生成 8 张整套电商图。",
        )
        aspect_ratio = st.selectbox(
            "比例",
            ASPECT_RATIO_OPTIONS,
            index=ASPECT_RATIO_OPTIONS.index(settings.default_image_aspect_ratio),
        )
        image_size = st.selectbox(
            "分辨率",
            IMAGE_SIZE_OPTIONS,
            index=IMAGE_SIZE_OPTIONS.index(settings.default_image_size),
        )

    return {
        "brand_name": brand_name.strip(),
        "product_name": product_name.strip(),
        "shot_count": int(shot_count),
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "style_type": style_type,
        "style_notes": style_notes.strip(),
    }
