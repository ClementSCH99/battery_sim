"""
Example: B9 - Result Enrichment with Advanced Analysis

This example demonstrates:
1. Running a simulation with PyBaMM backend
2. Accessing enriched result signals (power, energy, capacity)
3. Using Result analysis methods (efficiency, SOH, etc.)
4. Using ResultAnalyzer for post-processing
5. Cycle detection and analysis
"""

from battery_sim.core.simulation import Simulation
from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest, CC_CV
from battery_sim.core.environment import Environment
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.backend.pybamm_backend import PyBaMMBackend
from battery_sim.types.signal import Signal
from battery_sim.core.result_analyzer import ResultAnalyzer


def main():
    # ========== Setup: Define cell, protocol, environment ==========
    
    # Create a battery cell (using Nickel-Cobalt-Aluminum chemistry - typical EV cell)
    cell = Cell(
        chemistry="NCA",
        nominal_capacity_Ah=5.0,            # 5 Ah cell
        nominal_voltage_V=3.7,               # 3.7V nominal
        electrode_area_m2=0.05,              # 50 cm² electrode area
        electrode_thickness_m=100e-6,        # 100 μm thick electrode
        density_kg_per_m3=2200.0,            # Typical lithium compound density
        specific_heat_J_per_kgK=800.0,       # Specific heat capacity
        thermal_conductivity_W_per_mK=5.0    # Thermal conductivity
    )
    
    # Create a simple charge-rest-discharge protocol
    protocol = (
        Protocol([ConstantCurrent(current_A=-1.0, _duration_s=3600)])   # Charge at 1A for 1h
        + Protocol([Rest(_duration_s=600)])                              # Rest for 10 min
        + Protocol([ConstantCurrent(current_A=1.0, _duration_s=3600)])   # Discharge at 1A for 1h
    )
    
    # Create environment (room temperature)
    environment = Environment(
        temperature_C=25.0,
        convection_W_per_m2K=10.0
    )
    
    # Configure solver
    solver_config = SolverConfig(
        solver=Solver.CASADI,
        rtol=1e-6,
        atol=1e-9,
        time_step_s=60.0  # 1-minute resolution
    )
    
    # Create PyBaMM backend
    backend = PyBaMMBackend()
    
    # Create and run simulation
    print("=" * 70)
    print("B9 - RESULT ENRICHMENT EXAMPLE")
    print("=" * 70)
    print("\nSetting up simulation...")
    print(f"  Cell: {cell.chemistry} {cell.nominal_capacity_Ah} Ah")
    print(f"  Protocol: Charge 1h → Rest 10m → Discharge 1h")
    print(f"  Environment: {environment.temperature_C}°C")
    
    simulation = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend,
        solver_config=solver_config
    )
    
    print("\nRunning simulation...")
    result = simulation.run()
    
    # ========== ACCESS ENRICHED RESULT SIGNALS ==========
    print("\n" + "=" * 70)
    print("ENRICHED SIGNALS AVAILABLE")
    print("=" * 70)
    
    available = result.available_signals()
    print(f"\nTotal signals available: {len(available)}")
    for signal in available:
        print(f"  • {signal.value}")
    
    # ========== QUICK ANALYSIS USING RESULT METHODS ==========
    print("\n" + "=" * 70)
    print("QUICK ANALYSIS - Result Methods")
    print("=" * 70)
    
    print(f"\nElectrical Metrics:")
    print(f"  Total Energy:                {result.total_energy():.2f} Wh")
    print(f"  Total Capacity Delivered:    {result.total_capacity_delivered():.2f} Ah")
    print(f"  Peak Power:                  {result.peak_power():.1f} W")
    print(f"  Average Power:               {result.average_power():.1f} W")
    
    print(f"\nVoltage Analysis:")
    print(f"  Min Voltage:                 {result.min_voltage():.3f} V")
    print(f"  Max Voltage:                 {result.max_voltage():.3f} V")
    
    print(f"\nState of Charge:")
    final_soc = result.final_soc()
    if final_soc:
        print(f"  Final SOC:                   {final_soc:.1f} %")
    
    print(f"\nTemperature Analysis:")
    print(f"  Min Temperature:             {result.min_temperature():.2f} °C")
    print(f"  Max Temperature:             {result.max_temperature():.2f} °C")
    
    print(f"\nInternal Resistance:")
    avg_ir = result.average_internal_resistance()
    if avg_ir:
        print(f"  Average Internal Resistance: {avg_ir:.4f} Ω")
    
    # ========== ADVANCED ANALYSIS USING ResultAnalyzer ==========
    print("\n" + "=" * 70)
    print("ADVANCED ANALYSIS - ResultAnalyzer")
    print("=" * 70)
    
    analyzer = ResultAnalyzer(result)
    
    # State of Health
    if cell.nominal_capacity_Ah:
        soh = analyzer.state_of_health(cell.nominal_capacity_Ah)
        if soh:
            print(f"\nHealth Estimation:")
            print(f"  State of Health (SOH):       {soh:.2f} %")
    
    # Cycle detection
    cycles = []
    if cell.nominal_capacity_Ah:
        cycles = analyzer.detect_cycles(
            soc_threshold_percent=10.0,
            nominal_capacity_Ah=cell.nominal_capacity_Ah
        )
    if cycles:
        print(f"\nCycle Analysis:")
        print(f"  Cycles Detected:             {len(cycles)}")
        for cycle in cycles:
            print(f"\n  Cycle #{cycle.cycle_number}:")
            print(f"    Time:                    {cycle.start_time_s:.0f}s - {cycle.end_time_s:.0f}s")
            print(f"    Capacity Charged:        {cycle.capacity_charged_Ah:.3f} Ah")
            print(f"    Capacity Discharged:     {cycle.capacity_discharged_Ah:.3f} Ah")
            print(f"    Energy In:               {cycle.energy_in_Wh:.2f} Wh")
            print(f"    Energy Out:              {cycle.energy_out_Wh:.2f} Wh")
            print(f"    Efficiency:              {cycle.efficiency:.1f} %")
            print(f"    Depth of Discharge:      {cycle.depth_of_discharge:.1f} %")
            print(f"    Voltage Range:           {cycle.min_voltage_V:.2f} - {cycle.max_voltage_V:.2f} V")
            print(f"    SOC Range:               {cycle.min_soc:.1f} - {cycle.max_soc:.1f} %")
    
    # Temperature excursions
    temp_exc = analyzer.temperature_excursions(min_temp_C=0.0, max_temp_C=60.0)
    if temp_exc:
        print(f"\nTemperature Safety Check:")
        print(f"  Below 0°C events:            {temp_exc['below_min_count']}")
        print(f"  Above 60°C events:           {temp_exc['above_max_count']}")
    
    # Voltage safety
    volt_exc = analyzer.voltage_excursions(min_voltage_V=2.5, max_voltage_V=4.2)
    if volt_exc:
        print(f"\nVoltage Safety Check:")
        print(f"  Below 2.5V events:           {volt_exc['below_min_count']}")
        print(f"  Above 4.2V events:           {volt_exc['above_max_count']}")
    
    # ========== GENERATE COMPREHENSIVE REPORT ==========
    print("\n" + "=" * 70)
    report = analyzer.summary_report(nominal_capacity_Ah=cell.nominal_capacity_Ah)
    print(report)
    
    # ========== SIGNAL SUMMARY ==========
    print("\n" + "=" * 70)
    print("STATE VARIABLES SUMMARY")
    print("=" * 70)
    summary = result.state_variables_summary()
    print(f"\n{'Signal':<30} {'Min':>10} {'Mean':>10} {'Max':>10} {'Final':>10}")
    print("-" * 70)
    for signal, stats in summary.items():
        ts = result.get(signal)
        unit = ts.unit
        print(f"{signal.value:<30} {stats['min']:>10.3f} {stats['mean']:>10.3f} "
              f"{stats['max']:>10.3f} {stats['final']:>10.3f} ({unit})")
    
    print("\n" + "=" * 70)
    print("✓ B9 Result Enrichment Example Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
