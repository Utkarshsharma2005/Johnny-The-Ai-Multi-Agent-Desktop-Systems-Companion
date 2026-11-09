import tempfile
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.memory.memory_manager import (
    ShortTermMemory,
    ProjectMemory,
    LongTermMemory,
    MemoryManager,
    memory_manager
)

def test_short_term_memory_sliding_window():
    stm = ShortTermMemory(capacity=3)
    stm.add("item1", "value1", ["tag1"])
    stm.add("item2", "value2", ["tag2"])
    stm.add("item3", "value3", ["tag3"])
    assert len(stm.get_all()) == 3

    # Add 4th item -> item1 evicted
    stm.add("item4", "value4", ["tag4"])
    all_items = stm.get_all()
    assert len(all_items) == 3
    keys = [item.key for item in all_items]
    assert "item1" not in keys
    assert "item4" in keys

    # Query search
    results = stm.query("value3")
    assert len(results) == 1
    assert results[0].key == "item3"

def test_project_memory_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm1 = ProjectMemory(base_dir=tmpdir)
        pm1.add("arch", "FastAPI + Tauri v2", ["architecture"])
        pm1.add("style", "Vanilla CSS + Tailwind", ["frontend"])
        assert len(pm1.get_all()) == 2

        # Re-instantiate from disk
        pm2 = ProjectMemory(base_dir=tmpdir)
        loaded_items = pm2.get_all()
        assert len(loaded_items) == 2
        keys = [item.key for item in loaded_items]
        assert "arch" in keys
        assert "style" in keys

def test_long_term_memory_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        custom_file = f"{tmpdir}/global_test.json"
        ltm1 = LongTermMemory(custom_path=custom_file)
        ltm1.add("theme_preference", "dark mode", ["preference", "ui"])
        assert len(ltm1.get_all()) == 1

        ltm2 = LongTermMemory(custom_path=custom_file)
        assert len(ltm2.get_all()) == 1
        assert ltm2.get_all()[0].value == "dark mode"

def test_prompt_context_enrichment():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProjectMemory(base_dir=tmpdir)
        ltm = LongTermMemory(custom_path=f"{tmpdir}/ltm.json")
        stm = ShortTermMemory()

        pm.add("tech_stack", "Python 3.14 + Vite React")
        ltm.add("user_name", "Anshu")

        mgr = MemoryManager(short_term=stm, project=pm, long_term=ltm)
        prompt = "How should I build the next feature?"
        enriched = mgr.enrich_prompt_context(prompt)

        assert "[Project Context Memory]" in enriched
        assert "[User Long-Term Preferences]" in enriched
        assert "Python 3.14 + Vite React" in enriched
        assert "Anshu" in enriched

@pytest.mark.asyncio
async def test_memory_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Record short_term memory
        res_rec = await ac.post("/api/v1/memory/record", json={
            "tier": "short_term",
            "key": "active_tool",
            "value": "git_status",
            "tags": ["git", "tool"]
        })
        assert res_rec.status_code == 200
        rec_data = res_rec.json()
        assert rec_data["key"] == "active_tool"
        assert rec_data["tier"] == "short_term"

        # 2. Query memory
        res_query = await ac.get("/api/v1/memory/query?term=git_status&tier=short_term")
        assert res_query.status_code == 200
        items = res_query.json()
        assert len(items) >= 1
        assert items[0]["key"] == "active_tool"

        # 3. Clear short_term memory
        res_clear = await ac.delete("/api/v1/memory/clear/short_term")
        assert res_clear.status_code == 200
        assert "Cleared memory tier" in res_clear.json()["message"]

def test_memory_optimization_and_truncation():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProjectMemory(base_dir=tmpdir)
        pm.max_capacity = 3

        # Test value truncation for long payloads
        long_payload = "A" * 3000
        item = pm.add("large_log", long_payload)
        assert len(item.value) < 1500
        assert "[truncated for memory efficiency]" in item.value

        # Test strict capacity enforcement (capacity = 3)
        pm.add("k1", "v1")
        pm.add("k2", "v2")
        pm.add("k3", "v3")
        assert len(pm.get_all()) == 3

