from scripts.gemini.part2_report_normalize import strip_one_big_thing_lines


def test_strip_one_big_thing_line():
    md = """### Headline
**The One Big Thing:** Council approved the rezoning.

* **Why it matters:** Residents get more housing.
"""
    out = strip_one_big_thing_lines(md)
    assert "One Big Thing" not in out
    assert "**Why it matters:**" in out
