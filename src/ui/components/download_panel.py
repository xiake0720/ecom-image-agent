from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_download_panel(image_paths: list[str], zip_path: str | None) -> None:
    for image_path in image_paths:
        path = Path(image_path)
        st.download_button(
            label=f"下载 {path.name}",
            data=path.read_bytes(),
            file_name=path.name,
            mime="image/png",
            key=f"download-{path.name}",
        )
    if zip_path:
        archive = Path(zip_path)
        st.download_button(
            label="下载全部 ZIP",
            data=archive.read_bytes(),
            file_name=archive.name,
            mime="application/zip",
            key="download-zip",
        )

