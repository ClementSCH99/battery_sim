# Architecture de battery_sim

Ce document décrit **le code actuel**. Les rapports sous `docs/audit/archive/` sont un historique et peuvent décrire un état antérieur.

## Flux principal

```text
Client MCP
   │
   ▼
mcp_server.py                validation et sérialisation de frontière
   │
   ▼
interface/agent_api.py       point d'entrée public de la façade agent
   │
   ├── interface/cell_tools.py
   ├── interface/simulation_tool.py
   ├── interface/investigation_tools.py
   ├── interface/degradation_tools.py
   ├── interface/vehicle_tools.py
   ├── interface/charging_tools.py
   ├── interface/operating_tools.py
   ├── interface/session_tools.py
   ├── interface/planning_tools.py
   │
   ▼
core/agent_api.py            façade historique, en cours d'amincissement
   │
   ├── core/services/
   │       exécution, batch, sweep, comparaison, sensibilité, cycling
   │
   ▼
core/simulation.py           demande de simulation validée
   │
   ▼
core/simulation_backend.py   port abstrait
   │
   ▼
backend/pybamm_backend.py    orchestrateur de l'adaptateur PyBaMM
   ├── pybamm_problem_builder.py
   ├── pybamm_result_extractor.py
   └── pybamm_observability.py
   │
   ▼
core/simulation_run.py       résultat canonique
```

## Couches et responsabilités

| Zone | Responsabilité | Ne doit pas faire |
|---|---|---|
| `core/cell.py`, `model.py`, `protocol.py`, `environment.py`, `solver.py`, `degradation.py` | Exprimer et valider l'intention physique | Importer PyBaMM ou choisir un backend concret |
| `core/simulation.py` | Regrouper une demande complète et la faire exécuter via un port | Construire des objets PyBaMM |
| `core/simulation_backend.py` | Définir ce que tout moteur de simulation doit fournir | Connaître les détails d'un moteur |
| `core/services/` | Orchestrer exécution, batch, sweep, comparaison, sensibilité et analyse de cycles | Formater une réponse MCP |
| `backend/` | Traduire le domaine vers PyBaMM et extraire les signaux | Définir une politique produit ou un contrat concurrent |
| `core/result.py` et `simulation_run.py` | Porter les signaux et l'état complet d'une exécution | Dépendre d'une solution PyBaMM brute |
| `interface/` | Présenter les cas d'usage, formater les réponses et gérer leur trace de session | Choisir directement un backend concret dans les handlers |
| `core/agent_api.py` | Façade historique compatible pendant la migration | Recevoir de nouveaux algorithmes ou de nouveaux cas d'usage |
| `mcp_server.py` | Déclarer les outils, valider les entrées et sérialiser les sorties | Recalculer les résultats métier |

## Contrats fondamentaux

### Entrée

`Simulation` contient :

- `Cell` : caractéristiques nominales et référence de paramétrage ;
- `Model` : niveau de fidélité électrochimique ;
- `Protocol` : séquence d'étapes imposées ;
- `Environment` : température ambiante, température cellule initiale optionnellement distincte et configuration thermique ;
- `SolverConfig` : intention numérique ;
- `DegradationConfig` optionnelle.

### Sortie

Toute exécution publique doit retourner `SimulationRun` :

- `result` : séries temporelles et grandeurs dérivées ;
- `metadata` : configuration, durée et statut ;
- `errors` : problèmes physiques ou numériques structurés ;
- `diagnostics` : informations de convergence disponibles.

`Result` seul n'est pas une preuve de succès et ne doit pas remplacer `SimulationRun` dans une API d'exécution.
Chaque `SimulationMetadata` porte un `simulation_id` unique pour corréler
réponse MCP, session et diagnostic.

## Carte des modules

### Domaine stable

- `cell.py`, `cell_presets.py` : cellule et presets ;
- `pack.py` : topologie série/parallèle nominale et hypothèses de packaging ;
- `protocol.py`, `drive_cycles.py`, `charging_strategies.py` : sollicitations ;
- `environment.py`, `model.py`, `solver.py`, `degradation.py` : configuration ;
- `exceptions.py` : erreurs de validation ;
- `types/signal.py`, `types/timeseries.py` : vocabulaire de résultats.

### Exécution et observabilité

- `simulation.py`, `simulation_backend.py` : demande et port ;
- `backend/parameter_mapper.py` : correspondance cellule → paramètres PyBaMM ;
- `backend/pybamm_signal.py` : correspondance signaux internes → variables PyBaMM ;
- `backend/pybamm_problem_builder.py` : traduction protocole, modèle, expérience, solveur et paramètres natifs ;
- `backend/pybamm_result_extractor.py` : extraction des signaux primaires, grandeurs dérivées et métriques par cycle ;
- `backend/pybamm_observability.py` : métadonnées, erreurs physiques et diagnostics d'une exécution ;
- `backend/pybamm_backend.py` : petit orchestrateur qui relie construction, résolution, extraction et observabilité ;
- `simulation_metadata.py`, `simulation_error.py`, `convergence_diagnostics.py`, `simulation_run.py` : preuve d'exécution.
- `reference_cases.py` : expériences LFP/NMC reproductibles et invariants scientifiques.
- `experiment_plan.py` : contrat non exécutable d'une expérience à faire valider.

### Analyse et interface

- `services/execution.py` : exécution unitaire et batch ;
- `services/sweep.py` : variation canonique des paramètres ;
- `services/comparison.py`, `sensitivity.py`, `cycling.py` : analyses ciblées ;
- `services/test_comparison.py` : alignement temporel et résidus simulation–essai sans extrapolation ;
- `services/evidence.py` : force de preuve, critère local et prochaines expériences sans déclaration automatique de validation ;
- `application_services.py` : imports de compatibilité temporaires, sans logique ;
- `charging_screen.py`, `operating_window.py`, `cell_selection.py` : algorithmes expérimentaux séparés par problème ;
- `investigation_tools.py` : contraintes, configuration d'analyse et imports de compatibilité historiques ;
- `parameter_sweep.py` : façade typée de compatibilité au-dessus du service canonique de sweep ;
- `result_analyzer.py` : helpers d'analyse de résultats encore à rationaliser ;
- `result_formatter.py`, `result_plotting.py`, `simulation_session.py` : présentation et session ;
- `api_schema.py` : catalogue du domaine ;
- `interface/agent_api.py` : import public utilisé par MCP ;
- `interface/cell_tools.py`, `interface/simulation_tool.py` : catalogue, faisabilité et simulation unitaire ;
- `interface/discovery_tools.py` : catalogue dérivé des méthodes exécutables et parcours core-first ;
- `interface/investigation_tools.py` : comparaison, hypothèses EV explicitement séparées et sensibilité locale ;
- `interface/degradation_tools.py` : extrapolation de vieillissement et screening garantie expérimentaux ;
- `interface/vehicle_tools.py` : screening cellule-pack-véhicule et hypothèses système explicites ;
- `interface/charging_tools.py` : criblage CC-CV et comparaison de stratégies avec métriques absentes explicites ;
- `interface/operating_tools.py` : présentation des impulsions SOC-température-C-rate et échantillons candidats de derating ;
- `interface/session_tools.py` : restitution de la trace d'investigation ;
- `interface/planning_tools.py` : proposition explicite du modèle, protocole,
  signaux, hypothèses et entrées manquantes avant exécution ;
- `interface/question_interpreter.py` : extraction bilingue conservatrice avec
  fragments sources ; aucune valeur physique n'est déduite d'un qualificatif ;
- `interface/test_comparison_tools.py` : construction d'une décharge CC,
  provenance d'essai, comparaison et journalisation de session ;
- `test_trace.py` : contrat validé des séries mesurées et convention de signe canonique ;
- `core/agent_api.py` : implémentation historique transitoire ;
- `mcp_server.py` : adaptateur MCP.

## Dette architecturale actuelle

1. `AgentAPI` reste une façade historique de près de 700 lignes, mais découverte,
   description et cas d'usage sont délégués à des handlers ciblés. Sa taille est
   maintenant plafonnée par un test ; la prochaine réduction concerne les
   déclarations de compatibilité et les helpers statiques restants.
2. `api_schema.py` reste volumineux, mais il ne contient plus de catalogue manuel d'outils : il décrit uniquement paramètres, signaux et presets.
3. `parameter_sweep.py` conserve volontairement les objets `SweepResult` et `ParameterOverride`, mais toute l'exécution est déléguée au service canonique.
4. `ChargingOptimizer`, `OperatingWindowAnalyzer` et `CellSelectionScorer` ont maintenant leurs modules ciblés ; `investigation_tools.py` réexporte encore leurs anciens chemins pour compatibilité.
5. Les helpers privés historiques de `PyBaMMBackend` restent comme délégations de compatibilité ; ils pourront disparaître lors d'une rupture de version contrôlée.
6. Les outils orientés charge et limites opératoires exposent maintenant leur preuve limitée, mais leurs anciens analyseurs de compatibilité dans `investigation_tools.py` et `charging_strategies.py` restent à simplifier.
7. Les packages `core/` et `types/` sont encore partiellement plats, ce qui masque certaines couches réelles.

## Règles protégées par les tests

- pas d'import d'infrastructure depuis le domaine, sauf façade transitoire explicitement tolérée ;
- `SimulationRun` est le contrat de sortie de toutes les exécutions ;
- le vocabulaire `Signal` et le catalogue de signaux restent alignés ;
- le catalogue des outils de `AgentAPI` est dérivé des méthodes `@agent_tool` ;
- le backend de `AgentAPI` peut être injecté.

Ces règles sont des garde-fous. Elles ne remplacent pas la validation physique des résultats.
