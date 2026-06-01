"""Unit tests for the CivicSearch topic-decoder FETCH extractor."""
from __future__ import annotations

import pytest

from scrapers.civicsearch.topics import (
    _bundle_url,
    _extract_topics_array,
    extract_topics,
)

# A minified-bundle fragment in the same shape as the real main.js: the topic
# array is the only `[{…}]` whose objects carry `keyword_stats`, with bare
# (unquoted) object keys in arbitrary order, embedded in surrounding code.
_FAKE_BUNDLE = (
    'var x=1;const hn=[{id:-1,keyword_stats:["seats","podium"],'
    'name:"Local governance",query_id:"local-governance"},'
    '{id:66,keyword_stats:["Police","officers"],name:"Police matters",'
    'query_id:"police-matters"},'
    '{id:36,name:"Contract negotiations",query_id:"contract-negotiations",'
    'keyword_stats:["contract","agreement"]}];function f(){return hn}'
)


def test_bundle_url_derives_from_api_base():
    assert _bundle_url("cities") == "https://www.civicsearch.org/main.js"
    assert _bundle_url("schools") == "https://schools.civicsearch.org/main.js"


def test_extract_topics_array_slices_only_the_array():
    arr = _extract_topics_array(_FAKE_BUNDLE)
    assert arr.startswith("[{") and arr.endswith("}]")
    # surrounding code is excluded
    assert "function f()" not in arr
    assert "var x=1" not in arr


def test_extract_topics_normalizes_and_sorts():
    topics = extract_topics(_FAKE_BUNDLE)
    assert [t["id"] for t in topics] == [-1, 36, 66]  # sorted, -1 kept
    by_id = {t["id"]: t for t in topics}
    assert by_id[66]["name"] == "Police matters"
    assert by_id[66]["query_id"] == "police-matters"
    assert by_id[36]["keyword_stats"] == ["contract", "agreement"]
    # every entry carries the four normalized keys
    for t in topics:
        assert set(t) == {"id", "name", "query_id", "keyword_stats"}
        assert isinstance(t["id"], int)


def test_extract_topics_raises_without_marker():
    with pytest.raises(ValueError):
        extract_topics("var nothing=here;function g(){}")
