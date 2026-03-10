"""
Example: B10 - Parameter Control with Presets and Sweeps

This example demonstrates:
1. Using cell presets for quick setup
2. Accessing preset metadata
3. Single-parameter sweeps (sensitivity analysis)
4. Multi-dimensional parameter sweeps
5. Analyzing sensitivity to parameters
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.cell import Cell
from battery_sim.core.cell_presets import CellPresets
from battery_sim.core.environment import Environment
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.simulation import Simulation
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.core.parameter_sweep import ParameterSweep, ParameterOverride
from battery_sim.backend.pybamm_backend import PyBaMMBackend


def main():
    print("=" * 70)
    print("B10 - PARAMETER CONTROL EXAMPLE")
    print("=" * 70)
    
    # ========== Part 1: Using Cell Presets ==========
    print("\n" + "=" * 70)
    print("PART 1: CELL PRESETS")
    print("=" * 70)
    
    # List all available presets
    all_presets = Cell.list_presets()
    print(f"\nAvailable presets ({len(all_presets)} total):")
    for preset_name in sorted(all_presets):
        print(f"  • {preset_name}")
    
    # Create cells from presets
    print("\n\nCreating cells from presets...")
    cell_lfp = Cell.preset('LFP_5AH')
    cell_nmc = Cell.preset('NMC_5AH')
    cell_nca = Cell.preset('NCA_5AH')
    
    print(f"\nLFP Cell:")
    print(f"  Chemistry: {cell_lfp.chemistry}")
    print(f"  Capacity: {cell_lfp.nominal_capacity_Ah} Ah")
    print(f"  Voltage: {cell_lfp.nominal_voltage_V} V")
    print(f"  Internal Resistance: {cell_lfp.internal_resistance_Ohm} Ω")
    
    print(f"\nNMC Cell:")
    print(f"  Chemistry: {cell_nmc.chemistry}")
    print(f"  Capacity: {cell_nmc.nominal_capacity_Ah} Ah")
    print(f"  Voltage: {cell_nmc.nominal_voltage_V} V")
    print(f"  Internal Resistance: {cell_nmc.internal_resistance_Ohm} Ω")
    
    print(f"\nNCA Cell:")
    print(f"  Chemistry: {cell_nca.chemistry}")
    print(f"  Capacity: {cell_nca.nominal_capacity_Ah} Ah")
    print(f"  Voltage: {cell_nca.nominal_voltage_V} V")
    print(f"  Internal Resistance: {cell_nca.internal_resistance_Ohm} Ω")
    
    # Show preset details
    print("\n\nDetailed preset information (NMC_5AH):")
    print(CellPresets.describe('NMC_5AH'))
    
    # Get presets by chemistry
    print("\n\nLFP presets available:")
    lfp_presets = CellPresets.by_chemistry('LFP')
    for preset_name in lfp_presets.keys():
        preset = lfp_presets[preset_name]
        print(f"  {preset_name}: {preset.description}")
    
    # ========== Part 2: Simple Parameter Override Examples ==========
    print("\n" + "=" * 70)
    print("PART 2: PARAMETER OVERRIDE (Standalone ParameterOverride class)")
    print("=" * 70)
    
    # Create a parameter override to track changes
    override = ParameterOverride(
        cell_parameters={'nominal_capacity_Ah': 6.0},
        environment_parameters={'temperature_C': 45.0}
    )
    
    print("\nParameter override tracking:")
    print(override.summary())
    print(f"\nSerialized to dict: {override.to_dict()}")
    
    # ========== Part 3: Single-Parameter Sensitivity (Capacity) ==========
    print("\n" + "=" * 70)
    print("PART 3: SINGLE-PARAMETER SWEEP (Capacity)")
    print("=" * 70)
    
    # Set up baseline simulation
    protocol = (
        Protocol.cc(1.0, 3600)
        + Protocol.rest(1800)
        + Protocol.cc(-1.0, 3600)
    )
    
    baseline_sim = Simulation(
        cell=Cell.preset('NMC_5AH'),
        model=Model.SPM,
        protocol=protocol,
        environment=Environment(temperature_C=25.0),
        backend=PyBaMMBackend(),
        solver_config=SolverConfig(solver=Solver.CASADI, rtol=1e-6)
    )
    
    print("\nRunning capacity sweep: 3.0, 4.0, 5.0, 6.0 Ah...")
    capacity_values = [3.0, 4.0, 5.0, 6.0]
    
    sweep_results = ParameterSweep.sweep_cell_parameter(
        baseline_sim,
        'nominal_capacity_Ah',
        capacity_values,
        verbose=True
    )
    
    print(f"\n✓ Completed {len(sweep_results)} simulations")
    
    print("\nResults summary:")
    print(f"{'Capacity (Ah)':<15} {'Peak Power (W)':<15} {'Total Energy (Wh)':<20} {'Efficiency (%)':<15}")
    print("-" * 65)
    for sr in sweep_results:
        capacity = sr.parameter_value
        peak_power = sr.simulation_result.peak_power() or 0
        total_energy = sr.simulation_result.total_energy() or 0
        efficiency = sr.simulation_result.charge_discharge_efficiency() or 0
        print(f"{capacity:<15.1f} {peak_power:<15.1f} {total_energy:<20.2f} {efficiency:<15.1f}")
    
    # Analyze sensitivity
    print("\n\nSensitivity Analysis:")
    sensitivity = ParameterSweep.analyze_sensitivity(
        sweep_results,
        lambda r: r.peak_power() or 0,
        "Peak Power"
    )
    
    print(f"  Parameter: {sensitivity['parameter_name']}")
    print(f"  Metric: {sensitivity['metric_name']}")
    print(f"  Range: {sensitivity['min']:.1f} - {sensitivity['max']:.1f} W")
    print(f"  Sensitivity: {sensitivity['sensitivity']:.2f} ({sensitivity['range']:.1f} W)")
    
    # ========== Part 4: Temperature Sweep ==========
    print("\n" + "=" * 71)
    print("PART 4: TEMPERATURE SWEEP")
    print("=" * 70)
    
    print("\nRunning temperature sweep: 0, 25, 40, 60°C...")
    temp_values = [0, 25, 40, 60]
    
    temp_sweep_results = ParameterSweep.sweep_environment_parameter(
        baseline_sim,
        'temperature_C',
        temp_values,
        verbose=True
    )
    
    print(f"\n✓ Completed {len(temp_sweep_results)} simulations")
    
    print("\nTemperature impact:")
    print(f"{'Temperature (°C)':<20} {'Internal Resistance (Ω)':<25} {'Efficiency (%)':<15}")
    print("-" * 60)
    for sr in temp_sweep_results:
        temp = sr.parameter_value
        ir = sr.simulation_result.average_internal_resistance() or 0
        efficiency = sr.simulation_result.charge_discharge_efficiency() or 0
        print(f"{temp:<20.0f} {ir:<25.4f} {efficiency:<15.1f}")
    
    # ========== Part 5: Multi-Dimensional Sweep ==========
    print("\n" + "=" * 70)
    print("PART 5: MULTI-DIMENSIONAL SWEEP (Capacity × Temperature)")
    print("=" * 70)
    
    print("\nRunning 2D parameter sweep: 3 capacities × 2 temperatures = 6 simulations...")
    
    params = {
        'cell::nominal_capacity_Ah': [4.0, 5.0, 6.0],
        'environment::temperature_C': [25, 40],
    }
    
    multi_results = ParameterSweep.multi_parameter_sweep(
        baseline_sim,
        params,
        verbose=True
    )
    
    print(f"\n✓ Completed {len(multi_results)} simulations")
    
    print("\nMulti-dimensional results:")
    print(f"{'Capacity (Ah)':<15} {'Temperature (°C)':<20} {'Efficiency (%)':<15} {'Peak Power (W)':<15}")
    print("-" * 65)
    for param_dict, result, override in multi_results:
        capacity = param_dict.get('nominal_capacity_Ah', 'N/A')
        temperature = param_dict.get('temperature_C', 'N/A')
        efficiency = result.charge_discharge_efficiency() or 0
        peak_power = result.peak_power() or 0
        print(f"{capacity:<15} {temperature:<20} {efficiency:<15.1f} {peak_power:<15.1f}")
    
    # ========== Summary ==========
    print("\n" + "=" * 70)
    print("B10 SUMMARY")
    print("=" * 70)
    print("""
✅ Cell Presets: Quick access to realistic battery chemistries
   - 9 presets available (LFP, NMC, NCA, LCO, LMNO, HE, HP)
   - Each includes physical parameters and metadata

✅ Parameter Override Tracking: Know what changed
   - ParameterOverride class tracks cell/environment changes
   - Supports serialization (to_dict/from_dict)
   - Compatible with future logging (B11)

✅ Single-Parameter Sweeps: Analyze one parameter's effect
   - sweep_cell_parameter(): Vary capacity, voltage, resistance, etc.
   - sweep_environment_parameter(): Vary temperature, convection, etc.
   - Sensitivity analysis: Quantify parameter impact

✅ Multi-Dimensional Sweeps: Understand combinations
   - Vary multiple parameters simultaneously
   - Automatically generates all combinations
   - Scalable to any number of dimensions

Ready for B11 (Observability & Logging) and B12 (Agent-Ready API)
    """)


if __name__ == "__main__":
    main()
