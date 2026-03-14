from __future__ import annotations

from src.ui.pages.home import _append_observability_summaries, _extract_cache_hit_nodes, _merge_runtime_debug_info


def test_extract_cache_hit_nodes_from_mixed_logs() -> None:
    logs = [
        "[plan_shots] cache hit key=abc123",
        "[generate_copy] cache miss key=def456",
        "[cache] node=build_prompts status=hit key=ghi789",
    ]

    result = _extract_cache_hit_nodes(logs)

    assert result == ["plan_shots", "build_prompts"]


def test_merge_runtime_debug_info_exposes_real_generation_chain() -> None:
    debug_info = {
        "image_provider_impl": "DashScopeImageProvider",
        "image_model_id": "wanx2.1-t2i-turbo",
        "render_mode": "full_auto",
    }
    state = {
        "cache_enabled": True,
        "ignore_cache": True,
        "product_analysis": {"category": "tea_gift_box"},
        "product_lock": {"category": "tea_gift_box"},
        "style_architecture": {"style_theme": "premium tea gifting"},
        "shot_plan": {"shots": []},
        "shot_prompt_specs": {"specs": []},
        "render_mode": "preview",
        "render_variant": "preview",
        "render_generation_mode": "image_edit",
        "render_reference_asset_ids": ["asset-01", "asset-02"],
        "render_image_provider_impl": "RoutedImageGenerationProvider",
        "render_image_model_id": "wan2.6-image",
    }
    logs = _append_observability_summaries(
        [
            "[analyze_product] cache hit key=cache-a",
            "[render] mode=preview variant=preview generation_mode=image_edit refs=['asset-01', 'asset-02']",
        ],
        state,
    )

    merged = _merge_runtime_debug_info(debug_info, state, logs)

    assert merged["cache_hit_nodes"] == ["analyze_product"]
    assert merged["connected_contract_files"] == [
        "product_analysis.json",
        "style_architecture.json",
        "shot_plan.json",
        "shot_prompt_specs.json",
    ]
    assert merged["style_architecture_connected"] is True
    assert merged["shot_prompt_specs_available_for_render"] is True
    assert merged["product_lock_connected"] is True
    assert merged["render_generation_mode"] == "image_edit"
    assert merged["image_model_id"] == "wan2.6-image"
    assert merged["real_generation_chain"]["reference_asset_ids"] == ["asset-01", "asset-02"]
