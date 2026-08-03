# Maturité des capacités agent

La présence d'un outil dans le code ne garantit pas qu'il soit prêt à soutenir une décision d'ingénierie. `AgentAPI.get_available_tools()` expose donc un statut de maturité dérivé du décorateur de chaque méthode.

## Core

Ces capacités forment le premier produit à stabiliser :

| Outil | Rôle |
|---|---|
| `describe_api` | Découvrir le système et son vocabulaire |
| `list_presets` | Examiner les points de départ disponibles |
| `plan_experiment` | Construire une proposition révisable avant exécution |
| `compare_test_data` | Quantifier les résidus d'une décharge CC simulée face à un essai sourcé |
| `run_simulation` | Exécuter une expérience cellule |
| `compare_presets` | Comparer des scénarios homogènes |
| `sensitivity_analysis` | Mesurer l'effet d'une variation simple |
| `check_feasibility` | Contrôler des contraintes élémentaires avant exécution |
| `get_session_summary` | Conserver la trace de l'investigation |

`core` signifie « dans le périmètre prioritaire de stabilisation », pas « validé pour homologation ».

`describe_api` publie le profil par défaut `core_first`, un parcours recommandé,
et ordonne le catalogue avec les outils `core` avant les outils expérimentaux.
Ces derniers restent appelables pour ne pas casser les clients existants.

Limites actuellement rendues explicites :

- `compare_presets` sépare les métriques issues de `SimulationRun` des hypothèses illustratives de masse, volume et coût ; ses coordonnées de Ragone sont dérivées des presets et ne constituent pas un essai de puissance pulsée simulé ;
- `sensitivity_analysis` est une étude locale *one-at-a-time* sur `temperature_C` ou `nominal_capacity_Ah`, avec `peak_power_W` comme réponse ; ce n'est pas une analyse de sensibilité globale ;
- `check_feasibility` est une pré-validation de contraintes élémentaires, pas une preuve de sûreté ou de qualification cellule.
- `compare_test_data` ne calibre aucun paramètre, n'extrapole pas au-delà du
  domaine temporel commun et considère encore l'alignement de l'état initial
  comme une hypothèse non vérifiée.

## Experimental

Ces capacités existent et leurs tests logiciels peuvent être verts, mais leurs hypothèses et leur domaine de validité doivent être revus avant de présenter leurs sorties comme des conclusions d'ingénierie :

- `predict_lifetime` ;
- `warranty_analysis` ;
- `optimize_charging` ;
- `operating_window` ;
- `derating_curves` ;
- `estimate_range` ;
- `compare_charging_strategies` ;
- `pack_sizing` ;
- `cell_selection_wizard`.

`predict_lifetime` et `warranty_analysis` exposent désormais leur preuve et leurs limites :

- seules les capacités de décharge par cycle sont observées dans `SimulationRun` ;
- l'EOL est une extrapolation linéaire ordinaire d'une fenêtre courte ;
- une absence de pente décroissante produit `N/A`, jamais une durée arbitraire d'un million de cycles ;
- le screening garantie s'arrête à la première limite atteinte, temps ou kilométrage ;
- aucune conclusion de garantie n'est recevable sans corrélation sur des données d'essais cellule représentatives.

Les outils système exposent également leurs hypothèses :

- `pack_sizing` calcule une topologie nominale idéale ; les surcharges de masse et volume de 20 % et 30 % sont des hypothèses, pas un design mécanique ou thermique ;
- `cell_selection_wizard` convertit l'autonomie en énergie avec 0,18 kWh/km, 90 % d'énergie utilisable et 100 cycles équivalents par an ; les données absentes restent `N/A` et empêchent de déclarer les contraintes satisfaites ;
- `estimate_range` intègre directement une trace de puissance synthétique au niveau pack. Il n'appelle plus PyBaMM et ne modélise ni température, ni auxiliaires, ni pertes pack ; les profils inclus ne sont pas des cycles réglementaires vitesse-temps.

Les outils de recharge et de limites opératoires ont aussi été ramenés à leur preuve réelle :

- `optimize_charging` est désormais un criblage de durée d'une charge CC-CV unique depuis 20 % de SOC. Il filtre la limite de C-rate du preset et n'invente plus de perte de capacité, d'efficacité ou de risque de placage lithium ; « optimal » signifie seulement « le plus rapide parmi les points simulés admissibles » ;
- `compare_charging_strategies` conserve le statut et l'erreur de chaque simulation, exclut les échecs des classements et publie `null` lorsque le signal requis n'existe pas ;
- `operating_window` initialise réellement chaque SOC demandé et classe comme `avoid` toute simulation échouée ou dépourvue de tension exploitable. Ses classes sont des étiquettes de criblage sur impulsion, pas des états de sûreté certifiés ;
- `derating_curves` produit des échantillons candidats au niveau cellule, avec une puissance en watts. Le modèle est isotherme et les résultats ne sont pas des tables BMS de production.

## Promotion d'un outil

Un outil expérimental passe en `core` seulement si les éléments suivants sont disponibles :

1. décision d'ingénierie et utilisateur visés ;
2. entrées, unités et conventions explicites ;
3. hypothèses et domaine de validité ;
4. provenance de chaque donnée ou paramètre ;
5. cas de référence numérique ;
6. erreurs et limites visibles dans la sortie ;
7. tests logiciels et revue physique.

Le serveur MCP conserve actuellement les outils expérimentaux pour compatibilité,
mais chaque réponse JSON expose désormais :

- `tool` : nom stable de l'opération appelée ;
- `maturity` : statut dérivé du décorateur réel de `AgentAPI` ;
- `contract.schema_version` ;
- `contract.domain_of_validity`, dérivé de la preuve ou de la portée du résultat ;
- `contract.assumptions`, qui reprend les hypothèses déclarées par le résultat et
  ajoute le cadre minimal propre à la maturité de l'outil ;
- pour les erreurs, `error_code`, `retryable` et le même contrat de maturité.

Les simulations unitaires exposent aussi un `simulation_id` unique qui relie la
réponse agent aux métadonnées de l'exécution.
