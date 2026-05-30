"""communityone-hosting: publishing/deployment tooling for Open Navigator.

Currently provides the :mod:`hosting.huggingface` subpackage for publishing
gold datasets to HuggingFace Datasets and deploying the app to HuggingFace
Spaces. The package is host-agnostic by design so additional hosts can be
added alongside ``huggingface`` later.
"""

__all__ = ["huggingface"]
