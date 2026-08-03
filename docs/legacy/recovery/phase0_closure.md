# Clôture de la phase 0

Date : 2026-08-03

## Résultat

La phase 0 est terminée. Le dépôt possède désormais des contraintes exécutables
pour empêcher le retour à une croissance non maîtrisée.

## Preuves

| Exigence | Preuve |
|---|---|
| Branche et checkpoint | `codex/recovery-roadmap`, commit `38f9071` |
| Matrice des responsabilités | `docs/module_matrix.md` |
| Cycle de vie des API | `docs/api_lifecycle.md` et métadonnées des outils |
| Compatibilité supprimable | `docs/compatibility_inventory.md` |
| Règles de dépendance et taille | `docs/architecture_rules.md` |
| PyBaMM verrouillé | `pybamm==25.12.2` dans `pyproject.toml` |
| Protection automatisée | `tests/test_phase0_governance.py` et `tests/test_architecture.py` |

## Ajustements de maturité

`compare_presets`, `sensitivity_analysis` et `check_feasibility` ont été retirés
du parcours `core`. Leur implémentation actuelle reste callable comme
`experimental`, mais leurs hypothèses ne permettent pas encore de soutenir une
décision BMS.

## Dette rendue explicite

Les modules existants de plus de 300 lignes ont un budget gelé. Ils ne peuvent
plus grossir. Un nouveau module est limité à 300 lignes et un déplacement vers
la future arborescence ne transfère pas l'exception : il faut réellement le
découper.

## Vérification

- tests de gouvernance, architecture et API : 59 réussis ;
- suite rapide complète : 440 réussis, 157 tests lents exclus ;
- aucun assouplissement d'une règle existante pour faire passer les tests.

Les tests structuraux ne prouvent pas la validité physique. Ils établissent le
cadre nécessaire pour que la validation de phase 1 soit lisible et traçable.
