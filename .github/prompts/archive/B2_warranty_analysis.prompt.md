---
mode: agent
description: Add warranty analysis tool
---

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end: add a warranty analysis tool that evaluates if a cell meets warranty requirements.

## TASK
Implement **warranty_analysis** — given a cell, usage profile, and warranty target, determine pass/fail with margin.

## CONTEXT
- Project: PyBaMM battery assistant API (`battery_sim`)
- Depends on: Task B1 (predict_lifetime, UsageProfile, calendar aging)
- This tool reuses predict_lifetime internally and adds warranty-specific logic
- Common EV warranty: 8 years / 160,000 km / 70-80% SOH retention
- AgentAPI returns `DualFormatResult`, MCP server wraps it
- Keep code simple and modular

## INSTRUCTIONS

### 1. Add `warranty_analysis()` to AgentAPI
- Signature:
  ```python
  def warranty_analysis(
      self,
      preset_name: str,
      warranty_years: float = 8.0,
      warranty_km: float = 160000.0,
      warranty_soh_threshold: float = 0.80,
      usage_profile: dict | None = None,
      temperature_C: float = 25.0,
  ) -> DualFormatResult
  ```
- Logic:
  1. Build UsageProfile from dict (or use defaults)
  2. Call `predict_lifetime()` internally to get capacity fade trajectory
  3. Calculate cycles at warranty end: `warranty_years × 365 × usage_profile.daily_charge_cycles`
  4. Calculate km at warranty end: `warranty_years × 365 × usage_profile.daily_km`
  5. Interpolate SOH at warranty end from capacity trajectory
  6. Determine pass/fail: SOH at warranty end >= warranty_soh_threshold
  7. Calculate safety margin: `(predicted_SOH - threshold) / threshold × 100%`
  8. Risk assessment: margin > 20% = "low risk", 10-20% = "moderate", < 10% = "high risk"
- Return DualFormatResult with:
  - JSON: pass_fail, predicted_soh_at_warranty_end, safety_margin_percent, risk_level, estimated_years_to_eol, warranty_years, warranty_km, warranty_soh_threshold
  - Markdown: clear pass/fail badge, risk level, recommendation

### 2. Add MCP tool in `mcp_server.py`
- Expose `warranty_analysis` following existing patterns

### 3. Add tests
- Test warranty_analysis returns valid result
- Test pass scenario (good cell, mild usage)
- Test fail scenario (aggressive usage, high temperature)
- Test edge case: warranty_years = 0

### 4. Write clean, minimal code
- Do not over-engineer
- Format the Markdown output to be clear and actionable for an EV engineer

## OUTPUT
- Working code: warranty_analysis in agent_api.py, MCP tool in mcp_server.py, tests passing
- A report in `/docs/reports/B2_warranty_analysis.md` including:
  - What was done
  - Key decisions (risk thresholds, interpolation method)
  - Issues encountered
  - Next improvements

## EDUCATION
In the report, briefly explain:
- How EV battery warranties work in the industry (years, km, SOH thresholds)
- Why warranty analysis matters for cell selection and BMS design
- How temperature and usage patterns affect warranty margins
- Safety margin concept: why you need margin above the threshold
