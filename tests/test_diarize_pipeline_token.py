"""WhisperX's diarization pipeline is built with whichever token argument the installed version takes (#318)."""

from types import SimpleNamespace

from llm.gemini.diarize_postprocess import make_diarization_pipeline


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
