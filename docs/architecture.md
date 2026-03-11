# Architecture

The MVP keeps Streamlit, workflow orchestration, providers, and local storage in a single Python project. Provider calls stay inside `src/providers/`, while workflow nodes only coordinate typed inputs and outputs.

