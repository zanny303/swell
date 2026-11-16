import json
import pathlib
import ai_provider


def test_provider_none_is_evidence_only(monkeypatch):
    for key in ("SWELL_AI_PROVIDER","SWELL_AI_API_KEY","SWELL_AI_BASE_URL","SWELL_AI_MODEL","ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert ai_provider.status()["configured"] is False
    assert ai_provider.status()["provider"] == "none"


def test_meta_provider_uses_official_openai_compatible_config(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","meta")
    monkeypatch.setenv("SWELL_AI_API_KEY","test-token-12345")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.meta.ai/v1")
    monkeypatch.setenv("SWELL_AI_MODEL","meta-test-model")
    state=ai_provider.status()
    assert state["configured"] is True
    assert state["provider"] == "meta"
    assert state["model"] == "meta-test-model"


def test_local_openai_compatible_can_run_without_key(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","compatible")
    monkeypatch.delenv("SWELL_AI_API_KEY",raising=False)
    monkeypatch.setenv("SWELL_AI_BASE_URL","http://127.0.0.1:1234/v1")
    monkeypatch.setenv("SWELL_AI_MODEL","local-model")
    assert ai_provider.status()["configured"] is True


def test_remote_plain_http_rejected():
    try:
        ai_provider._endpoint_ok("http://example.com/v1")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("remote HTTP must be rejected")


def test_openai_compatible_response_parsed(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","openai")
    monkeypatch.setenv("SWELL_AI_API_KEY","test-key-12345")
    monkeypatch.setenv("SWELL_AI_MODEL","gpt-test")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.openai.com/v1")
    calls={}
    def fake(url,payload,headers,timeout=65):
        calls["url"]=url;calls["payload"]=payload;calls["headers"]=headers
        return {"choices":[{"message":{"content":"Evidence-grounded test response."}}]}
    monkeypatch.setattr(ai_provider,"_post_json",fake)
    answer=ai_provider._generate("test",{"available":False},{},[])
    assert answer=="Evidence-grounded test response."
    assert calls["url"]=="https://api.openai.com/v1/chat/completions"
    assert calls["payload"]["max_completion_tokens"]==1100
    assert calls["headers"]["Authorization"]=="Bearer test-key-12345"


def test_synthetic_evidence_is_stripped(monkeypatch,tmp_path):
    import claude_provider, literature_rag
    monkeypatch.setattr(claude_provider,"site_evidence",lambda root,ctx:{
        "evidence_id":"SITE-METADATA","available":True,"site":"Demo","source_label":"SYNTHETIC",
        "synthetic_fixture":True,"selected_cell":{"observed_los_mm":123.4}})
    monkeypatch.setattr(literature_rag,"retrieve",lambda q,c,k=5:[{"id":"E1","title":"Paper","url":"https://example.org","text":"Clay soils swell."}])
    site,context,sources,synthetic=ai_provider._evidence("clay swelling",{"selected_cell":{"row":1,"col":2},"scenario_summary":{"baseline_mm":12}})
    assert synthetic is True
    assert "selected_cell" not in site
    assert "selected_cell" not in context
    assert "scenario_summary" not in context
    assert "observed_los_mm" not in json.dumps(site)
    assert sources[0]["id"]=="E1"


def test_provider_model_discovery_uses_models_endpoint(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","meta")
    monkeypatch.setenv("SWELL_AI_API_KEY","meta-token-12345")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.meta.ai/v1")
    monkeypatch.setenv("SWELL_AI_MODEL","")
    seen={}
    class Resp:
        def __enter__(self): return self
        def __exit__(self,*a): return False
        def read(self,n): return b'{"data":[{"id":"llama-model-a"},{"id":"llama-model-b"}]}'
    def fake_urlopen(req,timeout=25):
        seen["url"]=req.full_url
        seen["auth"]=req.headers.get("Authorization")
        return Resp()
    monkeypatch.setattr(ai_provider.urllib.request,"urlopen",fake_urlopen)
    result=ai_provider.list_models()
    assert result["models"]==["llama-model-a","llama-model-b"]
    assert seen["url"]=="https://api.meta.ai/v1/models"
    assert seen["auth"]=="Bearer meta-token-12345"


def test_ai_answer_flags_missing_research_citations(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","openai")
    monkeypatch.setenv("SWELL_AI_API_KEY","test-key-12345")
    monkeypatch.setenv("SWELL_AI_MODEL","gpt-test")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.openai.com/v1")
    monkeypatch.setattr(ai_provider,"_evidence",lambda q,c:(
        {"available":False},{"role":"planner"},
        [{"id":"E1","title":"Source","url":"https://example.org","text":"Evidence excerpt"}],False))
    monkeypatch.setattr(ai_provider,"_generate",lambda q,s,c,src:"A research statement without a citation.")
    result=ai_provider.ask("What does the research say?")
    assert "did not cite" in result["warning"]
    assert result["retrieval_method"]=="BM25 lexical RAG"


def test_provider_config_loads_saved_dotenv_after_restart(monkeypatch, tmp_path):
    import connections
    envfile=tmp_path/".env"
    envfile.write_text(
        "SWELL_AI_PROVIDER=meta\n"
        "SWELL_AI_API_KEY=meta-test-key-123456\n"
        "SWELL_AI_BASE_URL=https://api.meta.ai/v1\n"
        "SWELL_AI_MODEL=muse-spark-1.3\n"
    )
    monkeypatch.setattr(connections, "ENV", envfile)
    for key in ("SWELL_AI_PROVIDER","SWELL_AI_API_KEY","SWELL_AI_BASE_URL","SWELL_AI_MODEL"):
        monkeypatch.delenv(key, raising=False)
    assert ai_provider.status()["configured"] is True
    assert ai_provider.status()["provider"] == "meta"
    assert ai_provider.status()["model"] == "muse-spark-1.3"


def test_anthropic_request_uses_supported_messages_shape_without_temperature(monkeypatch):
    monkeypatch.setenv("SWELL_AI_PROVIDER","anthropic")
    monkeypatch.setenv("SWELL_AI_API_KEY","sk-ant-test-key-12345678901234567890")
    monkeypatch.setenv("SWELL_AI_MODEL","claude-sonnet-5")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.anthropic.com")
    captured={}
    def fake(url,payload,headers,timeout=65):
        captured.update(url=url,payload=payload,headers=headers)
        return {"content":[{"type":"text","text":"SWELL AI connection OK"}]}
    monkeypatch.setattr(ai_provider,"_post_json",fake)
    result=ai_provider.test_connection()
    assert result["ok"] is True
    assert captured["url"]=="https://api.anthropic.com/v1/messages"
    assert captured["payload"]["model"]=="claude-sonnet-5"
    assert "temperature" not in captured["payload"]
    assert captured["headers"]["anthropic-version"]=="2023-06-01"


def test_rag_returns_traceable_bm25_provenance(tmp_path):
    import literature_rag
    doc=tmp_path/"paper.txt"
    doc.write_text("Physics informed neural network for subsidence and clay moisture coupling. "*80)
    corpus=tmp_path/"corpus.json"
    corpus.write_text(json.dumps([{"title":"PINN paper","url":"https://example.org/pinn","file":"paper.txt"}]))
    rows=literature_rag.retrieve("physics informed neural network clay moisture",corpus,k=2)
    assert rows
    assert rows[0]["id"].startswith("E")
    assert rows[0]["file"]=="paper.txt"
    assert rows[0]["sha256"] and len(rows[0]["sha256"])==64
    assert rows[0]["word_offset"]==0
    assert rows[0]["score"]>0


def test_live_test_metadata_is_persisted_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("SWELL_AI_PROVIDER","meta")
    monkeypatch.setenv("SWELL_AI_API_KEY","super-secret-test-token-12345")
    monkeypatch.setenv("SWELL_AI_BASE_URL","https://api.meta.ai/v1")
    monkeypatch.setenv("SWELL_AI_MODEL","muse-spark-1.3")
    monkeypatch.setattr(ai_provider,"ROOT",tmp_path)
    (tmp_path/"out").mkdir()
    (tmp_path/"out"/"connection_status.json").write_text(json.dumps({"results":[{"id":"ai_provider","status":"not_tested"},{"id":"power","status":"ok"}]}))
    monkeypatch.setattr(ai_provider,"_post_json",lambda *a,**k:{"choices":[{"message":{"content":"SWELL AI connection OK"}}]})
    result=ai_provider.test_connection()
    assert result["ok"] is True
    report=json.loads((tmp_path/"out"/"connection_status.json").read_text())
    assert report["results"][0]["status"]=="ok"
    assert report["results"][1]["status"]=="ok"
    status=ai_provider.status()
    assert status["last_test"]["provider"]=="meta"
    saved=(tmp_path/"out"/"ai_provider_test.json").read_text()
    assert "super-secret-test-token-12345" not in saved
    assert "tested_at_utc" in saved


def test_last_test_does_not_claim_a_different_model_is_verified(monkeypatch, tmp_path):
    import connections
    envfile=tmp_path/".env"
    envfile.write_text("SWELL_AI_PROVIDER=openai\nSWELL_AI_API_KEY=test-key-12345\nSWELL_AI_BASE_URL=https://api.openai.com/v1\nSWELL_AI_MODEL=gpt-6-astra\n")
    monkeypatch.setattr(connections,"ENV",envfile)
    monkeypatch.setattr(ai_provider,"ROOT",tmp_path)
    (tmp_path/"out").mkdir()
    (tmp_path/"out"/"ai_provider_test.json").write_text(json.dumps({"ok":True,"provider":"openai","model":"old-model","tested_at_utc":"yesterday"}))
    for key in ("SWELL_AI_PROVIDER","SWELL_AI_API_KEY","SWELL_AI_BASE_URL","SWELL_AI_MODEL"):
        monkeypatch.delenv(key,raising=False)
    assert ai_provider.status()["last_test"] is None
