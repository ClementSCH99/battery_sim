# B12 - Agent-Ready API (Final Implementation)

## Executive Summary

**Phase 2 Step B12** transforms battery_sim into an investigative tool for LLM-based reasoning. The API enables agents to explore parameter space, understand sensitivities, and make informed recommendations about battery chemistry and BMS tuning.

**Status**: 🚀 **IN PROGRESS**  
**Approach**: Incremental implementation with teaching comments  
**Target Lines of Code**: ~2200 (5 core modules + comprehensive example)  
**Backward Compatibility**: 100% (wraps existing B9-B11 APIs)  
**Key Innovation**: Session-aware investigation framework  

---

## Project Context

### Phase 2 Completion Path

| Step | Component | Status | Purpose |
|------|-----------|--------|---------|
| B9 | Result Enrichment | ✅ Complete | Extract signals + metrics |
| B10 | Parameter Control | ✅ Complete | Systematic exploration |
| B11 | Observability & Logging | ✅ Complete | Error detection + diagnostics |
| **B12** | **Agent-Ready API** | **🚀 In Progress** | **LLM-driven investigation** |

### B12 Goals

**Primary Goal**: Enable LLM agents to investigate electrochemical systems through iterative simulation and reasoning.

475

**Key Objectives**:
1. ✅ **Introspection** - APIs can describe available operations, parameters, signals
2. ✅ **Investigation** - Tools for comparison, sensitivity analysis, constraint checking
3. ✅ **Dual Results** - JSON (LLM processing) + Markdown (engineer reading)
4. ✅ **Session Memory** - Track investigation history for context
5. ✅ **Investigative Hints** - Support LLM reasoning without prescribing answers

---

## B12 Architecture

### The Five-Layer Design

```
┌─────────────────────────────────────────────────┐
│  AGENT-READY API (Investigative Framework)     │
├─────────────────────────────────────────────────┤
│                                                 │
│  Layer 5: AGENT API (entry point)              │
│  ├─ Python classes with tool decorators        │
│  ├─ REST endpoints (Phase 3)                   │
│  └─ Session management                         │
│                                                 │
│  Layer 4: SESSION MEMORY (investigation context)
│  ├─ Run history                                │
│  ├─ Comparison across runs                     │
│  └─ Context for chaining                       │
│                                                 │
│  Layer 3: RESULT FORMATTING (dual output)      │
│  ├─ JSON with schema definitions               │
│  ├─ Markdown for humans                        │
│  └─ Investigative hints                        │
│                                                 │
│  Layer 2: INVESTIGATION TOOLS (core reasoning) │
│  ├─ Batch simulations                          │
│  ├─ Comparison analysis                        │
│  ├─ Sensitivity quantification                 │
│  ├─ Constraint checking                        │
│  └─ Parameter space exploration                │
│                                                 │
│  Layer 1: API SCHEMA (self-documentation)      │
│  ├─ Preset catalog with metadata               │
│  ├─ Parameter space definitions                │
│  ├─ Signal definitions                         │
│  └─ Tool discovery                             │
│                                                 │
│  ↓ Built on B9-B11 ↓                           │
│  Result, SimulationRun, Parameter sweeps       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Why This Layering?

**Layer 1 (API Schema)** answers: "What can I do?"  
**Layer 2 (Investigation Tools)** answers: "How do I explore?"  
**Layer 3 (Result Formatting)** answers: "What does the result mean?"  
**Layer 4 (Session Memory)** answers: "How does this relate to prior runs?"  
**Layer 5 (Agent API)** answers: "How do I use this?"  

---

## Implementation Path (Incremental)

### Phase 1: Core Introspection (Layer 1)
**Goal**: Let LLM discover available operations  
**Files**: `core/api_schema.py`  
**Key Classes**:
- `APISchema`: Describe the entire system
- `ParameterSpace`: Document what parameters exist and their ranges
- `SignalCatalog`: List available metrics with descriptions
- `PresetCatalog`: Available chemistries with properties

**Learning Focus**: How to design self-documenting APIs

### Phase 2: Investigation Tools (Layer 2)
**Goal**: Provide reasoning primitives  
**Files**: `core/investigation_tools.py`  
**Key Classes**:
- `SimulationComparison`: Side-by-side analysis
- `BatchSimulator`: Run multiple scenarios
- `SensitivityAnalyzer`: Quantify parameter impacts
- `ConstraintChecker`: Feasibility validation
- `ParameterExplorer`: Guided search through space

**Learning Focus**: How to decompose complex operations into tools

### Phase 3: Result Formatting (Layer 3)
**Goal**: Output both for LLM and humans  
**Files**: `core/result_formatter.py`  
**Key Classes**:
- `DualFormatResult`: JSON + Markdown output
- `ComparisonFormatter`: Tables and analysis
- `HintExtractor`: Investigative guidance

**Learning Focus**: How to serve multiple audiences (LLM + engineer)

### Phase 4: Session Management (Layer 4)
**Goal**: Track investigation for context  
**Files**: `core/simulation_session.py`  
**Key Classes**:
- `SimulationSession`: Track runs + history
- `SessionAnalyzer`: Compare across sessions

**Learning Focus**: How to enable stateful reasoning

### Phase 5: Agent API (Layer 5)
**Goal**: User-facing interface  
**Files**: `core/agent_api.py`  
**Key Classes**:
- `AgentAPI`: Main entry point with decorated methods
- Tool methods for LLM integration

**Learning Focus**: How to expose tools cleanly

### Phase 6: Realistic Example (Capstone)
**Goal**: Show complete BMS investigation workflow  
**Files**: `example_b12_bms_investigation.py`  
**Demonstrates**:
- Cell chemistry comparison
- Sensitivity analysis for calibration
- Constraint-driven exploration
- Session-based reasoning chain

**Learning Focus**: How all pieces work together

---

## Key Design Principles

### 1. **Self-Documentation First**
Every operation should expose metadata about itself:
- What parameters can I vary?
- What ranges are valid?
- How does each affect the result?
- What constraints must be satisfied?

```python
# Instead of: "Run a simulation"
# Better: Expose parameter space
schema = APISchema()
param_space = schema.get_parameter_space('cell')
# Returns: 
# {
#   'nominal_capacity_Ah': {'min': 1.0, 'max': 50.0, 'default': 5.0},
#   'internal_resistance_Ohm': {'min': 0.005, 'max': 0.5, 'default': 0.05},
#   ...
# }
```

### 2. **Irreducible Complexity**
Some operations can't be simpler:
- Running a simulation requires actually running it (that's the investigation)
- Comparing sensitivity requires multiple runs
- BUT: Hide the complexity behind clean abstractions

```python
# Good: LLM doesn't need to know HOW
comparison = investigation.compare_presets(['LFP_5AH', 'NMC_5AH'])

# Not good: Exposing all the machinery
for preset in presets:
    sim = Simulation(...)  # LLM shouldn't manage this
    result = sim.run()
    # ... manual comparison
```

### 3. **Dual Output by Default**
Every result should be immediately useful to BOTH LLM and engineer:
- JSON: Machine-readable for processing
- Markdown: Human-readable for interpretation

### 4. **Hints Not Prescriptions**
Guide the LLM's reasoning without dictating conclusions:

```python
# Good: "This parameter has high sensitivity"
{
    "parameter": "temperature_C",
    "sensitivity": 0.68,
    "interpretation": "High - 68% change in efficiency over range"
}

# Not good: "You should change this"
{
    "parameter": "temperature_C",
    "recommendation": "increase to 40C for better performance"  # ❌ Too prescriptive
}
```

### 5. **Session as First-Class Concept**
Statefulness enables reasoning chains:

```python
session = SimulationSession()

# Run 1: Explore chemistry
comparison = session.run_investigation('compare_presets', ['LFP_5AH', 'NMC_5AH'])

# Run 2: Deep dive on winner
sensitivity = session.run_investigation('sensitivity_analysis', 
                                       preset='NMC_5AH',
                                       parameters=['temperature_C', 'nominal_capacity_Ah'])

# Later: "How did we get here?"
session.summarize_reasoning()
# → Shows the path of investigation
```

---

## LLM Integration Pattern (B12 Enables B13)

This is the foundation for **B13: LLM Agent Integration**:

```python
# What B12 builds:
agent_api = AgentAPI(session=my_session)

# What B13 will add:
from anthropic import Anthropic

client = Anthropic()
tools = agent_api.get_tools()  # B12 provides

response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=4096,
    tools=tools,  # ← Powered by B12
    messages=[{
        "role": "user",
        "content": "Recommend a cell chemistry for a high-power application. Use simulation to explore."
    }]
)
```

B12 builds the investigative engine. B13 will layer the LLM on top.

---

## Detailed Algorithms

### Comparison Algorithm

```
Input:
  - preset_names: List[str] (e.g., ['LFP_5AH', 'NMC_5AH'])
  - test_conditions: Optional protocol + environment

Algorithm:
  1. results = []
  2. For each preset_name:
     a. cell = Cell.preset(preset_name)
     b. sim = create_simulation(cell, test_conditions)
     c. run = sim.run()
     d. results.append((preset_name, run))
  
  3. For each metric in [efficiency, energy, peak_power, ...]:
     a. Compare metric across all results
     b. Compute relative differences
     c. Normalized to reference (e.g., first preset = 100%)
  
  4. Return ComparisonResult with:
     - JSON: queryable data structure
     - Markdown: readable table + insights
     - Hints: "NMC has 30% higher peak power"

Time Complexity: O(n × simulation_time) where n = number of presets
```

### Sensitivity Analysis Algorithm

```
Input:
  - baseline_preset: str
  - parameters_to_vary: List[str]
  - variation_ranges: Dict[str, List[values]]

Algorithm:
  1. baseline_cell = Cell.preset(baseline_preset)
  2. baseline_result = run_simulation(baseline_cell)
  3. baseline_metrics = extract_metrics(baseline_result)
  
  4. For each parameter in parameters_to_vary:
     a. For each value in variation_ranges[parameter]:
        i. modified_cell = copy(baseline_cell)
        ii. setattr(modified_cell, parameter, value)
        iii. result = run_simulation(modified_cell)
        iv. metrics = extract_metrics(result)
        v. Store (value, metrics)
     
     b. Compute sensitivity:
        - Range = max(metrics) - min(metrics)
        - Sensitivity = Range / baseline_metrics
  
  5. Rank parameters by sensitivity
  
  6. Return SensitivityAnalysis with:
     - Ranked parameters
     - Sensitivity coefficients
     - JSON + Markdown formats

Time Complexity: O(m × n × simulation_time)
where m = number of parameters, n = values per parameter
```

### Session Analyzer Algorithm

```
Input:
  - session: SimulationSession with history

Algorithm:
  1. investigations = session.get_all_investigations()
  2. For each investigation in order:
     a. Record: what was tested, why (inferred from context)
     b. Compute: what was learned (metric changes)
  
  3. Build reasoning chain:
     - Investigation 1 → Learning 1
     - Learning 1 guides Investigation 2
     - Learning 1 + 2 guide Investigation 3
  
  4. Identify patterns:
     - Which parameters mattered most?
     - How did conclusions evolve?
     - What was the search strategy?
  
  5. Generate narrative explaining the journey

Output: Annotated session trace showing reasoning flow
```

---

## Example Workflow (End-to-End)

The comprehensive example `example_b12_bms_investigation.py` will demonstrate:

**Scenario**: "Recommend a cell chemistry optimized for high-power output with acceptable cycle life"

**Investigation Flow**:
1. **Discovery**: What chemistries are available? What are their characteristics?
   - Tool: `compare_presets(['LFP_5AH', 'NMC_5AH', 'NCA_5AH', ...])`
   - Output: Comparison table showing power vs energy vs safety

2. **Narrowing**: Which 2-3 are most promising?
   - Tool: Analyze sensitivity of peak power to temperature
   - Filter: Keep only those with >15W peak power

3. **Refinement**: How sensitive is peak power to capacity for finalists?
   - Tool: `sensitivity_analysis(preset='NMC_5AH', parameters=['nominal_capacity_Ah'])`
   - Insight: "Capacity varies 3-6 Ah, affects power but not dramatically"

4. **Validation**: Can this work in practice?
   - Tool: `constraint_check(preset, scenario='high_power')`
   - Check: Voltage limits, current limits, thermal constraints

5. **Recommendation**: Based on analysis, which chemistry wins?
   - Synthesize: All prior learnings
   - Trade-offs: Power vs efficiency vs cost vs Safety

---

## Implementation Status

### ✅ Completed (B9-B11)
- Result enrichment (24+ signals)
- Parameter control (sweeps + presets)
- Observability (metadata + errors + diagnostics)
- Backward compatibility maintained

### 🚀 In Progress (B12)
- Layer 1: API Schema (introspection)
- Layer 2: Investigation Tools (core operations)
- Layer 3: Result Formatting (dual output)
- Layer 4: Session Management (memory)
- Layer 5: Agent API (entry point)
- Example: BMS investigation workflow

### 📋 Planned (Phase 3)
- B13: LLM Agent Integration (Claude + tools)
- BMS model expansion
- REST API (FastAPI endpoints)
- Performance optimization

---

## Learning Progression

As you implement B12, you'll learn:

1. **API Design**: How to make APIs self-documenting
2. **Abstraction**: How to hide complexity behind clean interfaces
3. **Dual Audiences**: Designing for both machines and humans
4. **Session Management**: How state enables reasoning
5. **Test-Driven Development**: Each layer builds on the last

Each module includes comments on the "why" behind design choices, so you can understand the reasoning, not just the code.

---

## Next Steps

1. Implement Layer 1: `core/api_schema.py`
2. Implement Layer 2: `core/investigation_tools.py`
3. Implement Layer 3: `core/result_formatter.py`
4. Implement Layer 4: `core/simulation_session.py`
5. Implement Layer 5: `core/agent_api.py`
6. Implement Example: `example_b12_bms_investigation.py`
7. Validate: All tests pass, examples run, backward compatibility maintained

Total estimated time: ~4-6 hours with teaching mode enabled.

---
