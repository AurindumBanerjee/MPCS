import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tempfile

from hkg.config import (
    get_modality_seed,
    get_remedy_abbreviations,
    get_sections_config,
    get_sources_config,
    settings,
)
from hkg.schema.graph import (
    make_chunk_id,
    make_modality_id,
    make_occurrence_id,
    make_region_id,
    make_remedy_id,
    make_sensation_id,
    make_slug,
    make_source_id,
    make_symptom_id,
)
from hkg.schema.extraction import ChunkExtraction, ModalityOut, SymptomOut
from hkg.llm.cache import DiskLLMCache
from hkg.llm.ratelimit import TokenBucketRateLimiter
from hkg.llm.mock_client import MockLLMClient


def test_configs_load():
    sources = get_sources_config()
    assert "boericke_pocket_manual" in sources
    assert sources["boericke_pocket_manual"]["license"] == "public_domain"

    abbrs = get_remedy_abbreviations()
    assert abbrs["Ars."] == "Arsenicum album"
    assert abbrs["Puls."] == "Pulsatilla pratensis"

    sections = get_sections_config()
    assert "Mind" in sections
    assert sections["Mind"]["kind"] == "mental"
    assert "Stomach" in sections
    assert sections["Stomach"]["kind"] == "physical"

    modalities = get_modality_seed()
    assert len(modalities) > 0
    assert any(m["label"] == "after midnight" for m in modalities)


def test_id_generation_is_deterministic():
    slug = make_slug("Arsenicum Album (White Oxide)")
    assert slug == "arsenicum_album_white_oxide"

    rem_id = make_remedy_id("Arsenicum album")
    assert rem_id == "remedy:arsenicum_album"

    sym_id = make_symptom_id("Fear of death")
    assert sym_id == "symptom:fear_of_death"

    mod_id = make_modality_id("after midnight")
    assert mod_id == "modality:after_midnight"

    reg_id = make_region_id("Stomach")
    assert reg_id == "region:stomach"

    sens_id = make_sensation_id("burning")
    assert sens_id == "sensation:burning"

    src_id = make_source_id("boericke")
    assert src_id == "source:boericke"

    chunk_id = make_chunk_id(src_id, 42)
    assert chunk_id == "chunk:boericke:42"

    occ1 = make_occurrence_id(chunk_id, "Burning in stomach", "Intense burning in stomach after cold drinks.")
    occ2 = make_occurrence_id(chunk_id, "Burning in stomach", "Intense burning in stomach after cold drinks.")
    assert occ1 == occ2
    assert occ1.startswith("occ:")
    assert len(occ1) == 20  # "occ:" (4) + 16 chars hex


def test_extraction_schema_valid():
    sym = SymptomOut(
        symptom_raw="Fear of death",
        evidence_quote="Great fear of death, with extreme restlessness.",
        emphasis="bold",
        modalities=[
            ModalityOut(direction="worse", factor_raw="after midnight", factor_type="time")
        ],
        confidence=0.98,
    )
    assert sym.emphasis == "bold"
    assert len(sym.modalities) == 1
    assert sym.modalities[0].direction == "worse"

    extraction = ChunkExtraction(symptoms=[sym])
    data = extraction.model_dump()
    assert len(data["symptoms"]) == 1


def test_disk_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = DiskLLMCache(cache_dir=Path(tmpdir))
        key = cache.make_cache_key("test-model", "v1", "v1", "sample chunk")
        assert cache.get(key) is None

        cache.set(key, {"test": 123})
        cached = cache.get(key)
        assert cached == {"test": 123}
        assert cache.count() == 1


def test_mock_client():
    mock = MockLLMClient()
    health = mock.health_check()
    assert health["status"] == "ok"

    chunk = "**Great anguish and restlessness.**\nFear of death < after midnight."
    result = mock.extract(chunk, "Arsenicum album", "Mind")
    assert len(result.symptoms) >= 1
    assert any("death" in s.symptom_raw.lower() for s in result.symptoms)
