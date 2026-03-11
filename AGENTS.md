# AGENTS.md

## Goal
Build a local Streamlit-based e-commerce image generation tool for tea product image sets.

## Current scope
- Python 3.11 only
- Streamlit single-app delivery
- LangGraph workflow skeleton first
- Local file storage only
- Chinese copy is always rendered by Pillow after image generation

## Project rules
- Keep provider code inside `src/providers/`
- Keep orchestration inside `src/workflows/`
- Keep UI code inside `src/ui/`
- Persist every task under `outputs/tasks/{task_id}/`
- Use typed Pydantic schemas between workflow steps
- Favor runnable MVP over deeper abstraction

## MVP output
- Upload multiple source images
- Collect brand name, product name, platform, size, shot count, tone
- Create task id and persist inputs
- Run a LangGraph pipeline with mock-safe providers
- Generate placeholder images with structured overlay text
- Preview and download single images or a zip package

## Delivery notes
- Add actionable TODO comments where real model integration is still pending
- Keep files small and typed
- Avoid adding database, auth, or separate frontend layers

