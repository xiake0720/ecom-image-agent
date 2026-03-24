"""任务参数表单。"""

from __future__ import annotations

import streamlit as st

from src.core.config import get_settings
from src.core.constants import ASPECT_RATIO_OPTIONS, IMAGE_SIZE_OPTIONS, PLATFORM_OPTIONS
from src.domain.task import CopyMode

STYLE_TYPE_OPTIONS = [
    "高端极简",
    "东方雅致",
    "国风高级",
    "自然生活方式",
    "深色茶席",
    "浅色奶油系",
    "礼赠商务",
    "自定义",
]


def render_task_form() -> dict[str, object]:
    """渲染 v2 主链所需的任务入参。"""

    settings = get_settings()
    st.subheader("必要参数")
    brand_name = st.text_input("品牌名", value="示例品牌")
    product_name = st.text_input("商品名", value="示例茶礼")
    platform = st.selectbox("平台", PLATFORM_OPTIONS, index=0, disabled=len(PLATFORM_OPTIONS) == 1)
    shot_count = st.number_input("生成张数", min_value=1, max_value=8, value=settings.default_shot_count, step=1)
    aspect_ratio = st.selectbox("比例", ASPECT_RATIO_OPTIONS, index=ASPECT_RATIO_OPTIONS.index(settings.default_image_aspect_ratio))
    image_size = st.selectbox("分辨率", IMAGE_SIZE_OPTIONS, index=IMAGE_SIZE_OPTIONS.index(settings.default_image_size))

    st.subheader("图内文案")
    copy_mode = st.selectbox(
        "文案模式",
        [CopyMode.MIXED.value, CopyMode.MANUAL.value, CopyMode.AUTO.value],
        index=0,
        help="mixed：用户输入优先，缺失字段自动补齐；manual：只使用用户输入；auto：全部由新流程自动生成。",
    )
    title_text = st.text_input("主标题（可选，建议 4-8 字）", value="", max_chars=20)
    subtitle_text = st.text_input("副标题（可选，建议 8-15 字）", value="", max_chars=30)
    selling_points_raw = st.text_area(
        "卖点信息（可选，多条换行）",
        value="",
        height=96,
        help="每行一条，系统会按原文优先使用，不会擅自改写。",
    )

    st.subheader("风格控制")
    style_type = st.selectbox("风格类型", STYLE_TYPE_OPTIONS, index=0)
    style_preferences = st.text_area(
        "风格偏好（可选）",
        value="",
        height=96,
        help="例如：更克制、更干净、不要太暗、暖调、通透、不要太 AI 感。",
    )
    custom_elements_raw = st.text_area(
        "自定义元素（可选，多条换行）",
        value="",
        height=96,
        help="例如：竹影、白瓷杯、木托盘、茶席、石板、礼盒、花枝。",
    )
    avoid_elements_raw = st.text_area(
        "避免元素（可选，多条换行）",
        value="",
        height=96,
        help="例如：不要人物、不要金龙纹、不要太多花、不要复杂背景。",
    )

    return {
        "brand_name": brand_name.strip(),
        "product_name": product_name.strip(),
        "platform": platform,
        "shot_count": int(shot_count),
        "aspect_ratio": aspect_ratio,
        "image_size": image_size,
        "copy_mode": copy_mode,
        "title_text": title_text.strip(),
        "subtitle_text": subtitle_text.strip(),
        "selling_points": _normalize_multiline_list(selling_points_raw),
        "style_type": style_type,
        "style_preferences": style_preferences.strip(),
        "custom_elements": _normalize_multiline_list(custom_elements_raw),
        "avoid_elements": _normalize_multiline_list(avoid_elements_raw),
    }


def _normalize_multiline_list(raw_text: str) -> list[str]:
    """把多行文本归一化为字符串列表。"""

    normalized = raw_text.replace("\r", "\n")
    items: list[str] = []
    for part in normalized.replace("，", ",").split("\n"):
        for inner in part.split(","):
            item = inner.strip()
            if item:
                items.append(item)
    return items
