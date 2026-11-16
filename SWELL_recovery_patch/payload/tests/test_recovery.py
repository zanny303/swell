import ai_provider

def test_meta_reasoning_retry(monkeypatch):
    for k,v in {'SWELL_AI_PROVIDER':'meta','SWELL_AI_API_KEY':'test-key','SWELL_AI_BASE_URL':'https://api.meta.ai/v1','SWELL_AI_MODEL':'muse-spark-1.3'}.items():monkeypatch.setenv(k,v)
    calls=[]
    def post(url,payload,headers,timeout=65):
        calls.append(dict(payload));return {'choices':[{'finish_reason':'length','message':{'content':None,'reasoning_content':'private'}}]} if len(calls)==1 else {'choices':[{'finish_reason':'stop','message':{'content':'Visible evidence answer'}}]}
    monkeypatch.setattr(ai_provider,'_post_json',post)
    assert ai_provider._generate('q',{}, {},[])=='Visible evidence answer'
    assert calls[0]['reasoning_effort']=='low' and calls[0]['max_completion_tokens']==4096
    assert calls[1]['max_completion_tokens']==8192 and 'temperature' not in calls[0]

def test_meta_empty_stop_has_actionable_error(monkeypatch):
    for k,v in {'SWELL_AI_PROVIDER':'meta','SWELL_AI_API_KEY':'test-key','SWELL_AI_BASE_URL':'https://api.meta.ai/v1','SWELL_AI_MODEL':'muse-spark-1.3'}.items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(ai_provider,'_post_json',lambda *a,**k:{'choices':[{'finish_reason':'stop','message':{'content':None,'reasoning_content':'private'}}]})
    import pytest
    with pytest.raises(RuntimeError,match='finish_reason=stop'):ai_provider._generate('q',{}, {},[])

def test_world_mosaic_allowlist(tmp_path):
    import world_mosaics, pytest
    with pytest.raises(ValueError):world_mosaics.mosaic('../invalid',tmp_path)
