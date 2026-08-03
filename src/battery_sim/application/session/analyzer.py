"""Cross-session comparison helpers."""

from typing import Any, Dict, List

from battery_sim.application.session.facade import SimulationSession

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
