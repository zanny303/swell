import json
import decision_ledger


def test_decision_location_is_persisted_and_hash_verified(tmp_path):
    site_dir=tmp_path/"site"/"data"
    site_dir.mkdir(parents=True)
    (site_dir/"site.json").write_text(json.dumps({"name":"Real test site","source":"NASA NISAR GUNW","pass_days":[0,12]}))
    record=decision_ledger.append({
        "actor":"Test team","role":"Engineer","status":"proposed",
        "decision":"Inspect north zone","rationale":"Review selected cell and field evidence.",
        "evidence_ids":["SITE-METADATA","CELL-2-3-1"],
        "location":{"lat":32.8,"lon":-96.8,"row":2,"col":3,"zone":"north"}
    },tmp_path)
    assert record["location"]["lat"]==32.8
    listed=decision_ledger.list_records(tmp_path)
    assert listed[0]["location"]["zone"]=="north"
    assert decision_ledger.verify(tmp_path)["valid"] is True


def test_decision_ledger_keeps_synthetic_flag(tmp_path):
    site_dir=tmp_path/"site"/"data"
    site_dir.mkdir(parents=True)
    (site_dir/"site.json").write_text(json.dumps({"name":"Fixture","source":"SYNTHETIC","pass_days":[0,12]}))
    record=decision_ledger.append({
        "actor":"Demo team","role":"Planner","status":"proposed",
        "decision":"Rehearse workflow","rationale":"Software demonstration only.",
        "evidence_ids":["SYNTHETIC-FIXTURE"]
    },tmp_path)
    assert record["synthetic"] is True
    assert decision_ledger.verify(tmp_path)["valid"] is True
