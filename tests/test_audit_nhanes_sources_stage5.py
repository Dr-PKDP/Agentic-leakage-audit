from src.audit_nhanes_sources_stage5 import build_registry

def test_registry_covers_all_required_sources():
    names = {item["filename"] for item in build_registry()}
    assert len(names) == 34
    assert "RXQ_DRUG.XPT" in names
    assert "FASTQX_G.XPT" in names
    assert "FASTQX_H.XPT" in names
    assert "FASTQX_I.XPT" in names
    for suffix in "GHI":
        assert f"DEMO_{suffix}.XPT" in names
        assert f"MCQ_{suffix}.XPT" in names
        assert f"DPQ_{suffix}.XPT" in names
