"""fec_integration: both HTTP calls pass a timeout, so a stalled FEC server fails instead of hanging (#465).

`requests` has no default timeout. The API client's every request and the multi-GB bulk download passed none, so a
server that stopped answering hung the load forever. Every test here mocks the HTTP layer and points the bulk loader's
cache at a temp folder, so nothing is fetched and nothing under data/cache/ is read or written.
"""

from __future__ import annotations

from unittest import mock

from scrapers.fec import fec_integration as fec


def test_api_requests_pass_the_api_timeout(monkeypatch):
    api = fec.OpenFECAPI(api_key="test-key")
    response = mock.Mock()
    response.json.return_value = {"results": []}
    monkeypatch.setattr(api.session, "get", mock.Mock(return_value=response))
    monkeypatch.setattr(fec.time, "sleep", lambda s: None)
    assert api._make_request("candidates", {"q": "x"}) == {"results": []}
    assert api.session.get.call_args.kwargs["timeout"] == fec.FEC_API_TIMEOUT


def test_bulk_download_passes_the_bulk_timeout(monkeypatch, tmp_path):
    loader = fec.FECBulkDataLoader(cache_dir=tmp_path)
    response = mock.Mock(headers={"content-length": "3"})
    response.iter_content.return_value = [b"abc"]
    get = mock.Mock(return_value=response)
    monkeypatch.setattr(fec.requests, "get", get)
    path = loader.download_individual_contributions("2024")
    assert path.read_bytes() == b"abc"
    assert get.call_args.kwargs["timeout"] == fec.FEC_BULK_TIMEOUT
    assert get.call_args.kwargs["stream"] is True


def test_timeouts_are_connect_and_read_pairs():
    for t in (fec.FEC_API_TIMEOUT, fec.FEC_BULK_TIMEOUT):
        assert isinstance(t, tuple) and len(t) == 2 and all(v > 0 for v in t)
    assert fec.FEC_BULK_TIMEOUT[1] > fec.FEC_API_TIMEOUT[1]   # a slow chunk of a GB file needs longer than an API reply
