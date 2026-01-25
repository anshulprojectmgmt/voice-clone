"""
Story Narrator - AI-powered story generation and voice cloning system
"""

from .story_generator import StoryGenerator, StoryPrompt

# AudioSynthesizer and StoryNarrator require torch - make them optional
try:
    from .audio_synthesizer import AudioSynthesizer
    from .narrator import StoryNarrator
    _has_audio = True
except Exception:
    _has_audio = False

# RunPodTTSClient is optional
try:
    from .runpod_client import RunPodTTSClient
    _has_runpod = True
except Exception:
    _has_runpod = False

__all__ = [
    "StoryGenerator",
    "StoryPrompt",
]

if _has_audio:
    __all__.extend([
        "AudioSynthesizer",
        "StoryNarrator",
    ])

if _has_runpod:
    __all__.append("RunPodTTSClient")