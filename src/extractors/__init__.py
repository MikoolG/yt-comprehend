"""Video content extractors for each tier."""

from .audio import AudioExtractor
from .captions import CaptionExtractor

__all__ = ["CaptionExtractor", "AudioExtractor"]

# Tier 3 imports (optional, may not be installed)
try:
    from .visual import VisualExtractor
    __all__.append("VisualExtractor")
except ImportError:
    VisualExtractor = None
