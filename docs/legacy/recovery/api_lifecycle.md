# Cycle de vie des API

Ce catalogue décrit l'état accepté au terme de la phase 0. « Core » désigne le
parcours prioritaire, pas une homologation du modèle.

## Outils agent

| Outil | Statut | Justification |
|---|---|---|
| `describe_api` | core | Découverte et limites |
| `list_presets` | core | Découverte ; la provenance doit rester visible |
| `plan_experiment` | core | Revue des hypothèses avant calcul |
| `run_simulation` | core | Exécution canonique |
| `compare_test_data` | core | Comparaison sourcée sans extrapolation |
| `get_session_summary` | core | Traçabilité |
| `compare_presets` | experimental | Mélange encore simulation et métriques EV supposées |
| `sensitivity_analysis` | experimental | Étude locale et réponses encore trop limitées |
| `check_feasibility` | experimental | Contraintes élémentaires, pas une preuve physique |
| `predict_lifetime` | experimental | Extrapolation d'une fenêtre courte |
| `warranty_analysis` | experimental | Dépend d'une prédiction de vieillissement non validée |
| `optimize_charging` | experimental | Criblage de durée, pas optimisation multiobjectif |
| `compare_charging_strategies` | experimental | Preuve dépendante des signaux disponibles |
| `operating_window` | experimental | Classification de screening non validée |
| `derating_curves` | experimental | Pas une calibration BMS qualifiée |
| `pack_sizing` | experimental | Topologie nominale idéale |
| `cell_selection_wizard` | experimental | Critères et hypothèses système illustratifs |
| `estimate_range` | experimental | Véhicule hors périmètre |

## API Python du noyau

Les contrats à préserver conceptuellement pendant la restructuration sont :

- `Cell` et un futur identifiant explicite de paramétrage ;
- `Protocol` et ses étapes ;
- `Environment`, `Model`, `SolverConfig`, `DegradationConfig` ;
- `Simulation` comme demande canonique ;
- `SimulationBackend` comme port d'exécution tant que sa valeur est démontrée ;
- `SimulationRun` comme sortie canonique ;
- `Result`, `Signal` et `TimeSeries` comme vocabulaire de résultat ;
- les services d'exécution, comparaison essai et preuve.

Les chemins d'import actuels ne sont pas garantis : la phase de restructuration
créera une API publique courte depuis `battery_sim`.

## Critère de promotion

Une API expérimentale devient `core` seulement après :

1. identification de la décision BMS visée ;
2. provenance des données et paramètres ;
3. domaine de validité ;
4. séparation simulé, dérivé, supposé et mesuré ;
5. erreur structurée ;
6. cas de référence ou comparaison essai ;
7. revue physique.
