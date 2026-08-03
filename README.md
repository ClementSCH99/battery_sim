# battery_sim

`battery_sim` est un assistant interne d’investigation électrochimique construit
sur PyBaMM. Il vise des simulations cellule explicables, reproductibles et
utiles aux décisions de calibration BMS.

Le projet privilégie la chaîne suivante :

> question d’ingénierie → hypothèses explicites → expérience reproductible →
> résultat contrôlé → interprétation avec limites

## État actuel

- Phase 0 : inventaire, gouvernance et reprise Git terminés ;
- Phase 0.5 : architecture `src/` et découpage des responsabilités terminés ;
- prochaine étape : Phase 1, référence électrique NMC ;
- outils pack, véhicule, charge et vieillissement avancé conservés comme
  expérimentaux tant que leur preuve physique n’est pas suffisante.

## Installation

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

PyBaMM est volontairement verrouillé pendant la construction des références
scientifiques.

## Premier calcul

```python
from battery_sim import Cell, Environment, Model, Protocol, Simulation
from battery_sim.composition import create_backend

simulation = Simulation(
    cell=Cell.preset("NMC_CHEN_LGM50"),
    model=Model.SPM,
    protocol=Protocol.cc(current_A=5.0, duration_s=60.0),
    environment=Environment(temperature_C=25.0),
)

run = simulation.run(create_backend())

print(run.metadata.success)
print(run.result.voltage())
print(run.errors)
```

Une exécution renvoie toujours `SimulationRun`, qui regroupe le résultat, les
métadonnées, les erreurs et les diagnostics.

## Lire la documentation

Commencer par [l’index documentaire](docs/README.md). Le parcours recommandé
est : direction produit, architecture, validité physique, roadmap, puis guides.

## Vérification

```bash
.venv/bin/python -m pytest -m "not slow" -q
.venv/bin/python -m pytest tests/test_architecture.py tests/test_phase0_governance.py -q
.venv/bin/python -m pytest tests/test_reference_cases.py tests/test_physics_validation.py -q
```

Les anciens audits et rapports restent consultables sous `docs/legacy/`, mais
ne décrivent pas nécessairement le code actuel.
