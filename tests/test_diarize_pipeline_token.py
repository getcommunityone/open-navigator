"""WhisperX's diarization pipeline is built with whichever token argument the installed version takes (#318)."""

from types import SimpleNamespace

from llm.gemini.diarize_postprocess import align_language, make_diarization_pipeline


class NewPipeline:  # current whisperx: token=
    def __init__(self, *, token, device):
        self.token, self.device = token, device


class OldPipeline:  # whisperx before the community-1 switch: use_auth_token=
    def __init__(self, *, use_auth_token, device):
        self.token, self.device = use_auth_token, device


def test_current_whisperx_gets_token():
    p = make_diarization_pipeline(SimpleNamespace(DiarizationPipeline=NewPipeline), "hf_x", "cuda")
    assert (p.token, p.device) == ("hf_x", "cuda")


def test_older_whisperx_gets_use_auth_token():
    p = make_diarization_pipeline(SimpleNamespace(DiarizationPipeline=OldPipeline), "hf_x", "cpu")
    assert (p.token, p.device) == ("hf_x", "cpu")


def test_the_pipeline_class_can_live_in_whisperx_diarize():
    mod = SimpleNamespace(diarize=SimpleNamespace(DiarizationPipeline=NewPipeline))
    assert make_diarization_pipeline(mod, "hf_x", "cuda").token == "hf_x"


def test_the_requested_language_wins_over_whisperx_guess():
    assert align_language("en", "cy") == "en"


def test_without_a_request_the_guess_is_used_and_english_is_the_fallback():
    assert align_language(None, "es") == "es"
    assert align_language(None, None) == "en"


def _fake_whisperx(pipeline_cls):
    aligned = {"segments": [{"text": " Call to order. ", "start": 0.0, "end": 2.0}]}
    return SimpleNamespace(
        load_model=lambda *a, **k: SimpleNamespace(transcribe=lambda audio, batch_size: {"segments": [], "language": "en"}),
        load_audio=lambda path: "audio",
        load_align_model=lambda language_code, device: (None, None),
        align=lambda *a, **k: aligned,
        DiarizationPipeline=pipeline_cls,
        assign_word_speakers=lambda diarized, aligned: aligned,
    )


class RefusedPipeline:  # a gated model the token can't download
    def __init__(self, **kwargs):
        raise PermissionError("403 Forbidden")


def test_a_refused_speaker_model_keeps_the_transcript_without_speakers(tmp_path, monkeypatch):
    import sys

    from llm.gemini.diarize_postprocess import diarize_audio_whisperx
    audio = tmp_path / "m.wav"
    audio.write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "whisperx", _fake_whisperx(RefusedPipeline))
    out = diarize_audio_whisperx(audio, hf_token="hf_x", allow_no_speakers=True)
    assert [(s["text"], s["speaker"]) for s in out["segments"]] == [("Call to order.", None)]
    assert out["diarization_error"] == "PermissionError: 403 Forbidden"


def test_without_permission_a_refused_speaker_model_still_fails(tmp_path, monkeypatch):
    import sys

    import pytest
    from llm.gemini.diarize_postprocess import diarize_audio_whisperx
    audio = tmp_path / "m.wav"
    audio.write_bytes(b"x")
    monkeypatch.setitem(sys.modules, "whisperx", _fake_whisperx(RefusedPipeline))
    with pytest.raises(PermissionError):
        diarize_audio_whisperx(audio, hf_token="hf_x")
