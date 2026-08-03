# Démarrage et API Python

## Installation

Depuis la racine du dépôt :

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Construire une simulation

```python
from battery_sim import (
    Cell,
    Environment,
    Model,
    Protocol,
    Simulation,
    SolverConfig,
)
from battery_sim.composition import create_backend

request = Simulation(
    cell=Cell.preset("NMC_CHEN_LGM50"),
    model=Model.SPM,
    protocol=Protocol.cc(current_A=5.0, duration_s=600.0),
    environment=Environment(
        temperature_C=25.0,
        initial_temperature_C=25.0,
        thermal_model="isothermal",
    ),
    solver_config=SolverConfig(initial_soc=1.0),
)

run = request.run(create_backend())
```

Le courant positif représente une décharge. Pour une charge CC simple, utiliser
un courant négatif. Une charge CC-CV se construit avec `Protocol.cccv(...)`.

## Lire le résultat

```python
from battery_sim.core.result import Signal

print(run.metadata.success)
print(run.result.available_signals())
print(run.result.final(Signal.VOLTAGE))
print(run.errors)
print(run.diagnostics)
```

Toujours vérifier `metadata`, `errors` et `diagnostics` avant d’interpréter les
séries temporelles.

## Choisir un modèle

| Besoin | Premier choix |
|---|---|
| tension, courant, SOC, énergie | `Model.SPM` |
| électrolyte | `Model.SPMe` |
| états détaillés par électrode | `Model.DFN` |
| échauffement cellule simple | modèle électrochimique + thermique `lumped` |

Commencer simple, puis augmenter la fidélité uniquement pour obtenir un signal
ou lever une limite identifiée.

## Découvrir les presets

```python
from battery_sim import Cell

print(Cell.list_presets())
cell = Cell.preset("NMC_CHEN_LGM50")
print(cell.metadata)
```

Les métadonnées indiquent la provenance et le jeu de paramètres. Ne pas traiter
un preset synthétique comme une cellule commerciale calibrée.

## API d’investigation

Pour la découverte, la planification et les outils de plus haut niveau :

```python
from battery_sim.interfaces.python.agent_api import AgentAPI

api = AgentAPI()
print(api.get_available_tools())
plan = api.plan_experiment(
    question="Décharge NMC_CHEN_LGM50 à 25 C et observe la tension"
)
print(plan.markdown_text)
```

Les outils marqués `experimental` servent au screening et non à une décision
de calibration ou de sûreté sans validation supplémentaire.
