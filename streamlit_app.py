"""Streamlit 程序入口。

当前项目只有一个 UI 入口文件：`streamlit_app.py`。
开发者通过：

`python -m streamlit run streamlit_app.py`

启动应用后，Streamlit 会执行这里的 `main()`，再进入
`src.ui.pages.home.render_home_page()`，由页面层收集用户输入并触发 workflow。
"""

from __future__ import annotations

import logging

from src.core.config import get_settings
from src.core.logging import initialize_logging, log_application_startup
from src.ui.pages.home import render_home_page

logger = logging.getLogger(__name__)


def main() -> None:
    """启动首页渲染。

    这里本身不承载业务逻辑，只作为 Streamlit 到 UI 页面层的最外层入口。
    """
    settings = get_settings()
    initialize_logging(settings)
    log_application_startup(settings)
    logger.info("开始渲染 Streamlit 首页")
    render_home_page()


if __name__ == "__main__":
    main()

