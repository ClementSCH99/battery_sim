"""Composed SimulationSession facade."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
from battery_sim.application.session.models import (
    InvestigationRun,
)
from battery_sim.application.session.recording import RecordingMixin
from battery_sim.application.session.reasoning import ReasoningMixin
from battery_sim.application.session.persistence import PersistenceMixin

class SimulationSession(
    RecordingMixin,
    ReasoningMixin,
    PersistenceMixin,
):
    """
    Stateful investigation session.

    TEACHING: Think of this like a laboratory notebook.
    As the LLM investigates, it records what it did and what it learned.
    Later, it can flip back through the notebook to remember.

    The session enables multi-step reasoning:
    Step 1: Broad search (compare many options)
    Step 2: Analyze winner (sensitivity analysis)
    Step 3: Refine details (deep dive on best parameters)
    Step 4: Validate (check constraints, verify assumptions)

    Each step builds on the last.
    """
