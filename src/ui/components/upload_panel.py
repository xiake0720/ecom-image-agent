"""上传区域组件。"""

from __future__ import annotations

import streamlit as st


def render_upload_panel() -> dict[str, object]:
    """渲染主图与参考图上传区。"""

    st.subheader("文件上传")
    white_bg = st.file_uploader(
        "上传外包装白底图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        help="必传，建议上传完整包装白底图。",
    )
    reference_images = st.file_uploader(
        "上传参考图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="可选，建议上传展开图或包装细节图，最多保留前 4 张。",
    )
    return {
        "white_bg": white_bg,
        "references": list(reference_images or [])[:4],
    }
