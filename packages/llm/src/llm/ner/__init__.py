"""Motion/vote phrase spotting over transcript segments."""

from llm.ner.spot import VotePhraseHit, file_sha256, spot_segments

__all__ = ["VotePhraseHit", "file_sha256", "spot_segments"]