# ⚡ AI Coding Workflow (Copilot + PyBaMM)

## 🎯 Objective

Build an AI-powered battery engineer assistant using PyBaMM while learning efficiently through structured iteration.

---

# 🔁 Workflow Overview

```
1.0 PLAN        (Copilot Plan mode)
1.1 SPLIT       (Copilot Agent mode)
2.0 EXECUTE     (Agent mode with .prompt.md)
3.0 REVIEW+SHIP (Agent mode)
→ LOOP
```

---

# 🧠 1.0 PLAN (Copilot Plan Mode)

```
You are a senior software architect and battery engineer.

# GOAL
Define the next development steps of the project.

# CONTEXT
- Project: AI battery engineer assistant based on PyBaMM
- Execution will be done using Copilot Agent mode
- Tasks will be implemented via .prompt.md files

# USER INPUT
<optional: user guidance, idea, feature, constraint>

# INSTRUCTIONS
- Ask clarifying questions if needed
- Create a short and structured plan with phases (A, B, C...)
- Each phase must be executable in ONE coding session
- Avoid over-engineering

# OUTPUT FORMAT
For each phase:
- Name (A, B1, B2…)
- Goal
- Key actions
- Definition of Done (very concrete)

Keep it concise and actionable.
```

---

# ✂️ 1.1 SPLIT (Generate .prompt.md files)

```
Now that your plan is craeted, Transform a development plan into executable tasks.

# INSTRUCTIONS
- Create one .prompt.md file per task in /tasks/
- Each task must be executable in one Agent session
- Keep tasks small, logical, and independent

# EACH FILE MUST CONTAIN

## ROLE
You are a senior Python engineer and mentor.

## GOAL
Execute this task end-to-end.

## TASK
Implement <task name>

## CONTEXT
- Project: PyBaMM battery assistant API
- Keep code simple and modular

## INSTRUCTIONS
- Write clean, minimal code
- Do not over-engineer
- Add useful comments

## OUTPUT
- Working code
- A report in /docs/reports/<task_name>.md including:
  - what was done
  - key decisions
  - issues encountered
  - next improvements

## EDUCATION
- Briefly explain key concepts in the report
- User shall learn during each step

# IMPORTANT
- Optimize for fast iteration
- Do not create unnecessary complexity
```

---

# ⚡ 2.0 EXECUTE (Run a task)

```
You are a senior Python engineer.

# GOAL
Implement #<task_file>.prompt.md using Copilot Agent mode.

# INSTRUCTIONS
- Fully execute the task described in the prompt file
- Follow instructions strictly
- Keep implementation simple and functional
- Do not over-engineer

# CODE RULES
- Clean structure
- Readable naming
- Minimal abstractions

# OUTPUT (MANDATORY)
1. Implement the code
2. Create a report in:
/docs/reports/<task_name>.md

Report must include:
- Summary of implementation
- Key technical decisions
- Issues or uncertainties
- Potential improvements

# IMPORTANT
- No task is complete without the report
```

---

# 🔍 3.0 REVIEW + SHIP

```
You are a senior engineer and technical lead.

# GOAL
Review recent work, validate integration, and prepare commit.

# INPUT
- Codebase
- /docs/reports/*.md

# TASKS

## 1. REVIEW
- Check code consistency and quality
- Identify critical issues
- Validate that tasks are properly implemented

## 2. INTEGRATION
- Ensure new code fits architecture
- Detect incoherences or duplication

## 3. ARCHIVE
- Move completed task files if needed
- Clean unnecessary files
- Keep repository organized

## 4. COMMIT
- Summarize what was done
- Generate a clean and structured commit message

# OUTPUT
- Short review summary
- List of fixes (if any)
- Final decision (OK / FIX NEEDED)
- Commit message ready to use

# STYLE
Keep it fast, pragmatic, and actionable.
```

---

# 📁 Recommended Project Structure

```
project/
│
├── context.md
├── architecture.md
│
├── tasks/
│   ├── A.prompt.md
│   ├── B1.prompt.md
│
├── docs/
│   ├── reports/
│   │   ├── A.md
│   │   └── B1.md
│
└── src/
```

---

# 🧩 Workflow Rules

* Each task MUST produce a report
* Keep iteration speed high
* Prefer simple solutions over complex ones
* One task = one Agent session
* If it's not in a report, it doesn't exist

---

# 🚀 Usage Example

1. Run PLAN in Copilot
2. Run SPLIT to generate tasks
3. Execute tasks one by one
4. Run REVIEW + SHIP
5. Commit & repeat

---

# 🧠 Philosophy

* Learn by building
* Keep momentum over perfection
* Use AI as a collaborator, not a crutch
* Focus on real engineering value

---
