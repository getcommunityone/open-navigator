"""Visualization module for creating advocacy heatmaps and dashboards."""

# Lazy import to avoid requiring folium unless actually generating heatmaps
__all__ = ["AdvocacyHeatmap"]

def __getattr__(name):
    """Lazy import for AdvocacyHeatmap."""
    if name == "AdvocacyHeatmap":
        from scripts.visualization.heatmap import AdvocacyHeatmap
        return AdvocacyHeatmap
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
