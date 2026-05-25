from __future__ import annotations


def test_reexports_available() -> None:
    from docsfy.ai_client import (
        AIResult,
        call_ai_once,
        check_sidecar_available,
        list_models,
        run_parallel_with_limit,
    )

    assert callable(call_ai_once)
    assert callable(check_sidecar_available)
    assert callable(list_models)
    assert callable(run_parallel_with_limit)
    # AIResult is a dataclass
    assert "success" in AIResult.__dataclass_fields__
    assert "text" in AIResult.__dataclass_fields__
