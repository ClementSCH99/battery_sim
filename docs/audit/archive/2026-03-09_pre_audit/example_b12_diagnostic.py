"""
EXAMPLE: B12 - Physical Correctness Testing & Diagnostics

PURPOSE:
Deep dive into what B12 is computing and validate each step.
This will help identify where physical correctness might be violated.

STRUCTURE:
- Test 1: Raw result inspection
- Test 2: Metric extraction
- Test 3: Chemistry comparison with detailed metrics
- Test 4: Signal availability
- Test 5: Expected vs. actual behavior
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.agent_api import AgentAPI
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.model import Model
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.core.environment import Environment
from battery_sim.core.cell_presets import CellPresets
from battery_sim.core.simulation import Simulation
from battery_sim.core.investigation_tools import SimulationComparison


def print_header(title: str) -> None:
    """Print major header."""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100 + "\n")


def print_subsection(title: str) -> None:
    """Print subsection."""
    print(f"\n{'─' * 100}")
    print(f"  {title}")
    print('─' * 100 + "\n")


def test_1_raw_results():
    """Test 1: Inspect raw simulation results. """
    print_subsection("TEST 1: Raw Simulation Results (No API Processing)")
    
    print("Running single simulations for LFP_5AH and NMC_5AH at 25°C")
    print("This shows what the simulator ACTUALLY produces.\n")
    
    # Create cells directly
    cells = {
        'LFP': CellPresets.get_cell('LFP_5AH'),
        'NMC': CellPresets.get_cell('NMC_5AH'),
    }
    
    # Create protocol
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=5.0, _duration_s=600),   # 10 min at 5A
        Rest(_duration_s=300),                              # 5 min rest
    ])
    
    # Create environment
    env = Environment(temperature_C=25.0)
    
    print("=" * 100)
    print("CHEMISTRY 1: LFP_5AH")
    print("=" * 100)
    
    try:
        sim_lfp = Simulation(
            cell=cells['LFP'],
            protocol=protocol,
            environment=env,
            model=Model.SPM,
            solver_config=SolverConfig(solver=Solver.CASADI),
        )
        
        result_lfp = sim_lfp.run()
        
        print(f"\nRuntime: {result_lfp.metadata.duration_s:.2f}s")
        print(f"Success: {result_lfp.metadata.success}")
        print(f"\nSignals Available in Result:")
        print(f"  Keys in result._data: {list(result_lfp._data.keys())}")
        
        print(f"\nKey Metrics (extracted):")
        print(f"  Peak Voltage: {result_lfp.peak_voltage():.3f} V")
        print(f"  Peak Current: {result_lfp.peak_current():.3f} A")
        print(f"  Peak Power: {result_lfp.peak_power():.3f} W")
        print(f"  Total Energy: {result_lfp.total_energy_Wh():.3f} Wh")
        print(f"  Efficiency: {result_lfp.charge_discharge_efficiency():.2f} %")
        print(f"  Final SOC: {result_lfp.final_soc():.1f} %")
        print(f"  Min Voltage: {result_lfp.min_voltage():.3f} V")
        print(f"  Max Voltage: {result_lfp.max_voltage():.3f} V")
        
        print(f"\nSignal Details:")
        for signal_name, timeseries in result_lfp._data.items():
            if timeseries is not None:
                vals = timeseries.values
                print(f"  {signal_name}:")
                print(f"    Min: {min(vals):.4f}, Max: {max(vals):.4f}, Mean: {sum(vals)/len(vals):.4f}")
                print(f"    Points: {len(vals)}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 100)
    print("CHEMISTRY 2: NMC_5AH")
    print("=" * 100)
    
    try:
        sim_nmc = Simulation(
            cell=cells['NMC'],
            protocol=protocol,
            environment=env,
            model=Model.SPM,
            solver_config=SolverConfig(solver=Solver.CASADI),
        )
        
        result_nmc = sim_nmc.run()
        
        print(f"\nRuntime: {result_nmc.metadata.duration_s:.2f}s")
        print(f"Success: {result_nmc.metadata.success}")
        print(f"\nSignals Available in Result:")
        print(f"  Keys in result._data: {list(result_nmc._data.keys())}")
        
        print(f"\nKey Metrics (extracted):")
        print(f"  Peak Voltage: {result_nmc.peak_voltage():.3f} V")
        print(f"  Peak Current: {result_nmc.peak_current():.3f} A")
        print(f"  Peak Power: {result_nmc.peak_power():.3f} W")
        print(f"  Total Energy: {result_nmc.total_energy_Wh():.3f} Wh")
        print(f"  Efficiency: {result_nmc.charge_discharge_efficiency():.2f} %")
        print(f"  Final SOC: {result_nmc.final_soc():.1f} %")
        print(f"  Min Voltage: {result_nmc.min_voltage():.3f} V")
        print(f"  Max Voltage: {result_nmc.max_voltage():.3f} V")
        
        print(f"\nSignal Details:")
        for signal_name, timeseries in result_nmc._data.items():
            if timeseries is not None:
                vals = timeseries.values
                print(f"  {signal_name}:")
                print(f"    Min: {min(vals):.4f}, Max: {max(vals):.4f}, Mean: {sum(vals)/len(vals):.4f}")
                print(f"    Points: {len(vals)}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # COMPARISON
    print("\n" + "=" * 100)
    print("PHYSICAL COMPARISON: LFP vs NMC")
    print("=" * 100)
    
    try:
        print("\nExpected Physical Differences:")
        print("  • Peak Voltage: LFP (~3.2V) < NMC (~3.7V)")
        print("  • Operating Voltage: LFP more constrained, NMC wider range")
        print("  • Energy Density: NMC > LFP for same capacity")
        print("  • Safety: LFP more stable, NMC higher energy")
        
        print("\n✓ Check above metrics and verify these relationships hold!")
    
    except Exception as e:
        print(f"Error in comparison: {e}")


def test_2_metric_extraction():
    """Test 2: How does metric extraction work?"""
    print_subsection("TEST 2: Metric Extraction from SimulationRun")
    
    print("Testing the metric extraction pipeline\n")
    
    # Create a simple simulation
    cell = CellPresets.get_cell('NMC_5AH')
    protocol = Protocol(steps=[ConstantCurrent(current_A=5.0, _duration_s=600)])
    env = Environment(temperature_C=25.0)
    
    sim = Simulation(
        cell=cell,
        protocol=protocol,
        environment=env,
        model=Model.SPM,
        solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    sim_run = sim.run()
    
    print(f"SimulationRun object type: {type(sim_run)}")
    print(f"SimulationRun attributes: {dir(sim_run)}")
    
    # Check result
    if hasattr(sim_run, 'result'):
        print(f"\n✓ Has .result attribute")
        print(f"  Result type: {type(sim_run.result)}")
    
    # Check metadata
    if hasattr(sim_run, 'metadata'):
        print(f"✓ Has .metadata attribute")
        print(f"  Metadata: {sim_run.metadata}")
    
    # Check diagnostics
    if hasattr(sim_run, 'diagnostics'):
        print(f"✓ Has .diagnostics attribute")
    
    # Check errors
    if hasattr(sim_run, 'errors'):
        print(f"✓ Has .errors attribute")
        print(f"  Error count: {len(sim_run.errors) if sim_run.errors else 0}")
    
    # Now test the comparison metric extraction
    print("\n" + "─" * 100)
    print("Testing SimulationComparison.extract_metrics:")
    print("─" * 100 + "\n")
    
    metrics = SimulationComparison.extract_metrics(sim_run)
    
    print("Extracted metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    print("\n⚠️  Issues to check:")
    print("  - Are all important metrics present?")
    print("  - Are values reasonable?")
    print("  - Are there NaN or None values that shouldn't be?")


def test_3_api_comparison():
    """Test 3: What does the API comparison actually show?"""
    print_subsection("TEST 3: API Comparison Results (Detailed)")
    
    print("Using AgentAPI.compare_presets() and inspecting JSON output\n")
    
    api = AgentAPI(
        session_name="Physical Correctness Diagnostic",
        default_model=Model.SPM,
        default_solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    print("Comparing: LFP_5AH, NMC_5AH, NCA_5AH (if available)\n")
    
    try:
        result = api.compare_presets(
            preset_names=['LFP_5AH', 'NMC_5AH'],
            environment_temp_C=25.0,
        )
        
        # Show markdown
        print("MARKDOWN OUTPUT:")
        print(result.markdown_text)
        
        # Show JSON structure
        print("\n\nJSON OUTPUT (detailed):")
        json_data = result.json_data
        
        print(json.dumps(json_data, indent=2))
        
        # Analyze what's in there
        print("\n\nJSON STRUCTURE ANALYSIS:")
        print(f"  Top-level keys: {list(json_data.keys())}")
        
        if 'metrics' in json_data:
            metrics = json_data['metrics']
            print(f"  Metrics available: {list(metrics.keys())}")
            print(f"\n  Detailed metric structure:")
            for metric_name in list(metrics.keys())[:3]:  # First 3
                print(f"    {metric_name}: {list(metrics[metric_name].keys())}")
        
        # Check values
        print("\n\nVALUE EXTRACTION:")
        if 'metrics' in json_data:
            for preset in ['LFP_5AH', 'NMC_5AH']:
                print(f"\n  {preset}:")
                for metric_name, metric_data in json_data['metrics'].items():
                    if 'values' in metric_data and preset in metric_data['values']:
                        val = metric_data['values'][preset]
                        print(f"    {metric_name}: {val}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_4_expected_physics():
    """Test 4: What physical behavior should we expect?"""
    print_subsection("TEST 4: Expected Physical Behavior")
    
    print("""
CHEMISTRY COMPARISON EXPECTATIONS (all at 25°C):

1. NOMINAL VOLTAGE:
   LFP:  2.5 - 3.65 V  (very flat curve)
   NMC:  2.75 - 4.2 V   (steeper, wider range)
   NCA:  2.75 - 4.3 V   (similar to NMC)
   
   ✓ Expected Peak Voltages:
     LFP < NMC ≈ NCA

2. ENERGY DENSITY:
   For same 5Ah capacity at nominal voltage:
   LFP:  ~18 Wh  (3.65V × 5Ah)
   NMC:  ~18 Wh  (3.7V × 5Ah)
   NCA:  ~19 Wh  (3.8V × 5Ah)
   
   ✓ Expected Total Energy:
     All roughly similar, NCA slightly higher

3. POWER DELIVERY:
   Depends on internal resistance and voltage drop under load.
   Higher OCV → higher power available at any SOC
   
   ✓ Expected Peak Power:
     NCA > NMC > LFP  (higher voltage = higher power at same current)

4. EFFICIENCY:
   Coulombic efficiency (reversibility) + voltage efficiency (irrev. losses)
   
   LFP: Highest (most stable, smallest voltage hysteresis)
   NMC: Medium (good reversibility)  
   NCA: Medium/Low (more complex chemistry)
   
   ✓ Expected Round-Trip Efficiency:
     LFP ≈ NMC > NCA  (especially at higher discharge rates)

5. THERMAL BEHAVIOR:
   Different chemistries have different impedance vs temperature
   
   ✓ Expected Temperature Sensitivity:
     LFP: Lower temp sensitivity (stable)
     NMC: Higher temp sensitivity (typical Li-ion)
     NCA: Similar to NMC

DIAGNOSTIC CHECKLIST:
☐ Do LFP and NMC show different peak voltages?
☐ Does energy scale correctly with capacity?
☐ Is power ranking: NCA > NMC > LFP?
☐ Is efficiency ranking: LFP ≈ NMC > NCA?
☐ Do metrics change with temperature?
☐ Do sensitivity values match physical intuition?
""")


def test_5_individual_signals():
    """Test 5: Check what individual signals are being computed."""
    print_subsection("TEST 5: Individual Signal Inspection")
    
    print("Running a single simulation and checking all signals\n")
    
    cell = CellPresets.get_cell('NMC_5AH')
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=5.0, _duration_s=600),
        Rest(_duration_s=300),
    ])
    env = Environment(temperature_C=25.0)
    
    sim = Simulation(
        cell=cell,
        protocol=protocol,
        environment=env,
        model=Model.SPM,
        solver_config=SolverConfig(solver=Solver.CASADI),
    )
    
    result = sim.run()
    
    print("All signals in result object:")
    print()
    
    for signal_name, timeseries in result._data.items():
        if timeseries is not None:
            vals = timeseries.values
            print(f"{str(signal_name):40} | Min: {min(vals):10.4f} | Max: {max(vals):10.4f} | Points: {len(vals):5d}")
    
    print("\n⚠️  Expected signals that might be missing:")
    print("  • Voltage (terminal voltage)")
    print("  • Current (discharge/charge current)")
    print("  • Temperature (if thermal model enabled)")
    print("  • Power (V × I)")
    print("  • Energy (integral of Power)")
    print("  • SOC (state of charge)")
    print("  • Efficiency metrics")


def main():
    """Run all diagnostic tests."""
    print_header("B12 PHYSICAL CORRECTNESS DIAGNOSTICS")
    
    print("""
This diagnostic suite investigates what B12 actually computes and 
checks if results are physically correct.

Tests:
 1. Raw simulation results (direct)
 2. Metric extraction pipeline
 3. API comparison output  
 4. Expected physical behavior
 5. Individual signals
    """)
    
    try:
        test_1_raw_results()
    except Exception as e:
        print(f"\n❌ Test 1 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_2_metric_extraction()
    except Exception as e:
        print(f"\n❌ Test 2 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_3_api_comparison()
    except Exception as e:
        print(f"\n❌ Test 3 failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        test_4_expected_physics()
    except Exception as e:
        print(f"\n❌ Test 4 failed: {e}")
    
    try:
        test_5_individual_signals()
    except Exception as e:
        print(f"\n❌ Test 5 failed: {e}")
        import traceback
        traceback.print_exc()
    
    print_header("DIAGNOSTIC COMPLETE")
    
    print("""
NEXT STEPS:
1. Review the raw simulation results and check if they differ between chemistries
2. Verify that metric extraction is capturing all available signals
3. Check if the API comparison shows expected differences
4. Compare actual results against expected physics
5. Identify which part of the pipeline removes physical distinction

COMMON ISSUES TO INVESTIGATE:
• All metrics showing identical values → problem in metric extraction
• All errors showing as "122 critical errors" → debug this sentinel value
• Missing efficiency/energy data → check if signals are available
• Temperature showing no effect → check environment propagation
""")


if __name__ == '__main__':
    main()
