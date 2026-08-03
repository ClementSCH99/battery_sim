"""Focused persistence behavior."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from battery_sim.application.session.models import (
    InvestigationRun,
)

class PersistenceMixin:
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize session to JSON for saving.

        TEACHING: We can save the entire investigation to a file,
        then reload it later. This enables:
        1. Reproducibility ("run the same investigation again")
        2. Auditing (engineer can review what was tested)
        3. Learning (understand how the LLM reasoned)
        """

        return {
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'investigations': [run.to_dict() for run in self.investigation_history],
            'conclusions': self.conclusions,
            'strategy': self.identify_investigation_pattern(),
            'total_time_s': self.total_simulation_time(),
        }
    def to_json_string(self) -> str:
        """Pretty-print session as JSON."""
        return json.dumps(self.to_dict(), indent=2)
    def save_to_file(self, filepath: str) -> None:
        """
        Save session to a JSON file.

        TEACHING: Persistence enables reproducibility and auditing.
        """
        with open(filepath, 'w') as f:
            f.write(self.to_json_string())
        print(f"Session saved to {filepath}")
    @staticmethod
    def load_from_file(filepath: str) -> "SimulationSession":
        """Load session from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)

        session = SimulationSession(name=data.get('name', 'Loaded Session'))
        session.created_at = datetime.fromisoformat(data.get('created_at'))
        session.conclusions = data.get('conclusions', {})

        # Note: Reconstructing full InvestigationRun objects would require
        # more info. For now, this is a partial reconstruction.

        return session
