"""Streamlit 程序入口。

当前项目只有一个 UI 入口文件：`streamlit_app.py`。
开发者通过：

`python -m streamlit run streamlit_app.py`

启动应用后，Streamlit 会执行这里的 `main()`，再进入
`src.ui.pages.home.render_home_page()`，由页面层收集用户输入并触发 workflow。
"""

from __future__ import annotations

from src.ui.pages.home import render_home_page


def main() -> None:
    """启动首页渲染。

    这里本身不承载业务逻辑，只作为 Streamlit 到 UI 页面层的最外层入口。
    """
    render_home_page()


if __name__ == "__main__":
    main()

