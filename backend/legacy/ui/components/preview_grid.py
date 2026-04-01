"""结果网格组件。"""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_preview_grid(image_paths: list[str]) -> None:
    """按双列网格展示最终图片。"""

    if not image_paths:
        st.info("生成完成后会在这里展示最终图片。")
        return

    columns = st.columns(2)
    for index, image_path in enumerate(image_paths):
        with columns[index % 2]:
            st.image(image_path, width="stretch", caption=Path(image_path).name)
