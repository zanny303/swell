import json
import connections


def test_nisar_zero_granules_is_no_data_not_key_failure(monkeypatch):
    monkeypatch.setattr(connections, "_get", lambda url, **kwargs: (b"{}", {"CMR-Hits":"0"}))
    try:
        connections.c_nisar(32.8,-96.8)
    except connections.NoDataError as exc:
        assert "no NISAR GUNW granules" in str(exc)
    else:
        raise AssertionError("zero NISAR granules must be reported as no data")


def test_connection_report_is_persisted_without_secret_values(monkeypatch,tmp_path):
    monkeypatch.setattr(connections,"ROOT",tmp_path)
    monkeypatch.setattr(connections,"ENV",tmp_path/".env")
    monkeypatch.setattr(connections,"CHECKS",[
        ("source","Public source","core","test source",lambda lat,lon:"service answered"),
        ("earthdata","Earthdata","account","test login",lambda lat,lon:"login accepted"),
    ])
    (tmp_path/".env").write_text("EARTHDATA_PASSWORD=do-not-store-this-secret\n")
    result=connections.run(32.8,-96.8)
    path=tmp_path/"out"/"connection_status.json"
    assert path.exists()
    saved=path.read_text()
    assert "do-not-store-this-secret" not in saved
    assert result["ready_for_real_twin"] is True
    assert "does NOT mean a study is loaded" in result["next_step"]


def test_ai_settings_change_invalidates_previous_green_provider_check(monkeypatch, tmp_path):
    monkeypatch.setattr(connections,"ROOT",tmp_path)
    monkeypatch.setattr(connections,"ENV",tmp_path/".env")
    for key in ("SWELL_AI_PROVIDER","SWELL_AI_API_KEY","SWELL_AI_BASE_URL","SWELL_AI_MODEL"):
        monkeypatch.delenv(key,raising=False)
    out=tmp_path/"out";out.mkdir()
    (out/"connection_status.json").write_text(json.dumps({"results":[
        {"id":"ai_provider","status":"ok","detail":"old provider passed"},
        {"id":"power","status":"ok","detail":"public source"}
    ]}))
    (out/"ai_provider_test.json").write_text(json.dumps({"ok":True,"provider":"openai","model":"old-model"}))
    connections.save_keys({
        "SWELL_AI_PROVIDER":"meta",
        "SWELL_AI_API_KEY":"meta-key-123456789",
        "SWELL_AI_BASE_URL":"https://api.meta.ai/v1",
        "SWELL_AI_MODEL":"muse-spark-1.3",
    })
    report=json.loads((out/"connection_status.json").read_text())
    assert report["results"][0]["status"]=="not_tested"
    assert report["results"][1]["status"]=="ok"
    assert "Test AI generation" in report["results"][0]["detail"]
    assert not (out/"ai_provider_test.json").exists()
