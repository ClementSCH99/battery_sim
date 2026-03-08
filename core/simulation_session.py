"""
LAYER 4: SESSION MANAGEMENT - Investigation Memory

TEACHING FOCUS: Stateful reasoning

WHY THIS LAYER EXISTS:
When an LLM investigates a problem, it doesn't start fresh each time.
It builds on previous learnings:

"I compared presets and found NMC is the best balance.
Now let me analyze its sensitivity to temperature."

This requires the API to REMEMBER what happened before.
That's what SimulationSession does.

DESIGN PRINCIPLE: Sessions are first-class objects.
The LLM can:
1. Start a new session
2. Run investigations
3. Query what it learned
4. Trace the reasoning path

This enables reasoning chains that humans can audit.

---

EXAMPLE: Session-based reasoning

session = SimulationSession("BMS calibration investigation")

# Investigation 1: Chemistry comparison
run1 = session.run_investigation(
    'compare_presets',
    preset_names=['LFP_5AH', 'NMC_5AH', 'NCA_5AH']
)
# → "NMC wins on balance: 18W power, 94% efficiency"

# Investigation 2: NMC sensitivity analysis  
run2 = session.run_investigation(
    'sensitivity_analysis',
    preset='NMC_5AH',
    parameters=['temperature_C', 'nominal_capacity_Ah']
)
# → "Temperature is HIGH sensitivity (45%), capacity is LOW (8%)"

# Investigation 3: Temperature deep-dive
run3 = session.run_investigation(
    'batch_simulate',
    preset='NMC_5AH',
    environments=[
        Environment(temperature_C=0),
        Environment(temperature_C=25),
        Environment(temperature_C=50),
    ]
)

# Later: What did we learn?
session.summarize_reasoning()
# → Shows the path: Chemistry comparison → Winner sensitivity → Refine best parameters

The session remembers EVERYTHING. The LLM can reason about it.
We can also audit the LLM's reasoning: "Here's exactly what you tested."
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json


# ============================================================================
# INVESTIGATION RUN: One investigation in a session
# ============================================================================

@dataclass
class InvestigationRun:
    """
    A single investigation within a session.
    
    TEACHING: An "investigation run" is one thing the LLM tried.
    It records:
    - What question was asked (investigation_type)
    - What parameters it used
    - What it learned (result_summary)
    - When it happened (timestamp)
    
    The collection of InvestigationRun objects forms the session history.
    """
    
    investigation_type: str  # 'compare_presets', 'sensitivity_analysis', etc.
    timestamp: datetime
    parameters: Dict[str, Any]  # What was tested?
    result_summary: Dict[str, Any]  # What was learned?
    result_markdown: str  # Human-readable format
    duration_seconds: float  # How long did it take?
    
    # Optional: insights that the investigation revealed
    key_findings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """JSON serialization for logging."""
        return {
            'type': self.investigation_type,
            'timestamp': self.timestamp.isoformat(),
            'parameters': self.parameters,
            'summary': self.result_summary,
            'duration_s': self.duration_seconds,
            'findings': self.key_findings,
        }


# ============================================================================
# SIMULATION SESSION: Stateful investigation framework
# ============================================================================

class SimulationSession:
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
    
    def __init__(self, name: str = "Investigation Session"):
        """
        Initialize a new investigation session.
        
        Args:
            name: Human-readable name for this investigation
        """
        self.name = name
        self.created_at = datetime.now()
        self.investigation_history: List[InvestigationRun] = []
        
        # Track "conclusions" - what the LLM has learned
        self.conclusions: Dict[str, Any] = {}
    
    def record_investigation(
        self,
        investigation_type: str,
        parameters: Dict[str, Any],
        result_summary: Dict[str, Any],
        result_markdown: str,
        duration_seconds: float = 0,
        key_findings: Optional[List[str]] = None,
    ) -> InvestigationRun:
        """
        Record an investigation that was run.
        
        TEACHING: After the LLM runs an investigation tool, it calls this
        to record what happened. This builds the session history.
        
        Args:
            investigation_type: Tool that was used (e.g., 'compare_presets')
            parameters: Parameters passed to the tool
            result_summary: JSON result from the tool
            result_markdown: Markdown-formatted result
            duration_seconds: How long did it take?
            key_findings: List of insights from this investigation
        
        Returns:
            InvestigationRun object (added to session history)
        """
        
        run = InvestigationRun(
            investigation_type=investigation_type,
            timestamp=datetime.now(),
            parameters=parameters,
            result_summary=result_summary,
            result_markdown=result_markdown,
            duration_seconds=duration_seconds,
            key_findings=key_findings or [],
        )
        
        self.investigation_history.append(run)
        return run
    
    def update_conclusion(self, key: str, value: Any) -> None:
        """
        Record a conclusion from this investigation.
        
        TEACHING: After analyzing results, the LLM might conclude:
        "NMC is the best chemistry for this application"
        
        We record that so later steps can refer back to it.
        
        Args:
            key: What aspect of the problem? (e.g., "best_chemistry")
            value: What's the conclusion? (e.g., "NMC")
        """
        self.conclusions[key] = value
    
    def get_conclusion(self, key: str) -> Optional[Any]:
        """Retrieve a previous conclusion."""
        return self.conclusions.get(key)
    
    def get_investigation_history(self) -> List[InvestigationRun]:
        """Get all investigations in this session, in order."""
        return self.investigation_history
    
    def num_investigations(self) -> int:
        """How many investigations have been done?"""
        return len(self.investigation_history)
    
    def total_simulation_time(self) -> float:
        """Total wall-clock time spent on simulations."""
        return sum(run.duration_seconds for run in self.investigation_history)
    
    # ========================================================================
    # Session Analysis
    # ========================================================================
    
    def get_reasoning_chain(self) -> str:
        """
        Describe the reasoning path taken during this investigation.
        
        TEACHING: This is how we audit the LLM's reasoning.
        "Here's what the LLM did:
        1. Compared chemistries
        2. Found NMC best
        3. Analyzed NMC sensitivity
        4. Identified temperature as key
        5. Optimized for temperature"
        
        This narrative shows the investigation strategy.
        """
        
        lines = [
            f"=== INVESTIGATION CHAIN: {self.name} ===",
            f"Started: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Investigations run: {self.num_investigations()}",
            f"Total simulation time: {self.total_simulation_time():.1f}s",
            "",
            "## Investigation Sequence:",
            "",
        ]
        
        for i, run in enumerate(self.investigation_history, 1):
            lines.append(f"{i}. **{run.investigation_type}** ({run.duration_seconds:.1f}s)")
            
            # What was tested?
            param_str = ", ".join(f"{k}={v}" for k, v in run.parameters.items())
            if param_str:
                lines.append(f"   Parameters: {param_str}")
            
            # What was found?
            if run.key_findings:
                lines.append(f"   Key findings:")
                for finding in run.key_findings:
                    lines.append(f"   - {finding}")
            
            lines.append("")
        
        # Conclusions
        if self.conclusions:
            lines.append("## Conclusions Reached:")
            lines.append("")
            for key, value in self.conclusions.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
        
        return "\n".join(lines)
    
    def identify_investigation_pattern(self) -> str:
        """
        Identify what kind of investigation strategy was used.
        
        TEACHING: Different LLMs might use different strategies:
        - Broad-to-narrow: Compare many, then focus on best
        - Constraint-driven: Check feasibility first, then optimize
        - Sensitivity-first: Understand parameter importance, then explore
        
        This classifies what the LLM did.
        """
        
        if not self.investigation_history:
            return "No investigations run"
        
        types = [r.investigation_type for r in self.investigation_history]
        
        if types[0] == 'compare_presets' and 'sensitivity_analysis' in types:
            return "🎯 Broad-to-narrow: Start with preset comparison, then analyze winner"
        elif 'constraint_check' in types[:2]:
            return "🛡️  Constraint-driven: Check feasibility first, then explore"
        elif types[0] == 'sensitivity_analysis':
            return "🔬 Sensitivity-first: Understand parameters, then explore"
        else:
            return "🔍 Custom exploration strategy"
    
    def generate_report(self) -> str:
        """
        Generate a complete session report.
        
        TEACHING: This is what gets saved to disk or shown to the engineer.
        It documents the entire investigation process.
        """
        
        lines = [
            "=" * 70,
            "INVESTIGATION SESSION REPORT",
            "=" * 70,
            "",
            f"Name: {self.name}",
            f"Started: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Investigations: {self.num_investigations()}",
            f"Total time: {self.total_simulation_time():.1f}s",
            f"Strategy: {self.identify_investigation_pattern()}",
            "",
        ]
        
        # Detail each investigation
        for i, run in enumerate(self.investigation_history, 1):
            lines.append(f"\n### Investigation {i}: {run.investigation_type}")
            lines.append(f"Timestamp: {run.timestamp.strftime('%H:%M:%S')}")
            lines.append(f"Duration: {run.duration_seconds:.1f}s")
            lines.append("")
            
            # Include the markdown result
            lines.append(run.result_markdown)
            lines.append("")
        
        # Conclusions
        if self.conclusions:
            lines.append("\n## FINAL CONCLUSIONS")
            lines.append("")
            for key, value in self.conclusions.items():
                lines.append(f"**{key}**: {value}")
            lines.append("")
        
        return "\n".join(lines)
    
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
        print(f"✅ Session saved to {filepath}")
    
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


# ============================================================================
# SESSION ANALYZER: Compare across sessions
# ============================================================================

class SessionAnalyzer:
    """
    Analyze and compare multiple investigation sessions.
    
    TEACHING: If we have multiple sessions, we can compare them:
    - How much computation did each strategy use?
    - Which led to better conclusions?
    - What patterns do we see across runs?
    """
    
    @staticmethod
    def compare_sessions(sessions: List[SimulationSession]) -> Dict[str, Any]:
        """
        Compare multiple sessions statistically.
        
        Args:
            sessions: List of SimulationSession objects
        
        Returns:
            Comparison statistics
        """
        
        comparison = {
            'num_sessions': len(sessions),
            'sessions': {},
        }
        
        for session in sessions:
            comparison['sessions'][session.name] = {
                'investigations': session.num_investigations(),
                'total_time_s': session.total_simulation_time(),
                'strategy': session.identify_investigation_pattern(),
                'conclusions': len(session.conclusions),
            }
        
        # Aggregate stats
        all_times = [s.total_simulation_time() for s in sessions]
        comparison['aggregate'] = {
            'avg_time_s': sum(all_times) / len(all_times) if all_times else 0,
            'total_time_s': sum(all_times),
            'total_investigations': sum(s.num_investigations() for s in sessions),
        }
        
        return comparison
    
    @staticmethod
    def generate_comparison_report(sessions: List[SimulationSession]) -> str:
        """Generate human-readable comparison of sessions."""
        if not sessions:
            return "No sessions to compare"
        
        comparison = SessionAnalyzer.compare_sessions(sessions)
        
        lines = [
            "=" * 70,
            "MULTI-SESSION COMPARISON",
            "=" * 70,
            "",
        ]
        
        # Summary
        lines.append(f"Sessions compared: {comparison['num_sessions']}")
        lines.append(f"Total investigations: {comparison['aggregate']['total_investigations']}")
        lines.append(f"Total computation time: {comparison['aggregate']['total_time_s']:.1f}s")
        lines.append("")
        
        # Per-session details
        lines.append("### Per-Session Breakdown")
        lines.append("")
        
        for name, stats in comparison['sessions'].items():
            lines.append(f"**{name}**")
            lines.append(f"- Investigations: {stats['investigations']}")
            lines.append(f"- Computation time: {stats['total_time_s']:.1f}s")
            lines.append(f"- Strategy: {stats['strategy']}")
            lines.append(f"- Conclusions: {stats['conclusions']}")
            lines.append("")
        
        return "\n".join(lines)
