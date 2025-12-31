#!/usr/bin/env python3
"""Quick test script to verify YT-Comprehend setup."""

import sys
from pathlib import Path

def check_dependencies():
    """Check that required dependencies are installed."""
    print("Checking dependencies...\n")
    
    required = {
        "youtube_transcript_api": "youtube-transcript-api",
        "yt_dlp": "yt-dlp",
        "faster_whisper": "faster-whisper",
        "click": "click",
        "rich": "rich",
        "yaml": "pyyaml",
    }
    
    optional = {
        "scenedetect": "scenedetect[opencv]",
        "paddleocr": "paddleocr",
        "imagededup": "imagededup",
    }
    
    missing_required = []
    missing_optional = []
    
    for module, package in required.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} [REQUIRED]")
            missing_required.append(package)
    
    print("\nOptional (Tier 3 visual analysis):")
    for module, package in optional.items():
        try:
            __import__(module)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ○ {package} [not installed]")
            missing_optional.append(package)
    
    # Check system tools
    print("\nSystem tools:")
    import subprocess
    
    for tool in ["ffmpeg", "deno"]:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
            print(f"  ✓ {tool}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"  ✗ {tool} [REQUIRED]")
            if tool not in missing_required:
                missing_required.append(tool)
    
    print()
    
    if missing_required:
        print("Missing required dependencies:")
        print(f"  pip install {' '.join(p for p in missing_required if not p.startswith('ffmpeg') and not p.startswith('deno'))}")
        if "ffmpeg" in missing_required:
            print("  sudo apt install ffmpeg")
        if "deno" in missing_required:
            print("  curl -fsSL https://deno.land/install.sh | sh")
        return False
    
    return True


def test_tier1(test_url: str = None):
    """Test Tier 1 caption extraction."""
    print("\n" + "="*50)
    print("Testing Tier 1: Caption Extraction")
    print("="*50)
    
    # Use a known video with captions for testing
    test_url = test_url or "dQw4w9WgXcQ"  # Rick Astley - known to have captions
    
    try:
        from src.extractors.captions import CaptionExtractor
        
        extractor = CaptionExtractor()
        
        # Just check if captions are available
        if extractor.is_available(test_url):
            print(f"✓ Captions available for test video")
            
            # Actually extract
            result = extractor.extract(test_url)
            preview = result.text[:200] + "..." if len(result.text) > 200 else result.text
            print(f"✓ Extracted {len(result.segments)} segments")
            print(f"✓ Language: {result.language} (auto-generated: {result.is_generated})")
            print(f"\nPreview:\n{preview}")
            return True
        else:
            print("✗ Captions not available for test video")
            return False
            
    except Exception as e:
        print(f"✗ Tier 1 test failed: {e}")
        return False


def test_tier2_init():
    """Test Tier 2 Whisper model initialization (without full transcription)."""
    print("\n" + "="*50)
    print("Testing Tier 2: Whisper Initialization")
    print("="*50)
    
    try:
        from src.extractors.audio import AudioExtractor
        
        print("Initializing AudioExtractor with 'tiny' model...")
        extractor = AudioExtractor(model_name="tiny", device="cpu", compute_type="int8")
        
        # Just check model loads
        print("Loading model (this may download ~75MB on first run)...")
        _ = extractor.model
        
        print("✓ Whisper model loaded successfully")
        return True
        
    except Exception as e:
        print(f"✗ Tier 2 initialization failed: {e}")
        return False


def main():
    print("YT-Comprehend Setup Test")
    print("="*50)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n⚠ Some dependencies are missing. Install them before continuing.")
        sys.exit(1)
    
    print("\n✓ All required dependencies installed!")
    
    # Test tiers
    tier1_ok = test_tier1()
    tier2_ok = test_tier2_init()
    
    print("\n" + "="*50)
    print("Summary")
    print("="*50)
    print(f"  Tier 1 (Captions):     {'✓ Ready' if tier1_ok else '✗ Failed'}")
    print(f"  Tier 2 (Whisper):      {'✓ Ready' if tier2_ok else '✗ Failed'}")
    print(f"  Tier 3 (Visual):       Run 'pip install -e .[visual]' to enable")
    
    if tier1_ok and tier2_ok:
        print("\n✓ Setup complete! Try:")
        print('  yt-comprehend "https://youtube.com/watch?v=VIDEO_ID"')
    else:
        print("\n⚠ Some tests failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
