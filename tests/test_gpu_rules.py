"""GPU runs go to the owner's Colab only, and a paid run needs the owner's yes (#357)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agents_md_states_the_gpu_rules():
    agents = (ROOT / "AGENTS.md").read_text()
    assert "## GPU and paid compute" in agents
    section = agents.split("## GPU and paid compute", 1)[1].split("\n## ", 1)[0]
    assert "owner's Colab" in section and "never the Kaggle account" in section
    assert "owner's explicit yes" in section
    assert "before and after" in section
    assert "gpu-compute-decisions" in section
    assert (ROOT / "web_docs" / "docs" / "development" / "gpu-compute-decisions.md").exists()
