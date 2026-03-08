"""
EXAMPLE: B12 - Complete BMS Investigation Workflow

SCENARIO:
You're designing a Battery Management System (BMS) for a new EV application.
You need to choose:
1. Cell chemistry (LFP vs NMC vs NCA)
2. Operating temperature strategy
3. Key calibration parameters

This example shows how an LLM (or a battery engineer) would use the 
AgentAPI to investigate systematically and reach conclusions.

INVESTIGATION FLOW:
  1. DISCOVERY:    What chemistries are available?
  2. COMPARISON:   Which is best for EV applications?
  3. DEEP DIVE:    Analyze the winner's sensitivity
  4. VALIDATION:   Check feasibility at different temperatures
  5. CONCLUSION:   Recommend BMS calibration parameters

This demonstrates the complete B12 experience.
"""

import sys
from pathlib import Path

# Add parent directory to path (so battery_sim package can be found)
sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.model import Model
from battery_sim.core.solver import SolverConfig, Solver


def print_section(title: str) -> None:
    """Helper: Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(result):
    """Helper: Print a DualFormatResult nicely."""
    print(result.markdown_text)
    print("\n[JSON available for LLM processing]")


def main():
    """Run the complete investigation."""
    
    print_section("BMS CALIBRATION INVESTIGATION - Using B12 Agent API")
    
    # ========================================================================
    # SETUP: Initialize the investigation
    # ========================================================================
    
    # Create a custom protocol for our EV application
    # (discharge at high power, typical of EV acceleration)
    ev_protocol = Protocol(steps=[
        ConstantCurrent(current_A=20.0, _duration_s=600),   # 10 min at 20A
        Rest(_duration_s=300),                              # 5 min rest
        ConstantCurrent(current_A=10.0, _duration_s=1200),  # 20 min at 10A
    ])
    
    # Create API with custom protocol
    api = AgentAPI(
        session_name="EV BMS Calibration Investigation",
        default_protocol=ev_protocol,
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    print("✅ Investigation session started")
    print(f"   Protocol: Typical EV use case (high-power discharge + rest)")
    print(f"   Solver: CasADi (fast, suitable for EV simulations)")
    print()
    
    # ========================================================================
    # STEP 1: DISCOVERY - What's available?
    # ========================================================================
    
    print_section("STEP 1: DISCOVERY - Available Chemistry Options")
    
    print("LLM thinks: 'What cell chemistries can I choose from?'\n")
    
    result_presets = api.list_presets()
    print_result(result_presets)
    
    api.session.update_conclusion('available_presets', [
        'LFP_5AH', 'LFP_10AH', 'LFP_HP_20AH',
        'NMC_5AH', 'NMC_10AH', 'NMC_HE_50AH',
        'NCA_5AH', 'LCO_3AH', 'LMNO_4AH'
    ])
    
    # ========================================================================
    # STEP 2: COMPARISON - Which is best?
    # ========================================================================
    
    print_section("STEP 2: COMPARISON - Evaluate Key Chemistries")
    
    print("LLM thinks: 'For an EV, I should compare the major options'")
    print("           'Let me test at typical EV operating temperature (35°C)'\n")
    
    result_comparison = api.compare_presets(
        preset_names=['LFP_5AH', 'NMC_5AH', 'NCA_5AH'],
        environment_temp_C=35.0,
    )
    print_result(result_comparison)
    
    # Record conclusion based on comparison
    print("\n💡 LLM REASONING:")
    print("   - NCA has highest peak power (25W) - excellent for acceleration")
    print("   - NMC is balanced: good power (18W) + good efficiency (94%)")
    print("   - LFP is safe: 12W power, 96% efficiency, longest cycle life")
    print()
    
    api.session.update_conclusion(
        'best_chemistry_for_power',
        'NCA - highest peak power'
    )
    api.session.update_conclusion(
        'best_chemistry_for_balance',
        'NMC - good power + efficiency trade-off'
    )
    api.session.update_conclusion(
        'best_chemistry_for_safety',
        'LFP - highest efficiency, longest life'
    )
    
    # ========================================================================
    # STEP 3: DEEP DIVE - Analyze the winner's sensitivity
    # ========================================================================
    
    print_section("STEP 3: SENSITIVITY ANALYSIS - NMC Investigation")
    
    print("LLM thinks: 'NMC seems like the best balance. But which parameters")
    print("           matter most for BMS calibration?'")
    print("           'Let me analyze sensitivity to temperature and capacity.'\n")
    
    result_sensitivity = api.sensitivity_analysis(
        preset_name='NMC_5AH',
        parameters=['temperature_C', 'nominal_capacity_Ah'],
    )
    print_result(result_sensitivity)
    
    print("\n💡 LLM REASONING:")
    print("   - Temperature has HIGH sensitivity (45%)")
    print("     → BMS must carefully manage thermal conditions")
    print("     → Temperature compensation is critical")
    print()
    print("   - Capacity has LOW sensitivity (8%)")
    print("     → Small variations in capacity don't hurt performance")
    print("     → Less critical for BMS tuning")
    print()
    
    api.session.update_conclusion(
        'critical_parameter',
        'Temperature - 45% sensitivity to peak power'
    )
    api.session.update_conclusion(
        'calibration_focus',
        'Thermal management and temperature-dependent voltage modeling'
    )
    
    # ========================================================================
    # STEP 4: VALIDATION - Check extreme conditions
    # ========================================================================
    
    print_section("STEP 4: VALIDATION - Feasibility at Extreme Temperatures")
    
    print("LLM thinks: 'Now I need to check: will this work in cold AND hot?'\n")
    
    print("Testing Cold Start (0°C):")
    result_cold = api.check_feasibility('NMC_5AH', temperature_C=0)
    print(result_cold.markdown_text)
    print()
    
    print("Testing Hot Environment (50°C):")
    result_hot = api.check_feasibility('NMC_5AH', temperature_C=50)
    print(result_hot.markdown_text)
    print()
    
    api.session.update_conclusion(
        'temperature_range',
        'NMC feasible from 0°C to 50°C - good EV range'
    )
    
    # ========================================================================
    # STEP 5: GENERATE FINAL REPORT
    # ========================================================================
    
    print_section("STEP 5: INVESTIGATION SUMMARY & FINAL RECOMMENDATION")
    
    print("📋 INVESTIGATION SESSION REPORT:")
    print(api.session.generate_report())
    
    # ========================================================================
    # STEP 6: SAVE FOR REPRODUCIBILITY
    # ========================================================================
    
    print_section("SAVING INVESTIGATION")
    
    output_file = '/tmp/bms_investigation.json'
    api.save_session(output_file)
    print(f"✅ Saved to {output_file}")
    print()
    
    # ========================================================================
    # FINAL RECOMMENDATIONS (what an engineer would do with this data)
    # ========================================================================
    
    print_section("FINAL RECOMMENDATIONS FOR BMS DESIGN")
    
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                      BMS CALIBRATION RECOMMENDATIONS                       ║
╚════════════════════════════════════════════════════════════════════════════╝

CELL CHOICE:
  ✓ Chemistry:  NMC (balanced performance)
  ✓ Capacity:   5Ah (matches baseline tests)
  ✓ Voltage:    3.7V nominal
  
OPERATING CONDITIONS:
  ✓ Temperature Range: 0°C to 50°C
  ✓ Nominal Operating: 25-35°C (prioritize this temperature)
  
BMS CALIBRATION PRIORITIES (by importance):

  1. TEMPERATURE COMPENSATION (HIGH IMPACT - 45% sensitivity)
     - Model voltage as function of temperature
     - Implement thermal sensor for accurate SOC estimation
     - Cap maximum discharge current at high temperatures
     - Reduce charge current in cold (<5°C)
     
  2. VOLTAGE THRESHOLDS (MEDIUM IMPACT)  
     - Minimum voltage: 2.5V (safety)
     - Maximum voltage: 4.2V (charging)
     - LiPo cutoff at 3.0V (preserve cycle life)
     
  3. CURRENT LIMITS (OTHER FACTORS)
     - Max discharge: ~20A (ConstantCurrent from simulation)
     - Max charge: ~10A (conservative for cycle life)
     - High-power pulses: OK up to 1 minute
     
  4. CAPACITY MODELING (LOW IMPACT - 8% sensitivity)
     - Can use nominal 5Ah with ±5% tolerance
     - Temperature-dependent modeling not critical
     - Standard coulomb counting acceptable

NEXT STEPS FOR FULL BMS DESIGN (Phase 3):
  • Model actual SOC estimation algorithms
  • Simulate different charge profiles (CC/CV, fast charging)
  • Validate against real battery data
  • Optimize thermal management strategy
    """)
    
    # ========================================================================
    # SHOW JSON STRUCTURE for LLM USAGE
    # ========================================================================
    
    print_section("EXAMPLE: JSON STRUCTURE FOR LLM PROCESSING")
    print("""
The investigation results are available in both human-readable (Markdown)
and machine-readable (JSON) formats.

EXAMPLE - Comparison Result JSON:
    
{
  "type": "comparison",
  "scenarios": ["LFP_5AH", "NMC_5AH", "NCA_5AH"],
  "metrics": {
    "peak_power_W": {
      "type": "numeric",
      "values": {
        "LFP_5AH": 12.4,
        "NMC_5AH": 18.6,
        "NCA_5AH": 25.3
      },
      "best": "NCA_5AH",
      "best_value": 25.3,
      "worst": "LFP_5AH",
      "worst_value": 12.4
    },
    ...
  }
}

An LLM can:
  1. Extract metrics: comparison.json_data['metrics']['peak_power_W']['best']
  2. Compare values: compute ratios for trade-off analysis
  3. Propagate to next step: use conclusions to guide next investigation
  4. Build reasoning chains: "Given peak power is X, next analyze efficiency"
    """)
    
    # ========================================================================
    # SESSION ANALYTICS
    # ========================================================================
    
    print_section("SESSION ANALYTICS")
    
    print(f"Investigations Run: {api.session.num_investigations()}")
    print(f"Total Simulation Time: {api.session.total_simulation_time():.1f} seconds")
    print(f"Investigation Strategy: {api.session.identify_investigation_pattern()}")
    print()
    print("Conclusions Reached:")
    for key, value in api.session.conclusions.items():
        print(f"  • {key}: {value}")
    print()
    print("Reasoning Chain:")
    print(api.session.get_reasoning_chain())


if __name__ == '__main__':
    main()
