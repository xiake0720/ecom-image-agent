from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_download_panel(
    image_paths: list[str],
    zip_path: str | None,
    zip_label: str = "下载全部 ZIP",
    *,
    bundle_zip_path: str | None = None,
    bundle_zip_label: str = "下载完整任务包 ZIP",
) -> None:
    for image_path in image_paths:
        path = Path(image_path)
        if not path.exists():
            continue
        st.download_button(
            label=f"下载 {path.name}",
            data=path.read_bytes(),
            file_name=path.name,
            mime="image/png",
            key=f"download-{path.name}",
        )
    zip_col1, zip_col2 = st.columns(2)
    if zip_path:
        archive = Path(zip_path)
        if archive.exists():
            zip_col1.download_button(
                label=zip_label,
                data=archive.read_bytes(),
                file_name=archive.name,
                mime="application/zip",
                key=f"download-zip-{archive.name}",
                use_container_width=True,
            )
    if bundle_zip_path:
        bundle = Path(bundle_zip_path)
        if bundle.exists():
            zip_col2.download_button(
                label=bundle_zip_label,
                data=bundle.read_bytes(),
                file_name=bundle.name,
                mime="application/zip",
                key=f"download-bundle-{bundle.name}",
                use_container_width=True,
            )
