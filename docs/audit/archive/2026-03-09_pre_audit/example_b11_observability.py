"""
Example: Using B11 Observability Features

Demonstrates usage patterns for observability, error detection, 
and diagnostics with SimulationRun.

Teaching Focus:
- Access simulation metadata (timing, configuration, convergence)
- Detect errors automatically (physical + numerical violations)
- Interpret solver diagnostics (convergence rate, problem stiffness)
- Backward compatibility with Result API
- JSON serialization for logging/reproducibility
- Parameter tracking and reproducibility
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from battery_sim.core.cell import Cell
from battery_sim.core.model import Model
from battery_sim.core.environment import Environment
from battery_sim.core.protocol import Protocol, ConstantCurrent, Rest
from battery_sim.core.simulation import Simulation
from battery_sim.core.solver import SolverConfig, Solver
from battery_sim.backend.pybamm_backend import PyBaMMBackend


# ==============================================================================
# EXAMPLE 1: Basic Observability Access
# ==============================================================================

def example_1_basic_observability():
    """
    Access simulation metadata, errors, and diagnostics from a basic simulation.
    """
    print("\nEXAMPLE 1: Basic Observability Access")
    print("-" * 70)
    
    # Create a simple discharge protocol
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=5.0, _duration_s=3600),  # Discharge at 5A for 1 hour
    ])
    
    # Use a cell preset
    cell = Cell.preset('NMC_5AH')
    environment = Environment(temperature_C=25.0)
    
    solver_config = SolverConfig(solver=Solver.CASADI)
    backend = PyBaMMBackend()
    
    # Create and run simulation
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend,
        solver_config=solver_config
    )
    
    run = sim.run()
    
    # Access observability data
    print(f"\nMetadata (Observability Layer):")
    print(f"  Timestamp: {run.metadata.timestamp_utc}")
    print(f"  Duration: {run.metadata.duration_s:.3f}s")
    print(f"  Solver: {run.metadata.solver_type}")
    print(f"  Convergence: {run.metadata.convergence_reason}")
    
    print(f"\nErrors Detected: {len(run.errors)}")
    if run.errors:
        for error in run.errors:
            print(f"  - {error.error_type.name}: {error.message}")
    else:
        print("  None - simulation successful!")
    
    print(f"\nDiagnostics (Solver Performance):")
    print(f"  Total time steps: {run.diagnostics.total_time_steps}")
    print(f"  Avg Newton iterations: {run.diagnostics.avg_newton_iterations:.1f}")
    print(f"  Max Newton iterations: {run.diagnostics.max_newton_iterations}")
    print(f"  Problem stiffness: {run.diagnostics.problem_description}")


# ==============================================================================
# EXAMPLE 2: Error Detection and Severity
# ==============================================================================

def example_2_error_detection():
    """
    Demonstrate automatic error detection for problematic simulations.
    """
    print("\nEXAMPLE 2: Error Detection and Severity Classification")
    print("-" * 70)
    
    # Create a protocol with potentially problematic conditions
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=10.0, _duration_s=1800),  # High current discharge
    ])
    
    cell = Cell.preset('NMC_5AH')
    environment = Environment(temperature_C=50.0)  # Higher temperature
    
    solver_config = SolverConfig(solver=Solver.SCIPY)
    backend = PyBaMMBackend()
    
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend,
        solver_config=solver_config
    )
    
    run = sim.run()
    
    # Check simulation status
    print(f"\nSimulation Status:")
    print(f"  Is successful: {run.is_successful()}")
    print(f"  Has critical errors: {run.has_critical_errors()}")
    print(f"  Has warnings: {run.has_warnings()}")
    print(f"  Total issues: {len(run.errors)}")
    
    if run.has_critical_errors():
        print(f"\nCritical Errors:")
        for error in run.get_critical_errors():
            print(f"  Type: {error.error_type.name}")
            print(f"  Severity: {error.severity}")
            print(f"  Message: {error.message}")


# ==============================================================================
# EXAMPLE 3: Performance Diagnostics
# ==============================================================================

def example_3_performance_diagnostics():
    """
    Interpret solver diagnostics to understand convergence behavior.
    """
    print("\nEXAMPLE 3: Performance Diagnostics Interpretation")
    print("-" * 70)
    
    # Standard discharge protocol
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=1.0, _duration_s=3600),
    ])
    
    cell = Cell.preset('LFP_5AH')
    environment = Environment(temperature_C=25.0)
    
    backend = PyBaMMBackend()
    solver_config = SolverConfig(solver=Solver.CASADI)
    
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend,
        solver_config=solver_config
    )
    
    run = sim.run()
    
    diag = run.diagnostics
    
    print(f"\nIteration Statistics:")
    print(f"  Total time steps: {diag.total_time_steps}")
    print(f"  Min Newton iterations/step: {diag.min_newton_iterations}")
    print(f"  Max Newton iterations/step: {diag.max_newton_iterations}")
    print(f"  Avg Newton iterations/step: {diag.avg_newton_iterations:.1f}")
    
    print(f"\nProblem Classification:")
    print(f"  Convergence rate: {diag.convergence_rate.name}")
    print(f"  Problem stiffness: {diag.problem_description}")
    print(f"  Is well-behaved: {diag.is_well_behaved()}")
    print(f"  Is stiff: {diag.is_stiff()}")
    
    # Interpretation
    if diag.avg_newton_iterations > 50:
        print("\n  Interpretation: Problem is VERY stiff")
    elif diag.avg_newton_iterations > 20:
        print("\n  Interpretation: Problem is moderately stiff")
    else:
        print("\n  Interpretation: Problem is well-behaved")


# ==============================================================================
# EXAMPLE 4: Backward Compatibility with Result API
# ==============================================================================

def example_4_backward_compatibility():
    """
    Show that SimulationRun delegates to Result - all old API still works!
    """
    print("\nEXAMPLE 4: Backward Compatibility - Result API Methods")
    print("-" * 70)
    
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=2.0, _duration_s=1800),
        Rest(_duration_s=600),
        ConstantCurrent(current_A=-2.0, _duration_s=1800),
    ])
    
    cell = Cell.preset('NMC_5AH')
    environment = Environment(temperature_C=25.0)
    backend = PyBaMMBackend()
    
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend
    )
    
    run = sim.run()
    
    # All Result methods work through delegation
    print(f"\nResult Performance Metrics (via delegation):")
    
    peak_power = run.peak_power()
    if peak_power:
        print(f"  Peak power: {peak_power:.2f} W")
    
    avg_power = run.average_power()
    if avg_power:
        print(f"  Average power: {avg_power:.2f} W")
    
    efficiency = run.charge_discharge_efficiency()
    if efficiency:
        print(f"  Charge-discharge efficiency: {efficiency:.1f}%")
    
    net_energy = run.net_energy()
    if net_energy:
        print(f"  Net energy delivered: {net_energy:.2f} Wh")
    
    print(f"\nVoltage Profile:")
    min_v = run.min_voltage()
    max_v = run.max_voltage()
    if min_v and max_v:
        print(f"  Min: {min_v:.2f}V, Max: {max_v:.2f}V")
    
    print(f"\nAvailable signals: {len(run.available_signals())} total")


# ==============================================================================
# EXAMPLE 5: JSON Serialization for Logging
# ==============================================================================

def example_5_serialization_for_logging():
    """
    Export complete simulation data to JSON for archival/logging.
    """
    print("\nEXAMPLE 5: JSON Serialization for Logging/Archival")
    print("-" * 70)
    
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=3.0, _duration_s=1200),
    ])
    
    cell = Cell.preset('LFP_5AH')
    environment = Environment(temperature_C=25.0)
    backend = PyBaMMBackend()
    
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend
    )
    
    run = sim.run()
    
    # Serialize to dictionary (JSON-ready)
    data_dict = run.to_dict()
    
    print(f"\nSerialized Data Structure:")
    print(f"  Top-level keys: {list(data_dict.keys())}")
    print(f"  Metadata keys: {list(data_dict['metadata'].keys())}")
    print(f"  Errors recorded: {len(data_dict['errors'])}")
    print(f"  Diagnostics keys: {list(data_dict['diagnostics'].keys())}")
    
    print(f"\nExample Metadata Export:")
    meta = data_dict['metadata']
    print(f"  timestamp_utc: {meta['timestamp_utc']}")
    print(f"  duration_s: {meta['duration_s']:.3f}")
    print(f"  solver_type: {meta['solver_type']}")
    
    json_str = json.dumps(data_dict, indent=2)
    print(f"\nJSON export ready (size: {len(json_str)} bytes)")


# ==============================================================================
# EXAMPLE 6: Parameter Tracking (B10 Integration)
# ==============================================================================

def example_6_parameter_tracking():
    """
    Show how B11 integrates with B10 parameter tracking.
    """
    print("\nEXAMPLE 6: Parameter Tracking (B10+B11 Integration)")
    print("-" * 70)
    
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=1.5, _duration_s=2400),
    ])
    
    cell = Cell.preset('NMC_5AH')
    environment = Environment(temperature_C=25.0)
    backend = PyBaMMBackend()
    
    sim = Simulation(
        cell=cell,
        model=Model.SPM,
        protocol=protocol,
        environment=environment,
        backend=backend
    )
    
    run = sim.run()
    
    print(f"\nMetadata tracks:")
    print(f"  Solver used: {run.metadata.solver_type}")
    print(f"  Convergence: {run.metadata.convergence_reason}")
    print(f"  Duration: {run.metadata.duration_s:.3f}s")
    
    print(f"\nFor reproducibility:")
    print(f"  Timestamp: {run.metadata.timestamp_utc}")
    print(f"  All parameters stored in metadata")


# ==============================================================================
# EXAMPLE 7: Comprehensive Debugging Workflow
# ==============================================================================

def example_7_debugging_workflow():
    """
    Complete workflow showing how B11 helps debug simulation issues.
    """
    print("\nEXAMPLE 7: Comprehensive Debugging Workflow")
    print("-" * 70)
    
    # Attempt a challenging simulation
    protocol = Protocol(steps=[
        ConstantCurrent(current_A=8.0, _duration_s=900),
    ])
    
    cell = Cell.preset('NMC_5AH')
    environment = Environment(temperature_C=45.0)
    backend = PyBaMMBackend()
    
    sim = Simulation(
        cell=cell,
        model=Model.DFN,
        protocol=protocol,
        environment=environment,
        backend=backend,
        solver_config=SolverConfig(solver=Solver.SCIPY)
    )
    
    run = sim.run()
    
    print(f"\nDiagnostic Report:")
    print(f"  Convergence: {run.metadata.convergence_reason}")
    print(f"  Duration: {run.metadata.duration_s:.3f}s")
    print(f"  Solver: {run.metadata.solver_type}")
    
    if run.has_critical_errors():
        print(f"\nCritical Issues ({len(run.get_critical_errors())}):")
        for error in run.get_critical_errors():
            print(f"  - {error.error_type.name}")
    else:
        print(f"\nNo critical errors")
    
    print(f"\nSolver Diagnostics:")
    diag = run.diagnostics
    print(f"  Time steps: {diag.total_time_steps}")
    print(f"  Iterations/step: {diag.avg_newton_iterations:.1f} avg")
    print(f"  Problem: {diag.problem_description}")


# ==============================================================================
# MAIN: Run All Examples
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("B11 OBSERVABILITY EXAMPLES - Complete Tutorial")
    print("="*80)
    print("\nDemonstrating 7 key features of B11:")
    print("  1. Basic observability access")
    print("  2. Error detection and severity")
    print("  3. Performance diagnostics")
    print("  4. Backward compatibility with Result API")
    print("  5. JSON serialization")
    print("  6. Parameter tracking (B10+B11)")
    print("  7. Debugging workflow")
    
    print("\n" + "="*80 + "\n")
    
    try:
        example_1_basic_observability()
        example_2_error_detection()
        example_3_performance_diagnostics()
        example_4_backward_compatibility()
        example_5_serialization_for_logging()
        example_6_parameter_tracking()
        example_7_debugging_workflow()
        
        print("\n" + "="*80)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*80)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
