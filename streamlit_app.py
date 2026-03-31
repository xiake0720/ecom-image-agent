"""历史 Streamlit 入口（已降级为调试脚本）。

为什么保留：
- 兼容旧的本地演示方式，便于回归比对；
- 但正式入口已迁移为 `backend/main.py` + `frontend/`。
"""

from __future__ import annotations

import streamlit as st


def main() -> None:
    """显示迁移提示，避免误用旧入口。"""

    st.set_page_config(page_title="ecom-image-agent（迁移提示）", layout="centered")
    st.title("该项目已迁移为 FastAPI + React")
    st.info("请使用 `uvicorn backend.main:app --reload` 启动后端，并在 frontend 目录启动 React 前端。")


if __name__ == "__main__":
    main()
