import copy
import json
from pathlib import Path

import pytest

from aau_incident_exchange import (
    ExchangeError,
    build_pack,
    csaf_bridge,
    load_json,
    ocsf_bridge,
    openvex_export,
    sarif_export,
    verify_artifact_bindings,
    verify_pack,
)


ROOT = Path(__file__).resolve().parents[2]
EXCHANGE = ROOT / "agent-incident-exchange" / "examples" / "reference-exchange.json"


def test_reference_exchange_binds_three_public_regressions():
    exchange = load_json(EXCHANGE)
    verify_artifact_bindings(exchange, ROOT)
    assert len(exchange["entries"]) == 3
    assert all(entry["regression"]["clean_twin_present"] for entry in exchange["entries"])


def test_all_interoperability_views_preserve_explicit_boundaries():
    exchange = load_json(EXCHANGE)
    sarif = sarif_export(exchange)
    openvex = openvex_export(exchange)
    csaf = csaf_bridge(exchange)
    ocsf = ocsf_bridge(exchange)
    assert sarif["version"] == "2.1.0"
    assert len(openvex["statements"]) == 3
    assert csaf["x_aau_bridge"]["validated_against_csaf_schema"] is False
    assert ocsf["validated_against_ocsf_schema"] is False
    serialized = json.dumps([sarif, openvex, csaf, ocsf])
    assert "not a production vulnerability determination" in serialized.lower()


def test_complete_exchange_pack_recomputes_and_rejects_tampering(tmp_path):
    exchange = load_json(EXCHANGE)
    pack = tmp_path / "pack"
    build_pack(exchange, ROOT, pack)
    assert verify_pack(pack, ROOT)["exchange_id"] == exchange["exchange_id"]
    (pack / "findings.sarif.json").write_text("{}")
    with pytest.raises(ExchangeError, match="integrity mismatch"):
        verify_pack(pack, ROOT)


def test_regression_digest_drift_fails_closed():
    exchange = copy.deepcopy(load_json(EXCHANGE))
    exchange["entries"][0]["regression"]["artifact_sha256"] = "0" * 64
    unsigned = {key: value for key, value in exchange.items() if key != "exchange_sha256"}
    from aau_incident_exchange import digest

    exchange["exchange_sha256"] = digest(unsigned)
    with pytest.raises(ExchangeError, match="digest drift"):
        verify_artifact_bindings(exchange, ROOT)


def test_nonpublic_disclosure_is_rejected():
    exchange = copy.deepcopy(load_json(EXCHANGE))
    exchange["entries"][0]["disclosure"]["credentials_excluded"] = False
    unsigned = {key: value for key, value in exchange.items() if key != "exchange_sha256"}
    from aau_incident_exchange import digest

    exchange["exchange_sha256"] = digest(unsigned)
    with pytest.raises(ExchangeError, match="public defensive boundary"):
        verify_artifact_bindings(exchange, ROOT)
