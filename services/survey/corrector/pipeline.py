# services/survey/corrector/pipeline.py
from __future__ import annotations
from importlib import import_module
from pathlib import Path
from typing import List, Dict

from models.survey import Survey

_STAGE_DIR = Path(__file__).with_suffix('').parent / "stages"
_STAGE_ORDER = sorted(p.stem for p in _stage_dir.glob("*.py") if p.stem[0].isdigit())

def _load_stage(name: str):
    return import_module(f"services.survey.corrector.stages.{name}")

def correct_surveys(
    surveys_data: List[dict],
    context: Dict[str, object] | None = None,
) -> List[dict]:
    """Apply all correction stages in order and return *new* survey dicts."""
    context = context or {}
    surveys = [Survey(d) if isinstance(d, dict) else d for d in surveys_data]

    for stage_name in _STAGE_ORDER:
        surveys = _load_stage(stage_name).apply(surveys, context)

    return [s.to_dict() for s in surveys]