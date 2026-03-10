"""
EXAMPLE: B12 - Quick Physical Correctness Test

PURPOSE: 
Simple, focused test of B12 functionality to validate if metrics are physically correct.
Run this, check the output, and you'll immediately see if there's a problem.

WHAT TO LOOK FOR:
✓ Do LFP and NMC show different peak power?
✓ Do metrics change with temperature?
✓ Does the API output show important differences?

If all metrics are identical → There's a problem
If metrics differ → B12 is working correctly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.model import Model
from battery_sim.core.solver import SolverConfig, Solver


def print_box(title: str) -> None:
    """Print a formatted box."""
    print("\n" + "╔" + "═" * 98 + "╗")
    print("║  " + title.ljust(96) + "║")
    print("╚" + "═" * 98 + "╝\n")


def test_chemistry_comparison():
    """Test 1: Do different chemistries produce different metrics?"""
    print_box("TEST 1: Chemistry Comparison (Physical Distinctiveness)")
    
    print("Comparing three chemistries at 25°C:")
    print("  • LFP_5AH (iron phosphate) - safe, low voltage")
    print("  • NMC_5AH (nickel manganese cobalt) - balanced")
    print("  • NCA_5AH (nickel cobalt aluminum) - high energy")
    print()
    
    api = AgentAPI(
        session_name="B12 Quick Test",
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    result = api.compare_presets(
        preset_names=['LFP_5AH', 'NMC_5AH', 'NCA_5AH'],
        environment_temp_C=25.0,
    )
    
    print(result.markdown_text)
    print()
    
    # Extract values for analysis
    json_data = result.json_data
    metrics = json_data.get('metrics', {})
    
    print("=" * 100)
    print("ANALYSIS")
    print("=" * 100)
    print()
    
    # Check peak power
    print("1️⃣  PEAK POWER TEST:")
    power_metric = metrics.get('peak_power_W', {})
    if 'values' in power_metric:
        lfp_power = power_metric['values'].get('LFP_5AH')
        nmc_power = power_metric['values'].get('NMC_5AH')
        nca_power = power_metric['values'].get('NCA_5AH')
        
        print(f"   LFP_5AH: {lfp_power:.2f}W")
        print(f"   NMC_5AH: {nmc_power:.2f}W")
        print(f"   NCA_5AH: {nca_power:.2f}W")
        
        # Check if they're identical
        if lfp_power == nmc_power == nca_power:
            print()
            print("   ❌ PROBLEM: All identical!")
            print("      → This is physically WRONG")
            print("      → Different nominal voltages should give different power")
            print(f"      → Expected: NCA > NMC > LFP")
            print(f"      → But got: {lfp_power} = {nmc_power} = {nca_power}")
        else:
            # Check if ranking makes sense
            ranking = sorted([(lfp_power, 'LFP'), (nmc_power, 'NMC'), (nca_power, 'NCA')], reverse=True)
            print()
            print(f"   ✅ GOOD: Different values")
            print(f"      Ranking: {' > '.join([name for _, name in ranking])}")
            if ranking[0][1] in ['NCA', 'NMC'] and ranking[-1][1] == 'LFP':
                print(f"      ✓ Ranking is physically sensible")
            else:
                print(f"      ⚠️  Ranking might be wrong")
    
    return metrics


def test_temperature_variation():
    """Test 2: Does temperature affect performance?"""
    print_box("TEST 2: Temperature Variation (Does T affect results?)")
    
    print("Testing NMC_5AH at different temperatures:")
    temperatures = [0, 25, 50]
    
    api = AgentAPI(
        session_name="B12 Temperature Test",
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    results_by_temp = {}
    for temp in temperatures:
        print(f"  {temp}°C...", end=" ", flush=True)
        result = api.compare_presets(
            preset_names=['NMC_5AH'],
            environment_temp_C=temp,
        )
        results_by_temp[temp] = result.json_data
        print("✓")
    
    print()
    print("=" * 100)
    print("ANALYSIS")
    print("=" * 100)
    print()
    
    print("2️⃣  TEMPERATURE SENSITIVITY TEST:")
    print()
    print(f"Temp (°C) | Peak Power (W) | Change")
    print("─" * 40)
    
    powers = {}
    for temp in temperatures:
        metrics = results_by_temp[temp].get('metrics', {})
        power = metrics.get('peak_power_W', {}).get('values', {}).get('NMC_5AH')
        powers[temp] = power
        
        if temp == 0:
            diff_str = "(baseline)"
        else:
            diff = power - powers.get(temperatures[0], power)
            diff_pct = (diff / powers.get(temperatures[0], 1.0)) * 100 if powers.get(temperatures[0]) else 0
            diff_str = f"({diff:+.2f}W, {diff_pct:+.1f}%)" if diff != 0 else "(no change)"
        
        print(f"{temp:9} | {power:14.2f} | {diff_str}")
    
    print()
    
    # Check if temperature affects anything
    power_0 = powers.get(0, 0)
    power_50 = powers.get(50, 0)
    
    if power_0 == power_50:
        print("❌ PROBLEM: Temperature has NO effect")
        print("   → Power should vary with temperature")
        print("   → Li-ion impedance is temperature-dependent")
        print("   → Expect ~2-3% change across 50°C range")
    else:
        diff = abs(power_50 - power_0)
        diff_pct = (diff / power_0) * 100 if power_0 > 0 else 0
        print(f"✅ GOOD: Temperature affects results")
        print(f"   Change: {diff:.2f}W ({diff_pct:.1f}%)")
        if 0.5 < diff_pct < 10:
            print(f"   ✓ Change magnitude seems reasonable")
        else:
            print(f"   ⚠️  Change seems unusual (expected ~1-3%)")


def test_expected_metrics():
    """Test 3: Are expected metrics present?"""
    print_box("TEST 3: Available Metrics Check")
    
    api = AgentAPI(
        session_name="B12 Metrics Test",
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    result = api.compare_presets(
        preset_names=['LFP_5AH'],
        environment_temp_C=25.0,
    )
    
    json_data = result.json_data
    metrics = json_data.get('metrics', {})
    
    print("3️⃣  METRICS AVAILABILITY TEST:")
    print()
    
    # Define expected vs actual
    expected_metrics = {
        'peak_voltage_V': 'Peak voltage (V)',
        'peak_current_A': 'Peak current (A)',
        'peak_power_W': 'Peak power (W)',
        'total_energy_Wh': 'Total energy (Wh)',
        'efficiency_percent': 'Round-trip efficiency (%)',
        'min_voltage_V': 'Minimum voltage (V)',
        'max_voltage_V': 'Maximum voltage (V)',
    }
    
    print("Expected Metrics:")
    found = 0
    for key, description in expected_metrics.items():
        if key in metrics:
            value = metrics[key]['values'].get('LFP_5AH')
            if value is not None:
                print(f"  ✅ {key:30} = {value:10.3f}  ({description})")
                found += 1
            else:
                print(f"  ⚠️  {key:30} (present but None) ({description})")
        else:
            print(f"  ❌ {key:30} (MISSING) ({description})")
    
    print()
    print(f"Summary: {found}/{len(expected_metrics)} expected metrics found")
    print()
    
    if found < len(expected_metrics):
        print("❌ PROBLEM: Missing important metrics")
        print("   Missing metrics make it hard to compare chemistries")
        print("   Without energy/efficiency/voltage, can't assess suitability")
    else:
        print("✅ GOOD: All expected metrics present")


def main():
    """Run quick physical correctness tests."""
    print("\n" + "╔" + "═" * 98 + "╗")
    print("║" + " B12 Agent-Ready API - Quick Physical Correctness Test ".center(98) + "║")
    print("╚" + "═" * 98 + "╝")
    
    print("""
This test checks if B12 API output is physically correct.

Tests:
 1. Chemistry comparison - Do different chemistries show different metrics?
 2. Temperature variation - Does temperature affect performance?
 3. Metrics availability - Are important metrics present?
    """)
    
    try:
        print("\nRunning tests...")
        print("(This will run several simulations. May take 30-60 seconds.)")
        
        test_chemistry_comparison()
        test_temperature_variation()
        test_expected_metrics()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print_box("RESULTS SUMMARY")
    
    print("""
WHAT TO LOOK FOR:

✅ PHYSICALLY CORRECT (B12 is working):
  • Different chemistries show different peak power
  • Temperature has measurable effect on metrics
  • All important metrics are present
  • Peak power ranking makes sense: NCA > NMC > LFP

❌ PHYSICALLY WRONG (B12 has a bug):
  • All chemistries show identical metrics
  • Temperature has no effect
  • Missing important metrics (energy, efficiency, voltage)
  • Peak power all the same (20.40 W)

NEXT STEPS:
  If metrics are identical → Check metric extraction in investigation_tools.py
  If temperature has no effect → Check environment propagation
  If metrics missing → Check result.py and result_formatter.py
    """)


if __name__ == '__main__':
    main()
