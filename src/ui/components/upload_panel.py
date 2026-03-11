from __future__ import annotations

import streamlit as st


def render_upload_panel():
    return st.file_uploader(
        "上传商品素材图",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="支持白底图、产品图、细节图多张上传。",
    )

