# Architecture cible sous `src/`

Cette architecture doit être atteinte avant la phase 1. Elle privilégie la
lecture, la responsabilité locale et une direction de dépendances simple.

## Arborescence

```text
src/
└── battery_sim/
    ├── __init__.py
    ├── core/
    │   ├── cell/
    │   │   ├── model.py
    │   │   └── catalog.py
    │   ├── experiment/
    │   │   ├── model.py
    │   │   ├── protocol.py
    │   │   ├── environment.py
    │   │   ├── solver.py
    │   │   └── degradation.py
    │   ├── result/
    │   │   ├── model.py
    │   │   ├── signals.py
    │   │   └── timeseries.py
    │   └── simulation/
    │       ├── request.py
    │       ├── run.py
    │       ├── metadata.py
    │       ├── errors.py
    │       ├── diagnostics.py
    │       └── ports.py
    ├── application/
    │   ├── simulation/
    │   ├── validation/
    │   ├── analysis/
    │   └── session.py
    ├── validation/
    │   ├── reference_cases.py
    │   └── test_trace.py
    ├── infrastructure/
    │   └── pybamm/
    │       ├── adapter.py
    │       ├── parameters.py
    │       ├── problem.py
    │       ├── result.py
    │       ├── signals.py
    │       └── observability.py
    ├── interfaces/
    │   ├── python/
    │   ├── presenters/
    │   └── mcp/
    └── experimental/
        ├── ageing/
        ├── charging/
        ├── limits/
        ├── pack/
        └── system/
```

## Pourquoi ces frontières

### `core`

Contient le langage stable du produit : cellule, expérience, résultat et
simulation. Il n'importe aucune technologie externe et aucune présentation.

### `application`

Décrit ce que le produit fait : exécuter, comparer, évaluer une preuve ou
orchestrer une étude. Il dépend du `core` et de ports, jamais de PyBaMM concret.

### `validation`

Porte les références scientifiques et traces mesurées. Ces éléments sont assez
importants pour ne pas être cachés parmi les outils ou la présentation.

### `infrastructure.pybamm`

Traduit les contrats du noyau vers PyBaMM. PyBaMM reste le seul moteur ; cette
frontière existe pour isoler sa représentation et faciliter les tests, pas pour
prétendre supporter plusieurs moteurs.

### `interfaces`

Expose une API Python courte et, plus tard, MCP. Les presenters produisent JSON
ou Markdown sans contaminer le calcul.

### `experimental`

Conserve les fonctions non validées sans les laisser se présenter comme le
noyau. Aucune dépendance du `core` ou de `application` vers `experimental` n'est
autorisée.

## API Python cible

Le fichier `battery_sim/__init__.py` exposera seulement les contrats usuels :

```python
from battery_sim import (
    Cell,
    DegradationConfig,
    Environment,
    Model,
    Protocol,
    Simulation,
    SimulationRun,
    SolverConfig,
)
```

L'adaptateur concret sera construit par une fonction de composition documentée,
pas sélectionné depuis un objet du noyau.

## Ordre de migration

1. créer le layout `src/` et configurer le packaging ;
2. déplacer les petits types du noyau (`result`, puis `simulation`) ;
3. déplacer cellule et expérience ;
4. déplacer validation et services applicatifs ;
5. déplacer l'adaptateur PyBaMM ;
6. créer l'API Python publique ;
7. déplacer les interfaces ;
8. isoler les outils expérimentaux ;
9. supprimer les shims sans consommateur réel ;
10. mettre à jour README, tests et MCP.

Chaque étape est un commit séparé et laisse la suite rapide verte.

## Critères de sortie

- le package installé provient uniquement de `src/battery_sim` ;
- aucun package de production ne reste à la racine ;
- les imports publics documentés fonctionnent ;
- aucun nouveau cycle de dépendance ;
- aucune dépendance du noyau vers PyBaMM, interfaces ou expérimental ;
- aucun module supérieur à 300 lignes ;
- les shims historiques sont supprimés ou justifiés par un consommateur réel ;
- suite rapide, architecture et cas physiques de référence réussis.
