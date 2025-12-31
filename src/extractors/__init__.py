"""Video content extractors for each tier."""

from .captions import CaptionExtractor
from .audio import AudioExtractor

__all__ = ["CaptionExtractor", "AudioExtractor"]

# Tier 3 imports (optional, may not be installed)
try:
    from .visual import VisualExtractor
    __all__.append("VisualExtractor")
except ImportError:
    VisualExtractor = None
