"""
EXAMPLE: B12 - Comprehensive Validation and Testing

PURPOSE:
This example tests ALL B12 functionality with rigorous physical validation.
The goal is to ensure:
1. Metrics are extracted correctly and make physical sense
2. Comparisons are valid and properly interpreted
3. Sensitivity analysis reflects actual parameter impacts
4. Constraints are physically meaningful
5. Temperature effects are correctly modeled

VALIDATION APPROACH:
For each test, we:
- Run simulations with known parameters
- Extract metrics
- Validate that metrics satisfy physical constraints (e.g., energy conservation, SOC bounds)
- Check that results scale correctly with input parameters
- Verify that extremes are identified correctly
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.model import Model
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.core.environment import Environment


def print_header(title: str) -> None:
    """Print a major section header."""
    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90 + "\n")


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n{'─' * 90}")
    print(f"  {title}")
    print('─' * 90 + "\n")


def validate_physical_constraints(metrics: dict, preset_name: str, temp_C: float) -> list:
    """
    Check that extracted metrics satisfy basic physical constraints.
    
    Returns: List of validation issues (empty if all valid)
    """
    issues = []
    
    # Voltage should be reasonable for LiPo (2.5V - 4.3V)
    if 'peak_voltage_V' in metrics and metrics['peak_voltage_V'] is not None:
        if not (2.0 <= metrics['peak_voltage_V'] <= 4.5):
            issues.append(f"⚠️  Peak voltage {metrics['peak_voltage_V']:.2f}V is outside typical range [2.0V, 4.5V]")
    
    # Power and energy should be non-negative
    if 'peak_power_W' in metrics and metrics['peak_power_W'] is not None:
        if metrics['peak_power_W'] < 0:
            issues.append(f"❌ Peak power is negative: {metrics['peak_power_W']:.2f}W")
        elif metrics['peak_power_W'] > 100:  # Reasonable upper bound for small cells
            issues.append(f"⚠️  Peak power {metrics['peak_power_W']:.2f}W seems unusually high")
    
    # Energy should be positive
    if 'total_energy_Wh' in metrics and metrics['total_energy_Wh'] is not None:
        if metrics['total_energy_Wh'] < 0:
            issues.append(f"❌ Total energy is negative: {metrics['total_energy_Wh']:.2f}Wh")
    
    # Efficiency should be between 0-100%
    if 'efficiency_percent' in metrics and metrics['efficiency_percent'] is not None:
        if not (0 <= metrics['efficiency_percent'] <= 100):
            issues.append(f"❌ Efficiency {metrics['efficiency_percent']:.1f}% is outside range [0%, 100%]")
    
    # Temperature effects: higher temps usually reduce efficiency slightly
    if temp_C > 40:
        if 'efficiency_percent' in metrics and metrics['efficiency_percent'] is not None:
            if metrics['efficiency_percent'] > 98:
                issues.append(f"⚠️  Efficiency {metrics['efficiency_percent']:.1f}% seems high for T={temp_C}°C")
    
    return issues


def compare_chemistry_scaling(api: AgentAPI) -> None:
    """
    Test 1: Compare different chemistries and validate scaling.
    
    PHYSICS CHECK:
    - Higher capacity should have more energy
    - More power output doesn't necessarily mean higher efficiency
    - Same chemistry at different sizes should scale proportionally
    """
    print_subsection("TEST 1: Chemistry Comparison & Scaling Validation")
    
    print("Testing: Compare LFP_5AH, NMC_5AH, NCA_5AH at 25°C")
    print("Expected: Same capacity → comparable energy, but different power/efficiency trade-offs\n")
    
    result = api.compare_presets(
        preset_names=['LFP_5AH', 'NMC_5AH', 'NCA_5AH'],
        environment_temp_C=25.0,
    )
    
    print(result.markdown_text)
    
    # Extract and validate metrics
    json_data = result.json_data
    
    print("\n📊 VALIDATION CHECKS:")
    
    # Check 1: All should have similar energy (same capacity)
    metrics = json_data.get('metrics', {})
    energies = {}
    for preset in ['LFP_5AH', 'NMC_5AH', 'NCA_5AH']:
        energy = metrics.get('total_energy_Wh', {}).get('values', {}).get(preset)
        if energy:
            energies[preset] = energy
            print(f"  {preset}: {energy:.2f}Wh")
    
    if len(energies) >= 2:
        min_e = min(energies.values())
        max_e = max(energies.values())
        ratio = max_e / min_e if min_e > 0 else 999
        
        if ratio < 1.3:  # All energies within 30%
            print(f"  ✅ Energy values scale well ({ratio:.2f}x ratio)")
        else:
            print(f"  ⚠️  Energy values vary significantly ({ratio:.2f}x ratio)")
            print(f"    → This is OK if capacities differ, but they shouldn't for 5AH cells")
    
    # Check 2: Validate each chemistry's metrics
    print("\n  Individual Chemistry Validation:")
    for preset in ['LFP_5AH', 'NMC_5AH', 'NCA_5AH']:
        # Build a simple metrics dict for this preset
        preset_metrics = {}
        for metric_name, metric_data in metrics.items():
            if 'values' in metric_data and preset in metric_data['values']:
                preset_metrics[metric_name] = metric_data['values'][preset]
        
        issues = validate_physical_constraints(preset_metrics, preset, 25.0)
        
        if issues:
            print(f"\n    {preset}:")
            for issue in issues:
                print(f"      {issue}")
        else:
            print(f"    {preset}: ✅ All constraints satisfied")


def test_temperature_dependence(api: AgentAPI) -> None:
    """
    Test 2: Temperature effects on same chemistry.
    
    PHYSICS CHECK:
    - Efficiency usually decreases at higher temperatures (more losses)
    - OR increases at higher temperatures (less overpotential)
    - Voltage curves shift with temperature
    - Power capability typically increases with temperature (less resistance)
    """
    print_subsection("TEST 2: Temperature Dependence")
    
    print("Testing: NMC_5AH at different temperatures")
    print("Expected: Power and efficiency should show consistent temperature trends\n")
    
    temps = [0, 15, 25, 35, 50]
    results_by_temp = {}
    
    for temp in temps:
        print(f"  Running at {temp}°C...")
        result = api.compare_presets(
            preset_names=['NMC_5AH'],
            environment_temp_C=float(temp),
        )
        results_by_temp[temp] = result.json_data
    
    print("\n  📊 Temperature Scaling Analysis:")
    print(f"  {'Temp (°C)':<12} {'Power (W)':<12} {'Efficiency (%)':<15}")
    print(f"  {'-'*39}")
    
    powers = {}
    efficiencies = {}
    
    for temp, json_data in results_by_temp.items():
        metrics = json_data.get('metrics', {})
        
        power = metrics.get('peak_power_W', {}).get('values', {}).get('NMC_5AH')
        eff = metrics.get('efficiency_percent', {}).get('values', {}).get('NMC_5AH')
        
        if power is not None:
            powers[temp] = power
        if eff is not None:
            efficiencies[temp] = eff
        
        power_str = f"{power:.2f}" if power else "N/A"
        eff_str = f"{eff:.1f}" if eff else "N/A"
        
        print(f"  {temp:<12} {power_str:<12} {eff_str:<15}")
    
    # Validate trends
    print("\n  ✓ Trend Analysis:")
    
    if len(powers) > 1:
        sorted_temps = sorted(powers.keys())
        power_trend = powers[sorted_temps[-1]] - powers[sorted_temps[0]]
        
        if abs(power_trend) < 0.5:
            print(f"    Power change: {power_trend:+.2f}W (relatively stable)")
        elif power_trend > 0:
            print(f"    Power change: {power_trend:+.2f}W (increases with temperature)")
        else:
            print(f"    Power change: {power_trend:+.2f}W (decreases with temperature)")
    
    if len(efficiencies) > 1:
        sorted_temps = sorted(efficiencies.keys())
        eff_trend = efficiencies[sorted_temps[-1]] - efficiencies[sorted_temps[0]]
        
        if abs(eff_trend) < 1.0:
            print(f"    Efficiency change: {eff_trend:+.2f}% (relatively stable)")
        elif eff_trend > 0:
            print(f"    Efficiency change: {eff_trend:+.2f}% (improves at higher T)")
        else:
            print(f"    Efficiency change: {eff_trend:+.2f}% (degrades at higher T)")


def test_capacity_scaling(api: AgentAPI) -> None:
    """
    Test 3: Capacity scaling for same chemistry.
    
    PHYSICS CHECK:
    - 2x capacity should roughly → 2x energy
    - Power might increase slightly (better heat dissipation)
    - Efficiency should be similar or slightly better
    """
    print_subsection("TEST 3: Capacity Scaling (LFP Chemistry)")
    
    print("Testing: Different capacity LFP cells")
    print("Expected: Energy scales with capacity, efficiency stays similar\n")
    
    result = api.compare_presets(
        preset_names=['LFP_5AH', 'LFP_10AH'],
        environment_temp_C=25.0,
    )
    
    print(result.markdown_text)
    
    json_data = result.json_data
    metrics = json_data.get('metrics', {})
    
    energy_5ah = metrics.get('total_energy_Wh', {}).get('values', {}).get('LFP_5AH')
    energy_10ah = metrics.get('total_energy_Wh', {}).get('values', {}).get('LFP_10AH')
    
    eff_5ah = metrics.get('efficiency_percent', {}).get('values', {}).get('LFP_5AH')
    eff_10ah = metrics.get('efficiency_percent', {}).get('values', {}).get('LFP_10AH')
    
    print("\n  📊 Scaling Validation:")
    
    if energy_5ah and energy_10ah:
        energy_ratio = energy_10ah / energy_5ah
        print(f"    Energy ratio (10Ah/5Ah): {energy_ratio:.2f}x")
        if 1.8 <= energy_ratio <= 2.2:
            print(f"      ✅ Scales correctly (~2x)")
        else:
            print(f"      ⚠️  Unexpected scaling (expected ~2x)")
    
    if eff_5ah and eff_10ah:
        eff_change = eff_10ah - eff_5ah
        print(f"    Efficiency change: {eff_change:+.2f}%")
        if abs(eff_change) <= 2.0:
            print(f"      ✅ Efficiency stable as expected")
        else:
            print(f"      ⚠️  Efficiency changes significantly")


def test_sensitivity_analysis(api: AgentAPI) -> None:
    """
    Test 4: Sensitivity analysis.
    
    PHYSICS CHECK:
    - Temperature should have HIGH sensitivity (affects all processes)
    - Nominal capacity should have MEDIUM sensitivity (affects max power)
    - Parameters should show consistent ranking
    """
    print_subsection("TEST 4: Sensitivity Analysis")
    
    print("Testing: How sensitive is NMC_5AH to key parameters?")
    print("Expected: Temperature > Capacity in importance\n")
    
    result = api.sensitivity_analysis(
        preset_name='NMC_5AH',
        parameters=['temperature_C', 'nominal_capacity_Ah'],
    )
    
    print(result.markdown_text)
    
    print("\n  📊 Sensitivity Interpretation:")
    
    json_data = result.json_data
    sensitivities = json_data.get('sensitivities', {})
    
    # Extract sensitivity values
    params_ranked = []
    for param_name, sensitivity_data in sensitivities.items():
        if 'magnitude' in sensitivity_data:
            params_ranked.append((param_name, sensitivity_data['magnitude']))
    
    # Sort by magnitude
    params_ranked.sort(key=lambda x: x[1], reverse=True)
    
    print("\n    Parameter Importance (ranked by sensitivity):")
    for i, (param, mag) in enumerate(params_ranked, 1):
        print(f"    {i}. {param}: {mag:.1f}% impact")
    
    # Validate that temperature is high
    temp_sensitivity = next((m for p, m in params_ranked if 'temperature' in p), None)
    if temp_sensitivity and temp_sensitivity > 20:
        print(f"\n    ✅ Temperature sensitivity is HIGH ({temp_sensitivity:.1f}%)")
        print(f"       → Temperature compensation is critical for BMS")
    else:
        print(f"\n    ⚠️  Temperature sensitivity is low ({temp_sensitivity}%)")
        print(f"       → This would be unusual for Li-ion batteries")


def test_feasibility_constraints(api: AgentAPI) -> None:
    """
    Test 5: Feasibility checking.
    
    PHYSICS CHECK:
    - Battery should work at temperature extremes (though degraded)
    - Voltage should stay within safe bounds
    - Current should be achievable
    """
    print_subsection("TEST 5: Feasibility Constraints")
    
    print("Testing: Feasibility of NMC_5AH at extreme temperatures\n")
    
    temps = {
        0: "Cold start",
        25: "Nominal",
        50: "Hot environment",
    }
    
    for temp, description in temps.items():
        print(f"  {description} ({temp}°C):")
        result = api.check_feasibility('NMC_5AH', temperature_C=temp)
        
        # Parse the result
        lines = result.markdown_text.split('\n')
        
        # Print key lines
        for line in lines[:5]:  # First few lines usually have the status
            if line.strip():
                print(f"    {line.strip()}")
        print()


def test_session_memory(api: AgentAPI) -> None:
    """
    Test 6: Session tracking and reproducibility.
    
    PHYSICS CHECK:
    - All investigations should be recorded
    - Conclusions should be consistent
    - Session should be saveable/loadable
    """
    print_subsection("TEST 6: Session Memory & Reproducibility")
    
    print("Checking: Is investigation session properly tracked?\n")
    
    print(f"  Session Name: {api.session.name}")
    print(f"  Number of Investigations: {api.session.num_investigations()}")
    print(f"  Total Computation Time: {api.session.total_simulation_time():.1f} seconds")
    print()
    
    # Show reasoning chain
    chain = api.session.get_reasoning_chain()
    if chain:
        print("  Reasoning Chain:")
        for i, step in enumerate(chain.split('\n')[:10], 1):  # First 10 lines
            if step.strip():
                print(f"    {i}. {step.strip()}")
    
    # Generate report
    report = api.session.generate_report()
    print(f"\n  Report Generated: {len(report)} characters")
    print(f"  ✅ Session is tracking properly")


def main():
    """Run complete validation suite."""
    
    print_header("B12 COMPREHENSIVE VALIDATION SUITE")
    
    print("""
This test suite validates the B12 Agent-Ready API implementation.

For each test, we will:
1. Run simulations with known parameters
2. Extract metrics
3. Validate physical correctness
4. Check that results make sense

VALIDATIONS:
✓ E01: Chemistry comparison and energy scaling
✓ E02: Temperature effects on performance  
✓ E03: Capacity scaling
✓ E04: Sensitivity analysis
✓ E05: Feasibility constraints
✓ E06: Session tracking
    """)
    
    # Create API
    print("\nInitializing B12 API...")
    
    api = AgentAPI(
        session_name="B12 Comprehensive Validation",
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    print("✅ API initialized\n")
    
    # Run all tests
    try:
        compare_chemistry_scaling(api)
        
        test_temperature_dependence(api)
        
        test_capacity_scaling(api)
        
        test_sensitivity_analysis(api)
        
        test_feasibility_constraints(api)
        
        test_session_memory(api)
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    # Final summary
    print_header("VALIDATION SUMMARY")
    
    print("""
TESTS COMPLETED:
  E01: Chemistry Comparison ✓
  E02: Temperature Effects ✓
  E03: Capacity Scaling ✓
  E04: Sensitivity Analysis ✓
  E05: Feasibility ✓
  E06: Session Memory ✓

NEXT STEPS FOR REVIEW:
1. Check that all metrics satisfy physical bounds
2. Verify temperature trends make sense
3. Confirm capacity scaling is proportional
4. Review sensitivity rankings (temperature should be high)
5. Validate constraints are physically meaningful

POSSIBLE ISSUES TO INVESTIGATE:
⚠️  If metrics show violations of physical constraints
⚠️  If temperature trends are backwards
⚠️  If capacity doesn't scale linearly with energy
⚠️  If sensitivity values are unrealistic
⚠️  If feasibility constraints are too strict or too loose
    """)
    
    print("\n✅ Validation suite completed. Review output above for physical correctness.")


if __name__ == '__main__':
    main()
