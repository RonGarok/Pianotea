from __future__ import annotations

import logging

from .fluidsynth_engine import FluidSynthEngine, create_audio_engine as create_fluidsynth_engine
from .synth import SoftwareSynth


logger = logging.getLogger(__name__)


def create_audio_engine(parent=None):
    try:
        engine = create_fluidsynth_engine(parent)
        logger.info("Using FluidSynth SoundFont engine")
        return engine
    except Exception as exc:
        logger.warning("FluidSynth unavailable, using fallback synth: %s", exc)
        return SoftwareSynth(parent)


__all__ = ["FluidSynthEngine", "create_audio_engine"]
