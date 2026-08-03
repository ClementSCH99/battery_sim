# Matrice des modules

> Inventaire historique établi en Phase 0. La migration correspondante est fermée dans `phase05_closure.md`; les chemins ci-dessous décrivent l'état audité avant restructuration.


Cette matrice est l'inventaire de phase 0. Elle décrit la responsabilité actuelle,
le statut et la destination prévue. Les chemins cibles seront créés sous
`src/battery_sim/` pendant la phase de restructuration.

## Noyau physique et contrats

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `core/cell.py` | Identité et propriétés déclarées d'une cellule | core | `core/cell/model.py` |
| `core/cell_presets.py` | Catalogue et provenance des cellules proposées | core à assainir | `core/cell/catalog.py` |
| `core/model.py` | Niveau de modèle électrochimique demandé | core | `core/experiment/model.py` |
| `core/protocol.py` | Étapes et séquences de sollicitation cellule | core | `core/experiment/protocol.py` |
| `core/environment.py` | Conditions thermiques imposées et initiales | core | `core/experiment/environment.py` |
| `core/solver.py` | Intention numérique indépendante du moteur | core | `core/experiment/solver.py` |
| `core/degradation.py` | Configuration explicite des mécanismes de dégradation | core à assainir | `core/experiment/degradation.py` |
| `core/experiment_plan.py` | Plan non exécutable et hypothèses proposées | core | `application/planning/model.py` |
| `core/exceptions.py` | Erreurs de validation du domaine | core | `core/errors.py` |
| `core/reference_cases.py` | Définition des références scientifiques | core | `validation/reference_cases.py` |
| `core/test_trace.py` | Contrat d'une trace d'essai sourcée | core | `validation/test_trace.py` |

Le noyau dépend uniquement de la bibliothèque standard et de ses propres types.
Il ne dépend ni de PyBaMM, ni des interfaces, ni des outils expérimentaux.

## Simulation et résultats

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `core/simulation.py` | Demande complète de simulation | core | `core/simulation/request.py` |
| `core/simulation_backend.py` | Port d'exécution | core à réévaluer | `core/simulation/ports.py` |
| `core/simulation_run.py` | Agrégat de sortie canonique | core | `core/simulation/run.py` |
| `core/simulation_metadata.py` | Provenance et métadonnées d'exécution | core | `core/simulation/metadata.py` |
| `core/simulation_error.py` | Erreurs physiques et numériques structurées | core | `core/simulation/errors.py` |
| `core/convergence_diagnostics.py` | Diagnostic numérique disponible | core | `core/simulation/diagnostics.py` |
| `core/result.py` | Séries et métriques d'une exécution | core | `core/result/model.py` |
| `types/signal.py` | Vocabulaire canonique des signaux | core | `core/result/signals.py` |
| `types/timeseries.py` | Série temporelle avec unité | core | `core/result/timeseries.py` |
| `core/result_analyzer.py` | Analyses historiques hétérogènes | legacy | À découper entre `application/analysis` et `experimental` |
| `core/result_formatter.py` | JSON, Markdown et interprétation mélangés | legacy | `interfaces/presenters/` |
| `core/result_plotting.py` | Tracé optionnel | experimental | `interfaces/plotting/` |

## Cas d'usage applicatifs

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `core/services/execution.py` | Exécution unitaire et batch | core | `application/simulation/execution.py` |
| `core/services/test_comparison.py` | Alignement et résidus modèle–essai | core | `application/validation/comparison.py` |
| `core/services/evidence.py` | Niveau de preuve et prochaines expériences | core | `application/validation/evidence.py` |
| `core/services/comparison.py` | Comparaison de scénarios | experimental | `application/analysis/comparison.py` |
| `core/services/sensitivity.py` | Sensibilité locale | experimental | `application/analysis/sensitivity.py` |
| `core/services/sweep.py` | Balayage canonique de paramètres | experimental | `application/analysis/sweep.py` |
| `core/services/cycling.py` | Extraction et tendance de cycles | experimental | `application/ageing/cycling.py` |
| `core/simulation_session.py` | Journal d'investigation | core à simplifier | `application/session.py` |
| `core/api_schema.py` | Catalogue de paramètres, signaux et presets | legacy volumineux | À découper par contrat propriétaire |

## Adaptateur PyBaMM

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `backend/parameter_mapper.py` | Résolution cellule → jeu de paramètres | core infrastructure | `infrastructure/pybamm/parameters.py` |
| `backend/pybamm_signal.py` | Correspondance signaux → variables PyBaMM | core infrastructure | `infrastructure/pybamm/signals.py` |
| `backend/pybamm_problem_builder.py` | Construction modèle, expérience et solveur | core infrastructure | `infrastructure/pybamm/problem.py` |
| `backend/pybamm_result_extractor.py` | Traduction solution → résultat canonique | core infrastructure | `infrastructure/pybamm/result.py` |
| `backend/pybamm_observability.py` | Métadonnées et diagnostics d'exécution | core infrastructure | `infrastructure/pybamm/observability.py` |
| `backend/pybamm_backend.py` | Orchestration de l'adaptateur | core infrastructure | `infrastructure/pybamm/adapter.py` |
| `backend/base.py` | Ancien contrat backend | legacy | Supprimer si redondant avec le port |

L'adaptateur dépend du noyau. Le noyau ne dépend jamais de l'adaptateur.

## Interfaces

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `interface/simulation_tool.py` | Présentation de l'exécution simple | core interface | `interfaces/python/simulation.py` |
| `interface/test_comparison_tools.py` | Présentation comparaison essai | core interface | `interfaces/python/validation.py` |
| `interface/planning_tools.py` | Présentation plan d'expérience | core interface | `interfaces/python/planning.py` |
| `interface/cell_tools.py` | Découverte cellule et contrôle élémentaire | mixte | À séparer entre découverte core et screening expérimental |
| `interface/discovery_tools.py` | Découverte des capacités et maturités | core interface | `interfaces/python/discovery.py` |
| `interface/session_tools.py` | Présentation de session | core interface | `interfaces/python/session.py` |
| `interface/investigation_tools.py` | Comparaison et sensibilité | experimental | `experimental/interfaces/analysis.py` |
| `interface/degradation_tools.py` | Vieillissement et garantie | experimental | `experimental/interfaces/ageing.py` |
| `interface/charging_tools.py` | Criblage de charge | experimental | `experimental/interfaces/charging.py` |
| `interface/operating_tools.py` | Fenêtre et derating | experimental | `experimental/interfaces/limits.py` |
| `interface/vehicle_tools.py` | Pack, sélection et autonomie | experimental hors périmètre | `experimental/interfaces/system.py` |
| `interface/question_interpreter.py` | Extraction conservatrice d'une question | experimental | `interfaces/python/question.py` |
| `mcp_server.py` | Adaptation MCP et sérialisation de frontière | experimental interface | `interfaces/mcp/server.py` |

## Algorithmes expérimentaux

| Modules actuels | Responsabilité unique | Statut | Destination cible |
|---|---|---|---|
| `core/charging_screen.py` | Criblage de courant CC-CV | experimental | `experimental/charging/screen.py` |
| `core/charging_strategies.py` | Protocoles et comparaison de charge | experimental | `experimental/charging/strategies.py` |
| `core/operating_window.py` | Grille de réponse aux impulsions | experimental | `experimental/limits/window.py` |
| `core/pack.py` | Topologie pack nominale | experimental pertinent | `experimental/pack/topology.py` |
| `core/cell_selection.py` | Score de sélection à hypothèses arbitraires | experimental | `experimental/system/selection.py` |
| `core/drive_cycles.py` | Profils système synthétiques | experimental hors périmètre | `experimental/system/profiles.py` |

## Compatibilité à supprimer

| Modules actuels | Statut | Destination |
|---|---|---|
| `core/application_services.py` | legacy | Suppression après migration des imports |
| `core/investigation_tools.py` | legacy mixte | Extraction des quelques contrats utiles, puis suppression |
| `core/parameter_sweep.py` | legacy | Suppression après déplacement des contrats |
| `core/agent_api.py` | legacy | Remplacement par composition hors du noyau |
| `interface/agent_api.py` | legacy | Remplacement par l'API Python publique |

## Flux canonique actuel

```text
mcp_server
  → interface.agent_api
  → core.agent_api (legacy)
  → interface handler
  → core.services
  → core.simulation
  → core.simulation_backend
  → backend.pybamm_backend
  → core.simulation_run
```

## Flux canonique cible

```text
interfaces.python ou interfaces.mcp
  → application
  → core
  → infrastructure.pybamm (implémentation d'un port)
  → core.simulation.SimulationRun
```
