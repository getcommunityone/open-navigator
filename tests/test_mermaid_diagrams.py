from scripts.gemini.mermaid_diagrams import (
    repair_mermaid_fences_in_markdown,
    sanitize_mindmap_mermaid,
    sanitize_timeline_mermaid,
)


def test_timeline_dedupes_duplicate_period_labels():
    raw = """timeline
    section Lifecycle
        Next : First event
        Next : Second event"""
    out = sanitize_timeline_mermaid(raw)
    assert "Next : First" in out
    assert "Next 2 : Second" in out


def test_mindmap_root_flattens_inner_parentheses():
    raw = """mindmap
  root((Old Jail Property (202803 Gary Fit Street)))
    Child"""
    out = sanitize_mindmap_mermaid(raw)
    assert "root((Old Jail Property - 202803 Gary Fit Street))" in out
    assert "(202803" not in out.split("root((")[1].split("))")[0]


def test_mindmap_nests_arguments_and_proposal_children():
    raw = """mindmap
root((Rezoning 2842 18th St))
    Proposal
    Duplex construction
    MR1 to SFR5
    Arguments For
    Affordable housing
    Redevelopment
    Arguments Against
    Front yard parking concerns
    Outcome
    Recommended for Approval (7-0)"""
    out = sanitize_mindmap_mermaid(raw)
    lines = out.splitlines()
    assert "    Proposal" in out
    assert "      Duplex construction" in out
    assert "    Arguments For" in out
    assert "      Affordable housing" in out
    assert "    Arguments Against" in out
    assert "      Front yard parking concerns" in out
    assert "    Outcome" in out
    assert "      Recommended for Approval - 7-0" in out
    assert "(" not in out.split("Outcome", 1)[-1]
    # Proposal line must appear before its children
    prop_i = lines.index("    Proposal")
    duplex_i = lines.index("      Duplex construction")
    args_i = lines.index("    Arguments For")
    assert prop_i < duplex_i < args_i


def test_mindmap_nests_problem_solution_funding_timeline():
    raw = """mindmap
  root((Julia Tutwiler Access Road Project))
    Problem
    Initial ALDOT plan isolates school
    Circuitous routes for emergency services
    Solution
    Exit off McFarland
    Roundabout at Julia Tutwiler terminus
    Funding
    Total Cost - $2.5 million
    ATRIP Grant - $2 million
    Timeline
    Construction Start - May 2027"""
    out = sanitize_mindmap_mermaid(raw)
    assert "    Problem\n      Initial ALDOT" in out or (
        "    Problem" in out and "      Initial ALDOT plan isolates school" in out
    )
    assert "    Solution\n      Exit off McFarland" in out or (
        "    Solution" in out and "      Exit off McFarland" in out
    )
    assert "    Funding" in out and "      Total Cost" in out
    assert "    Timeline" in out and "      Construction Start" in out


def test_mindmap_strips_parentheses_in_body_nodes():
    """Regression: ``Contractor (Rollo Consultants)`` caused SPACELIST parse errors."""
    raw = """mindmap
  root((Remson Cemetery Crowns Maintenance Revocation))
    Problem
      Contractor (Rollo Consultants) performed unsatisfactorily
      Only ~50% of work completed"""
    out = sanitize_mindmap_mermaid(raw)
    assert "Contractor - Rollo Consultants" in out
    assert "(Rollo" not in out


def test_repair_fences_in_markdown():
    md = """#### Timeline
```mermaid
mindmap
  root((Topic (detail)))
```
"""
    fixed = repair_mermaid_fences_in_markdown(md)
    assert "Topic - detail" in fixed
