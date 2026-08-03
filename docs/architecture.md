# Architecture de battery_sim

Le code de production est installé uniquement depuis `src/battery_sim`.
L'arborescence rend visibles la maturité et la responsabilité de chaque module.

## Flux principal

```text
Python ou MCP
      │
      ▼
interfaces ──► application ──► core
      │               │          ▲
      │               └──────────┤
      ▼                          │
composition ──► infrastructure/pybamm
```

- `core/` porte uniquement le langage stable : cellule, expérience, résultat et
  simulation ;
- `application/` orchestre les exécutions, analyses, preuves et sessions ;
- `validation/` contient les cas de référence et traces mesurées ;
- `infrastructure/pybamm/` adapte les contrats du noyau au moteur PyBaMM ;
- `interfaces/python/` expose les handlers et l'API introspectable ;
- `interfaces/presenters/` transforme les résultats en JSON ou Markdown ;
- `interfaces/mcp/` valide et sérialise la frontière MCP ;
- `experimental/` isole les outils de charge, limites, pack et système dont la
  validité n'est pas encore suffisante pour le parcours principal.

La dépendance concrète PyBaMM est construite dans `battery_sim/composition.py`.
Le noyau ne choisit jamais son infrastructure.

## Domaine stable

```text
core/
├── cell/          spécification, catalogue et presets par chimie
├── experiment/    modèle, protocole, environnement, solveur, vieillissement
├── result/        signaux, séries temporelles et métriques
└── simulation/    demande, port, résultat d'exécution et diagnostics
```

Toute exécution publique produit un `SimulationRun`. Son `result` ne suffit pas
à déclarer une simulation réussie : les métadonnées, erreurs et diagnostics
font partie du contrat.

## Interfaces

L'API Python publique courte est disponible directement depuis
`battery_sim` :

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

Le registre d'outils conserve les statuts `core`, `experimental` et `legacy`.
MCP ne recalcule aucune physique : il applique validation, contrat de réponse
et sérialisation aux mêmes cas d'usage Python.

## Contraintes exécutables

- aucun module de production ne dépasse 300 lignes ;
- aucune exception de taille n'est conservée ;
- le noyau n'importe ni interfaces, ni infrastructure, ni expérimental ;
- les signaux du schéma restent alignés avec le vocabulaire d'exécution ;
- PyBaMM reste verrouillé pendant la validation des références ;
- les tests d'architecture et de gouvernance contrôlent ces contraintes.

Les outils sous `experimental/` restent accessibles pour exploration, mais ne
constituent pas une preuve de calibration, de sûreté ou de qualification.
