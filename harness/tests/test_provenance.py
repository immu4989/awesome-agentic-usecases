

def test_a_redirected_model_is_not_pinned():
    """`deepseek-chat` looks pinned and serves `deepseek-v4-flash`.

    No marker in the requested name reveals this. The mismatch is the only evidence, so it
    has to be what drives the flag, otherwise a result gets filed as reproducible when the
    provider is free to move the weights under the same name.
    """
    from aau_harness import provenance

    class _B:
        model = "deepseek-chat"
        served_model = "deepseek-v4-flash"

    provenance.register_backend(_B())
    snap = provenance.snapshot()
    assert snap["served_differs_from_requested"] is True
    assert snap["model_pinned"] is False
    assert "alias" in snap["reproducibility_note"]
