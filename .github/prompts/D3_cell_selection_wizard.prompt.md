---
mode: agent
description: Add cell selection wizard with scored recommendations
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add an interactive cell selection wizard that ranks presets based on application requirements.

## TASK
Implement **cell_selection_wizard** — takes EV application requirements and returns scored, ranked cell recommendations.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Tasks D1 (enhanced presets with metadata) and D2 (pack sizing)
- Cell presets have: energy density, cost, C-rate, cycle life, weight, volume metadata
- This is the "decision support" capstone — combine sizing, comparison, and scoring into one tool
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `CellSelectionScorer` in `core/investigation_tools.py`
```python
class CellSelectionScorer:
    """Score and rank cell presets against application requirements."""
    
    def score(
        self,
        requirements: dict,
        presets: list[CellPreset],
    ) -> list[dict]:
        """
        Requirements dict keys:
            range_km: float          # Target range
            power_kW: float          # Peak power requirement
            weight_budget_kg: float  # Max pack weight
            volume_budget_L: float   # Max pack volume (optional)
            cost_budget_usd: float   # Max pack cost (optional)
            lifetime_years: float    # Minimum required lifetime
            charge_time_min: float   # Target 10-80% charge time (optional)
        
        Returns list of scored presets, sorted best-first:
            [{preset_name, total_score, scores_breakdown, pack_config, meets_requirements, recommendation}, ...]
        """
```
- Scoring dimensions (each 0-100):
  - `energy_score`: can the cell achieve targeted range within weight/volume budget?
  - `power_score`: does C-rate capability meet peak power demand?
  - `cost_score`: pack cost within budget?
  - `lifetime_score`: cycle life meets lifetime requirement?
  - `charge_score`: fast charge capability meets charge time target?
- Total score = weighted average (equal weights by default)
- `meets_requirements`: boolean, True if all hard constraints met
- `recommendation`: one-sentence summary ("Best for..." or "Fails on...")

### 2. Add `cell_selection_wizard()` to AgentAPI
- Signature:
  ```python
  def cell_selection_wizard(
      self,
      range_km: float = 400.0,
      power_kW: float = 150.0,
      weight_budget_kg: float = 500.0,
      lifetime_years: float = 8.0,
      cost_budget_usd: float | None = None,
      charge_time_min: float | None = None,
  ) -> DualFormatResult
  ```
- Uses CellSelectionScorer with all available presets
- Returns DualFormatResult with:
  - JSON: ranked results with scores and pack configs
  - Markdown: executive summary, ranked table, per-preset recommendation, "best for" callouts

### 3. Add executive summary formatting in `core/result_formatter.py`
- Add a `format_executive_summary()` function or method:
  - Plain language, no jargon
  - Key takeaways in 3-5 bullet points
  - Clear go/no-go recommendation
  - Suitable for non-battery-expert stakeholders

### 4. Add MCP tool in `mcp_server.py`

### 5. Add tests
- Test CellSelectionScorer scoring math
- Test cell_selection_wizard returns ranked results
- Test that "meets_requirements" correctly identifies failing presets
- Test executive summary is non-empty and contains key info

### 6. Write clean, minimal code
- Do not over-engineer
- Add comments explaining scoring logic

## OUTPUT
- Working code: CellSelectionScorer, cell_selection_wizard API + MCP, executive summary formatter, tests passing
- A report in `/docs/reports/D3_cell_selection_wizard.md` including:
  - What was done
  - Key decisions (scoring weights, requirement thresholds)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- Multi-criteria decision making for cell selection
- Why no single "best" cell exists — it depends on application priorities
- The engineering tradeoff space: energy vs power vs cost vs lifetime
- How OEMs actually perform cell selection (testing, simulation, benchmarking)
