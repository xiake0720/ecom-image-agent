"""Streamlit 应用入口。

文件位置：
- 仓库根目录 `streamlit_app.py`

核心职责：
- 作为整个项目唯一的 UI 启动入口
- 初始化配置与日志
- 将页面控制权交给 `src.ui.pages.home.render_home_page()`

主要调用方：
- `python -m streamlit run streamlit_app.py`

主要依赖：
- `src.core.config` 读取运行配置
- `src.core.logging` 初始化日志
- `src.ui.pages.home` 渲染首页并触发 workflow

关键输入/输出：
- 输入是 Streamlit 当前会话状态
- 输出是页面渲染副作用，不直接返回业务对象
"""

from __future__ import annotations

import logging

import streamlit as st

from src.core.config import get_settings
from src.core.logging import initialize_logging, log_application_startup
from src.ui.pages.home import render_home_page
from src.workflows.graph import reload_runtime

logger = logging.getLogger(__name__)


def main() -> None:
    """启动首页渲染。

    调用链位置：
    - 由 Streamlit 直接执行
    - 入口极薄，不承载业务逻辑

    关键副作用：
    - 根据页面标记决定是否重载 runtime
    - 初始化日志
    - 渲染首页
    """
    if st.session_state.pop("_ecom_reload_runtime", False):
        reload_runtime()
    settings = get_settings()
    initialize_logging(settings)
    log_application_startup(settings)
    logger.info("开始渲染 Streamlit 首页")
    render_home_page()


if __name__ == "__main__":
    main()
