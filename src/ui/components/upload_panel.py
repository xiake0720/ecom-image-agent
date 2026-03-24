"""上传区域组件。"""

from __future__ import annotations

import streamlit as st


def render_upload_panel() -> dict[str, object]:
    """渲染产品参考图与背景风格参考图上传区。"""

    st.subheader("文件上传")
    white_bg = st.file_uploader(
        "上传外包装白底图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        help="必传，建议上传完整包装白底图，作为产品保真主参考。",
    )
    product_reference_images = st.file_uploader(
        "上传产品参考图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="可选，用于上传展开图、包装细节图或内部结构图，最多保留前 4 张。",
    )
    background_style_reference_images = st.file_uploader(
        "上传背景风格参考图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="可选，仅用于学习背景氛围、色调和场景语言，不会替换产品包装。",
    )
    return {
        "white_bg": white_bg,
        "product_references": list(product_reference_images or [])[:4],
        "background_style_references": list(background_style_reference_images or [])[:4],
    }
