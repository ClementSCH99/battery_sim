# Investigation boîte noire du serveur MCP `battery_sim`

Date de l’investigation : 4 août 2026
Méthode : appels au serveur MCP uniquement, sans analyse du code, des tests ou de la documentation du dépôt
Objectif : fournir une base factuelle pour le refactoring du contrat MCP et des outils exposés

## Synthèse technique

Le serveur expose 18 outils, 15 presets et 11 libellés de chimie. Les réponses sont généralement riches en provenance, hypothèses et limites. La validation des entrées est souvent précise, et `compare_test_data` constitue le meilleur exemple de contrat exploitable : alignement des traces, conventions de signe, résidus, couverture, seuil d’acceptation et limites de validation sont explicités.

La fiabilité globale est toutefois limitée par quatre problèmes structurants :

1. **Il n’existe pas de modèle d’état ou d’erreur uniforme.** Un même échec peut être représenté par `error: true`, par `error: "<texte>"`, par `status: "failed"` avec `success: true`, ou par une réponse nominale vide. Tous ces cas sont remontés avec un appel MCP considéré comme réussi au niveau transport.
2. **Le catalogue, la simulation et les outils de décision ne partagent pas la même définition d’un preset utilisable.** Trois presets publiés ne sont pas simulables. Plusieurs presets redimensionnés produisent une énergie sans rapport avec leur capacité nominale. Ils restent néanmoins utilisés dans le dimensionnement et le classement de cellules.
3. **Le plan d’expérience n’est pas exécutable sans perte d’information.** Il peut déclarer un plan DFN prêt à exécuter, alors que `run_simulation` impose un modèle single-particle et ne retourne pas les signaux demandés.
4. **Les outils de vieillissement et de garantie produisent des conclusions catégoriques à partir d’extrapolations numériquement non informatives.** Des projections de plusieurs milliers de milliards d’années et des `R²` négatifs conduisent malgré tout à une garantie déclarée « Low Risk ».

En l’état observé, le serveur est utile pour l’exploration et le prototypage, mais ses réponses ne doivent pas alimenter automatiquement une décision d’ingénierie sans validation supplémentaire côté client.

## Périmètre et protocole d’investigation

### Couverture

- 18 outils MCP exercés au moins une fois.
- 15 presets testés en décharge à courant constant.
- 12 simulations de presets ayant retourné un résultat exploitable.
- 3 presets du catalogue ayant échoué avant simulation.
- 6 formulations dédiées au parsing du C-rate et de la température.
- 30 probes de validation ou de limites, complétés par des tests de déterminisme et de cohérence inter-outils.
- 45 investigations retenues par `get_session_summary` à la fin du protocole ; plusieurs appels valides ne sont pas comptabilisés par cet outil.

### Scénario de référence pour les presets

- Courant : capacité nominale du preset en ampères, soit 1C.
- Durée demandée : 3 600 s.
- Température ambiante : 25 °C.
- Les énergies nominales de contrôle sont calculées par `capacité_Ah × tension_nominale_V`.

### Données de comparaison

Les traces envoyées à `compare_test_data` étaient des fixtures synthétiques créées uniquement pour tester le contrat :

- temps : 0, 600, 1 200 et 1 800 s ;
- tension : 4,08, 3,95, 3,82 et 3,68 V ;
- courant : 5 A ;
- aucune conclusion de validation physique n’est tirée de ces fixtures.

### Échelle de gravité

- **Critique** : peut produire une conclusion de succès ou de décision incorrecte.
- **Élevée** : peut modifier matériellement l’interprétation ou casser un client MCP.
- **Moyenne** : contrat ambigu, observabilité incomplète ou outil peu exploitable.
- **Faible** : incohérence ergonomique ou comportement acceptable mais insuffisamment explicite.

## Cartographie des outils

| Outil | Maturité annoncée | Comportement observé | Risque principal |
|---|---|---|---|
| `describe_api` | core | Décrit 18 outils et un workflow `core_first` | Certains paramètres décrits ne correspondent pas aux arguments appelables |
| `list_presets` | core | Retourne 15 presets ; filtre exact et sensible à la casse | Le catalogue ne distingue pas clairement les presets simulables |
| `plan_experiment` | core | Produit un plan traçable et des valeurs par défaut | Parsing C-rate erroné et plan non représentable par l’exécuteur |
| `run_simulation` | core | Simulation PyBaMM déterministe sur les métriques | `success`, `status` et erreurs critiques peuvent se contredire |
| `compare_test_data` | core | Contrat riche et prudent, résidus et couverture explicites | Convention de signe de `applied_current_A` différente de celle des mesures |
| `get_session_summary` | core | Rapport lisible des investigations enregistrées | Journal sélectif et non exhaustif |
| `compare_presets` | experimental | Agrège simulation et heuristiques EV | Classement inversé des erreurs et gestion ambiguë des doublons |
| `sensitivity_analysis` | experimental | Sensibilité locale sur `peak_power_W` | Paramètres très limités et capacité nominale sans effet observé |
| `check_feasibility` | experimental | Contrôle de domaine avec avertissements | « feasible » signifie seulement « dans le domaine accepté » |
| `predict_lifetime` | experimental | Extrapolation linéaire d’une courte trajectoire | Projection astronomique malgré pente quasi nulle et mauvais diagnostic |
| `pack_sizing` | experimental | Arithmétique de pack cohérente et hypothèses visibles | Utilise des valeurs catalogue indépendamment de la simulabilité |
| `cell_selection_wizard` | experimental | Classe 15 presets et applique des contraintes | Peut donner 100/100 avec dimensions manquantes et classer des presets non simulables |
| `warranty_analysis` | experimental | Traduit une projection de vieillissement en décision de garantie | Conclusion catégorique à partir d’une extrapolation non informative |
| `optimize_charging` | experimental | Balayage CC-CV de durée de charge | Le mot « optimal » ne couvre ni vieillissement, ni rendement, ni plating |
| `operating_window` | experimental | 27 pulses sur SOC, température et C-rate | Zones largement déterminées par des règles de température |
| `derating_curves` | experimental | Dérive des points à partir de `operating_window` | La « courbe » température ne contient qu’un point dans le test coarse |
| `estimate_range` | experimental | Intègre un profil de puissance synthétique | Label WLTP facilement surinterprétable ; température sans effet |
| `compare_charging_strategies` | experimental | Compare cinq stratégies et exclut les échecs | Toutes les stratégies échouent ; plusieurs protocoles donnent des sorties identiques |

## Constatations prioritaires

### MCP-01 — Le modèle d’erreur est fragmenté

**Gravité : critique — Confiance : élevée**

Quatre formes d’échec ont été observées :

1. Validation structurée :

   ```json
   {
     "error": true,
     "error_type": "ValidationError",
     "error_code": "validation_error",
     "message": "duration_s must be > 0"
   }
   ```

2. Erreur métier textuelle :

   ```json
   {
     "type": "range_estimation_error",
     "error": "ValueError: requested peak profile ... exceeds ... limit"
   }
   ```

3. Résultat contradictoire :

   ```json
   {
     "metrics": {
       "success": true,
       "status": "failed",
       "critical_errors": 1
     }
   }
   ```

4. Échec silencieux :

   ```json
   {
     "type": "charging_strategy_comparison",
     "strategies": [],
     "recommended_strategy": null
   }
   ```

Dans tous les cas de validation testés, la couche MCP a retourné `isError=false`. Un client ne peut donc pas s’appuyer sur le statut transport et doit implémenter plusieurs branches spécifiques à chaque outil.

**Impact refactoring :** définir une enveloppe unique avec au minimum `ok`, `status`, `error.code`, `error.message`, `data`, `warnings` et `diagnostics`. Les erreurs de validation et d’exécution devraient aussi être reflétées au niveau MCP lorsque le protocole le permet.

### MCP-02 — `success` ne signifie pas que le résultat est valide

**Gravité : critique — Confiance : élevée**

Sept presets ont retourné simultanément :

- `success=true` ;
- `status=failed` ;
- `critical_errors=1`.

Presets concernés :

- `LFP_10AH`
- `LFP_5AH`
- `LFP_HP_20AH`
- `LFP_PRADA_2P3AH`
- `NMC_10AH`
- `NMC_MOHTAT_POUCH`
- `NMC_OKANE_AGING`

Le comportement suggère que `success` représente la résolution numérique alors que `status` représente la validation du résultat. Ces deux concepts sont légitimes mais ne doivent pas partager un nom aussi ambigu.

**Impact refactoring :** remplacer `success` par des champs orthogonaux, par exemple :

- `solver_status`
- `simulation_completed`
- `validation_status`
- `decision_ready`

Un invariant minimal devrait imposer qu’un résultat `status="succeeded"` n’ait aucune erreur critique.

### MCP-03 — Le catalogue mélange presets descriptifs et presets simulables

**Gravité : critique — Confiance : élevée**

Trois presets listés par `list_presets` échouent avec `Unsupported chemistry mapping` :

- `LCO_3AH`
- `LMNO_4AH`
- `NCA_5AH`

Ils restent pourtant consommés par `cell_selection_wizard`, qui dimensionne leurs packs et leur attribue des scores. `NCA_5AH`, par exemple, reçoit des métriques de densité et de puissance alors que `run_simulation` et `compare_presets` ne peuvent pas l’exécuter.

**Impact refactoring :** publier des capacités explicites par preset :

```text
supports_simulation
supports_packaging
supports_aging
supports_charging
supports_operating_window
```

Un preset non simulable ne devrait pas être présenté comme comparable sur des métriques issues de simulation.

### MCP-04 — Les presets redimensionnés ne conservent pas leur énergie nominale

**Gravité : critique — Confiance : élevée**

Résultats du smoke test 1C :

| Preset | Énergie nominale | Énergie simulée | Ratio | Statut |
|---|---:|---:|---:|---|
| `LFP_10AH` | 32,00 Wh | 3,39 Wh | 10,6 % | failed |
| `LFP_5AH` | 16,00 Wh | 4,86 Wh | 30,4 % | failed |
| `LFP_HP_20AH` | 64,00 Wh | 2,18 Wh | 3,4 % | failed |
| `LFP_PRADA_2P3AH` | 7,36 Wh | 6,16 Wh | 83,7 % | failed |
| `NMC_10AH` | 37,00 Wh | 17,43 Wh | 47,1 % | failed |
| `NMC_5AH` | 18,50 Wh | 17,88 Wh | 96,6 % | succeeded |
| `NMC_AI_ENERTECH` | 8,21 Wh | 8,58 Wh | 104,5 % | succeeded |
| `NMC_CHEN_LGM50` | 18,15 Wh | 17,88 Wh | 98,5 % | succeeded |
| `NMC_ECKER_KOKAM` | 0,56 Wh | 0,59 Wh | 104,8 % | succeeded |
| `NMC_HE_50AH` | 185,00 Wh | 8,21 Wh | 4,4 % | succeeded |
| `NMC_MOHTAT_POUCH` | 18,00 Wh | 18,03 Wh | 100,1 % | failed |
| `NMC_OKANE_AGING` | 18,00 Wh | 17,85 Wh | 99,2 % | failed |

Le cas `NMC_HE_50AH` est particulièrement problématique : la simulation est marquée réussie après seulement 8,21 Wh pour une cellule nominale de 185 Wh. `run_simulation` ne retourne pas la durée effectivement simulée, ce qui empêche le client de distinguer une fin normale d’une terminaison anticipée.

La sensibilité de `peak_power_W` à `nominal_capacity_Ah` est par ailleurs annoncée exactement nulle lorsque la capacité est variée de 4 à 6 Ah. Ce résultat renforce l’hypothèse comportementale que la capacité catalogue n’est pas propagée jusqu’au modèle simulé.

**Impact refactoring :**

- soit redimensionner réellement les paramètres électrochimiques ;
- soit retirer les presets synthétiques de la simulation ;
- toujours retourner le temps final simulé, la raison de terminaison et la fraction du protocole couverte.

### MCP-05 — Le planificateur confond C-rate et température

**Gravité : élevée — Confiance : élevée**

| Question | Température produite | C-rate produit |
|---|---:|---:|
| `Décharge à 1C` | 1 °C | 1C |
| `Décharge à 1 C` | 1 °C | 1C |
| `Décharge à 1 °C` | 1 °C | 1C |
| `Décharge à 25°C` | 25 °C | 1C |
| `Décharge à C/2` | 25 °C par défaut | 1C |
| `Décharge à 2C` | 2 °C | 1C |

`C/2` est ignoré silencieusement. `1C` et `2C` sont convertis en degrés Celsius. Lorsque `temperature_C=25` est fourni explicitement avec une question contenant `1C`, le plan passe en statut `conflict` car il croit avoir extrait une température de 1 °C.

**Impact refactoring :** utiliser une grammaire d’unités séparant explicitement `°C` et C-rate, et ne jamais convertir une expression ambiguë sans diagnostic.

### MCP-06 — Un plan « ready » peut être impossible à exécuter

**Gravité : élevée — Confiance : élevée**

Un plan DFN a été produit avec :

- `ready_for_execution=true`
- modèle `doyle_fuller_newman`
- 5 A, 3 600 s et 25 °C
- signaux `voltage`, `temperature`, `electrolyte_concentration`

Le même objet indique simultanément :

- `direct_core_tool_supported=false`
- `tool=null`
- « current core MCP execution contract cannot express every planned setting »

La tentative de continuité avec `run_simulation` :

- conserve courant et température ;
- exécute `single_particle` au lieu de DFN ;
- ne retourne aucun des trois signaux demandés.

**Impact refactoring :** créer un objet `ExperimentSpec` commun au planificateur et à l’exécuteur. `ready_for_execution` doit être faux tant que le plan ne peut pas être représenté sans perte.

### MCP-07 — `compare_presets` classe les erreurs critiques à l’envers

**Gravité : élevée — Confiance : élevée**

Pour `LFP_5AH`, `NMC_5AH` et `NMC_10AH` :

- LFP : 1 erreur critique ;
- NMC : 0 erreur critique ;
- résultat déclaré : `best = LFP_5AH`, `best_value = 1`.

Les autres directions testées étaient correctes : énergie, puissance et tension maximisées ; temps solveur et avertissements minimisés.

Les doublons sont également ambigus. Avec `["NMC_5AH", "NMC_5AH"]`, la liste `scenarios` conserve deux entrées alors que les dictionnaires de métriques n’en conservent qu’une.

**Impact refactoring :** associer à chaque métrique une direction explicite et dédupliquer ou identifier les scénarios avant l’agrégation.

### MCP-08 — La durée de vie est extrapolée malgré l’absence de signal

**Gravité : critique — Confiance : élevée**

Avec trois cycles représentatifs sur `NMC_OKANE_AGING` :

- capacité observée : pratiquement constante à 2,5 Ah ;
- pente : `-3,04 × 10⁻¹⁶ Ah/cycle` ;
- `R² = -13` ;
- ratio d’extrapolation : `5,48 × 10¹⁴` ;
- durée annoncée : environ `4,50 × 10¹² années`.

Avec `warranty_analysis` :

- `R² = -8` ;
- ratio d’extrapolation : `6,92 × 10¹⁴` ;
- durée de vie estimée : environ `1,89 × 10¹³ années` ;
- conclusion : `passes_warranty=true`, `risk_level="Low Risk"`.

Les limites sont textuellement mentionnées, mais elles ne neutralisent pas les conclusions catégoriques.

**Impact refactoring :** retourner une projection indisponible lorsque :

- la pente n’est pas significativement négative ;
- la variance observée est insuffisante ;
- le `R²` est invalide ou inférieur au seuil choisi ;
- le ratio d’extrapolation dépasse une limite explicite.

Dans ces cas, `passes_warranty` et `risk_level` doivent rester `null`.

### MCP-09 — Les stratégies de charge ne produisent aucune comparaison exploitable

**Gravité : élevée — Confiance : élevée**

Sur `NMC_OKANE_AGING` et `NMC_CHEN_LGM50`, les cinq stratégies ont échoué :

- `standard_1C`
- `fast_2C`
- `gentle_0.5C`
- `multi_step_CC`
- `pulse_0.5C`

Pour les trois premières stratégies, les durées retournées sont identiques :

- charge : 45 min ;
- décharge : 45 min ;
- même erreur de sous-tension au même instant.

Cette identité est incompatible avec l’intuition attendue pour 0,5C, 1C et 2C et suggère que le protocole ou le reporting n’est pas réellement spécifique à la stratégie.

Un nom de stratégie inconnu n’est pas rejeté : l’outil retourne simplement `strategies=[]`.

**Impact refactoring :**

- valider les noms de stratégie ;
- exposer le protocole résolu pour chaque stratégie ;
- distinguer durée demandée, durée simulée et durée avant terminaison ;
- ajouter un invariant exigeant des stimuli distincts pour des stratégies distinctes.

### MCP-10 — Le wizard peut attribuer 100/100 avec des preuves manquantes

**Gravité : élevée — Confiance : élevée**

Dans le scénario 400 km, 150 kW, 500 kg, 8 ans, 350 L, 20 000 USD et 45 min :

- les trois premiers presets obtiennent 100/100 ;
- plusieurs autres obtiennent aussi 100/100 malgré des dimensions `null` ;
- `LFP_PRADA_2P3AH` obtient 100/100 avec énergie, coût et durée de vie manquants ;
- `NMC_CHEN_LGM50` obtient 100/100 avec les mêmes dimensions manquantes ;
- ces presets sont marqués `meets_requirements=false`, mais leur score reste maximal.

Le classement inclut aussi les presets non simulables et place `NMC_10AH` en première position alors que son smoke test 1C est en échec.

**Impact refactoring :** séparer :

- score sur preuves disponibles ;
- couverture des preuves ;
- satisfaction des contraintes ;
- éligibilité au classement.

Un score total ne devrait pas être comparable lorsque les dénominateurs diffèrent.

### MCP-11 — `estimate_range` est cohérent arithmétiquement mais facilement surinterprétable

**Gravité : moyenne — Confiance : élevée**

Pour un pack `96S40P` NMC de 71,04 kWh :

- énergie utilisable : 63,936 kWh ;
- énergie synthétique « WLTP » : 28,122 kWh sur 23,3 km ;
- autonomie : 52,97 km.

Sensibilités observées :

| Masse | Température | Autonomie |
|---:|---:|---:|
| 900 kg | 25 °C | 105,95 km |
| 1 800 kg | 25 °C | 52,97 km |
| 2 700 kg | 25 °C | 35,32 km |
| 1 800 kg | 0 °C | 52,97 km |
| 1 800 kg | 50 °C | 52,97 km |

La masse agit exactement par facteur inverse et la température n’a aucun effet. L’outil le déclare dans ses hypothèses, ce qui est positif. Le risque vient surtout du nom de cycle `WLTP`, alors que le profil est explicitement synthétique et non réglementaire.

**Impact refactoring :** renommer les profils synthétiques ou rendre le qualificatif visible dans les champs principaux, pas seulement dans les hypothèses.

### MCP-12 — Les courbes de derating sont dégénérées en mode coarse

**Gravité : moyenne — Confiance : élevée**

`operating_window` teste 27 points :

- 9 `safe` ;
- 18 `caution` ;
- 0 `avoid`.

Toutes les températures 0 et 50 °C sont classées `caution`, tandis que les neuf points à 25 °C sont `safe`. Le modèle est isotherme et `temperature_rise_C=0` partout.

`derating_curves` dérive alors :

- trois points SOC, tous à 3C ;
- un seul point température, 25 °C à 3C.

Le résultat nommé `max_crate_vs_temperature` n’est donc pas une courbe.

**Impact refactoring :** conserver les points caution avec un facteur de réduction explicite, ou retourner un statut `insufficient_curve_support`.

### MCP-13 — La sensibilité est plus étroite que son interface ne le suggère

**Gravité : moyenne — Confiance : élevée**

Les noms naturels `temperature` et `current` sont rejetés. Les seuls paramètres acceptés observés sont :

- `temperature_C`
- `nominal_capacity_Ah`

Le résultat porte uniquement sur `peak_power_W`. La capacité nominale variée de 4 à 6 Ah produit une sensibilité exactement nulle, tandis que la température de 0 à 55 °C produit une variation faible.

**Impact refactoring :** publier la liste des paramètres et métriques supportés dans `describe_api`, et relier la capacité modifiée au modèle réellement simulé.

### MCP-14 — Le journal de session est sélectif

**Gravité : moyenne — Confiance : élevée**

À la fin de l’investigation, `get_session_summary` comptait 45 investigations, réparties notamment entre simulations, comparaisons, pack, autonomie et vieillissement.

Les appels suivants n’apparaissaient pas :

- `describe_api`
- `list_presets`
- `plan_experiment`
- `check_feasibility`

Les erreurs de validation ne sont pas enregistrées de manière homogène. Certaines opérations internes sont en revanche visibles : un appel à `warranty_analysis` semble contribuer à un appel supplémentaire de `predict_lifetime`.

**Impact refactoring :** définir si la session journalise les requêtes utilisateur, les exécutions internes, ou les deux. Ajouter identifiant parent/enfant, statut et durée à chaque événement.

### MCP-15 — Les contrats annoncés et appelables divergent

**Gravité : moyenne — Confiance : élevée**

Exemples observés :

- `describe_api` présente `pack_sizing.voltage_range` comme un tuple ; l’outil appelable expose `voltage_range_min_V` et `voltage_range_max_V`.
- `describe_api` présente `optimize_charging.charge_current_range_A` comme un tuple ; l’outil appelable expose `charge_current_min_A` et `charge_current_max_A`.
- `sensitivity_analysis` ne publie pas les valeurs autorisées.
- la validation de `estimate_range` accepte aussi `WLTP_CLASS3`, absent de la courte description initiale des cycles.
- les signaux acceptés par `plan_experiment` ne sont découverts qu’après une erreur.

**Impact refactoring :** générer `describe_api` depuis le même schéma que l’enregistrement MCP, puis ajouter les enums et unités à ce schéma unique.

## Comportements solides à préserver

### Validation des entrées

Les validations suivantes sont claires et précises :

- preset inconnu avec liste des valeurs disponibles ;
- courant nul ;
- durée nulle ;
- température hors `[-40, 100]` ;
- longueurs de trace incompatibles ;
- temps non strictement croissant ;
- convention de signe inconnue ;
- liste de presets vide ;
- énergie de pack négative ;
- plage de tension inversée ;
- cycle véhicule inconnu ;
- nombre de cellules nul ;
- masse véhicule négative ;
- nombre de cycles insuffisant pour le fit ;
- seuil SOH hors `(0, 1]` ;
- plage de charge inversée ;
- taille de grille inconnue.

### Déterminisme

Deux simulations strictement identiques ont produit :

- des identifiants distincts ;
- des métriques physiques exactement identiques ;
- des temps solveur différents, comme attendu.

Deux plans identiques ont produit des identifiants distincts mais une configuration identique.

### `compare_test_data`

Points positifs à conserver :

- normalisation de l’origine temporelle ;
- interpolation documentée ;
- convention de résidu explicite ;
- normalisation correcte d’un courant mesuré négatif avec `discharge_negative` ;
- couverture et absence d’extrapolation indiquées ;
- RMSE, MAE, biais et erreur maximale ;
- seuil d’acceptation correctement évalué ;
- `decision_ready=false` malgré un seuil RMSE réussi ;
- limites et expériences suivantes clairement formulées.

La convention reste toutefois asymétrique : avec `discharge_negative`, les mesures peuvent être négatives, mais `applied_current_A` doit rester strictement positif.

### Arithmétique pack

Pour 60 kWh avec `NMC_5AH`, le résultat `95S35P` est arithmétiquement cohérent :

- 3 325 cellules ;
- 351,5 V ;
- 175 Ah ;
- 61,5125 kWh.

Pour 80 kWh, `pack_sizing` et `cell_selection_wizard` convergent sur `95S46P` et 80,845 kWh.

## Priorités proposées pour le refactoring

### P0 — Stabiliser le contrat de réponse

1. Introduire une enveloppe commune et versionnée.
2. Séparer résolution numérique, validation physique et aptitude décisionnelle.
3. Uniformiser les erreurs de validation, d’exécution et de domaine.
4. Faire échouer explicitement les listes vides dues à des identifiants inconnus.

### P0 — Empêcher les conclusions non soutenues

1. Neutraliser les projections de vieillissement lorsque la pente n’est pas identifiable.
2. Rendre `passes_warranty` et `risk_level` nuls si la projection est invalide.
3. Exclure du classement les presets non simulables ou insuffisamment documentés.
4. Ne jamais classer une exécution contenant une erreur critique comme meilleure.

### P1 — Unifier preset, plan et exécution

1. Créer une matrice de capacités par preset.
2. Utiliser un schéma `ExperimentSpec` partagé par planification et simulation.
3. Garantir que modèle, protocole, SOC, thermique et signaux sont conservés.
4. Corriger ou supprimer les presets dont la capacité nominale n’est pas propagée.

### P1 — Rendre les comparaisons auditables

1. Déclarer la direction de chaque métrique.
2. Exposer le protocole résolu de chaque stratégie de charge.
3. Séparer score, couverture des données et respect des contraintes.
4. Retourner durée demandée, durée simulée, événement de terminaison et couverture.

### P2 — Consolider la traçabilité

1. Générer `describe_api` depuis le schéma MCP réel.
2. Journaliser tous les appels avec parent, enfant, statut et durée.
3. Distinguer explicitement données de littérature, hypothèses illustratives et résultats simulés.
4. Renommer les profils véhicules synthétiques pour éviter une association réglementaire.

## Tests d’acceptation recommandés

### Contrat commun

- Toute réponse possède exactement un statut terminal normalisé.
- `ok=false` implique un objet `error` structuré.
- `validation_status=failed` interdit `decision_ready=true`.
- Une erreur critique interdit un statut global `succeeded`.

### Presets

- Chaque preset publié déclare ses capacités.
- Chaque preset `supports_simulation=true` passe un smoke test nominal.
- À 1C, la durée et l’énergie simulées sont cohérentes avec la capacité déclarée ou expliquées par un événement terminal.
- Aucun outil de décision n’utilise une métrique simulée pour un preset non simulable.

### Planification

- `1C`, `2C`, `C/2`, `1 °C` et `25 °C` sont distingués.
- Un plan `ready_for_execution=true` peut être transmis sans transformation à l’exécuteur.
- Modèle et signaux demandés sont préservés.

### Comparaisons

- `critical_errors` est minimisé.
- Les doublons de scénario sont refusés ou identifiés de manière unique.
- Les dimensions manquantes empêchent un score total maximal comparable.

### Vieillissement et garantie

- Une pente non identifiable produit `projection.status="insufficient_evidence"`.
- Un `R²` invalide ou une extrapolation excessive empêche toute décision de garantie.
- Les unités, seuils et horizons sont vérifiés avant projection.

### Charge

- Chaque stratégie expose un stimulus différent et vérifiable.
- Une stratégie inconnue produit une erreur de validation.
- Les durées 0,5C, 1C et 2C ne peuvent pas être identiques sans justification physique explicite.
- Aucun protocole en échec n’entre dans un classement.

### Session

- Chaque appel utilisateur crée un événement.
- Chaque sous-appel interne référence son parent.
- Les erreurs de validation sont visibles.
- Le nombre d’investigations est reproductible à partir des événements.

## Limites de cette investigation

- Audit strictement boîte noire : aucune hypothèse sur l’implémentation interne n’est présentée comme un fait.
- Aucune donnée expérimentale réelle n’a été utilisée.
- Les conclusions scientifiques portent sur la cohérence des réponses, pas sur la validité intrinsèque des jeux de paramètres PyBaMM.
- Les temps solveur ne constituent pas un benchmark de performance contrôlé.
- Les outils `fine` n’ont pas été exercés ; les fenêtres et courbes ont été testées en mode `coarse`.
- Les résultats décrivent le serveur observé le 4 août 2026 et doivent être rejoués après refactoring.

## Questions ouvertes

1. `success` représente-t-il officiellement le solveur, l’expérience ou le résultat validé ?
2. Les presets synthétiques sont-ils destinés à être simulables ou seulement utilisables pour le pack ?
3. Quelle est la source d’autorité des capacités nominales : catalogue, paramètre PyBaMM ou transformation de scaling ?
4. Les conclusions de garantie doivent-elles rester disponibles en absence de vieillissement mesurable ?
5. La session doit-elle être un journal d’audit complet ou seulement un rapport des résultats jugés intéressants ?
6. Le terme WLTP doit-il être réservé à une trace réglementaire ou corrélée ?

## Résolution appliquée après l’investigation

Date du refactoring : 9 août 2026
Portée : correction des contrats et comportements observés, avec conservation des champs historiques pour limiter la rupture des clients existants

Cette seconde phase s’appuie sur les constatations boîte noire ci-dessus. Le choix directeur est de ne jamais transformer une preuve insuffisante en conclusion : lorsqu’une fidélité physique ne peut pas être garantie, le serveur l’annonce et interdit l’usage décisionnel au lieu de fabriquer une précision.

| Constatation | Solution retenue | Raisonnement et contrôle |
|---|---|---|
| **MCP-01** | Enveloppe versionnée `2.0` ajoutée à toutes les réponses dictionnaire : `ok`, `response.status`, erreur structurée, avertissements et diagnostics. | Un client dispose désormais d’un chemin de lecture stable, tandis que les champs historiques restent disponibles pendant la migration. Tests de succès, validation et erreur métier. |
| **MCP-02** | Séparation de `solver_success`, `validation_status` et `decision_ready`; le champ historique `success` reflète maintenant la réussite validée. | La convergence numérique n’est plus confondue avec la validité du résultat. Invariants testés sur les comparaisons et résultats en échec. |
| **MCP-03** | Matrice de capacités centralisée par preset, exposant support de simulation, fidélité, jeu de paramètres, politique de mapping et domaines d’usage. | Catalogue, exécution et wizard consomment la même autorité; les chimies non supportées ne sont plus classées comme simulables. |
| **MCP-04** | Les mappings non redimensionnés sont explicitement marqués `chemistry_proxy_unscaled`; leurs résultats restent exploratoires et `decision_ready=false`. L’exécution expose durée demandée/simulée, couverture et terminaison. | Un redimensionnement électrochimique arbitraire aurait créé une fausse exactitude. La solution sûre est de rendre la limite visible et bloquante jusqu’à une vraie paramétrisation. La sensibilité à la capacité est retirée tant qu’elle n’est pas propagée. |
| **MCP-05** | Grammaires séparées pour `C/2`, `1C`, `2C` et les températures avec degré ou contexte explicite. | L’unité détermine désormais le sens; les formes ambiguës ne sont plus converties en température. Tests paramétrés sur les formulations de l’audit. |
| **MCP-06** | Le plan transmet modèle, SOC initial, mode thermique, C-rate et signaux; SPM, SPMe et DFN sont exécutables pour le protocole CC supporté. `ready_for_execution` exige un outil direct et une configuration complète. | La continuité plan-vers-exécution devient sans perte. Un test réel exécute un plan SPMe et vérifie modèle, signal, unité et couverture. |
| **MCP-07** | Direction de minimisation centralisée pour temps solveur, erreurs critiques et avertissements; doublons de presets rejetés. | Le classement ne peut plus récompenser une erreur critique ni écraser silencieusement un scénario. |
| **MCP-08** | Garde-fous sur variance, pente relative, R², ratio d’extrapolation et direction temporelle. En preuve insuffisante, années/cycles, verdict de garantie et risque valent `null`. | Une extrapolation n’est publiée que si le signal observé la soutient. Test réel sur la trajectoire quasi constante de l’audit. |
| **MCP-09** | Validation stricte des stratégies, protocole résolu exposé, courant réellement dépendant du C-rate, décharge dimensionnée et temps de phase dérivé du signe du courant. | Les stimuli 0,5C, 1C et 2C sont distincts et produisent des durées distinctes; une stratégie inconnue échoue explicitement. |
| **MCP-10** | Séparation du score sur preuves disponibles, de la couverture et de l’éligibilité; score total et rang supprimés si une dimension requise manque. | Un score incomplet ne peut plus être comparé à un score complet, et les presets non simulables sont exclus. |
| **MCP-11** | Profil principal renommé `synthetic_*`, avec nature synthétique, absence de statut réglementaire et absence d’effet thermique exposées au premier niveau. | Le résultat reste utile sans pouvoir être confondu avec une trace WLTP réglementaire ou un modèle thermique. |
| **MCP-12** | Chaque courbe publie son nombre de points et un statut; moins de deux points produit `insufficient_curve_support` et `decision_ready=false`. | Un point unique n’est plus présenté comme une courbe exploitable. Test unitaire et essai coarse réel. |
| **MCP-13** | Découverte limitée aux paramètres réellement propagés (`temperature_C`) et à la métrique réellement calculée (`peak_power_W`). | L’interface ne promet plus une sensibilité à la capacité nominale sans effet dans le modèle. |
| **MCP-14** | Tous les outils de découverte, planification, faisabilité et erreurs de validation sont journalisés. Chaque événement porte identifiant, parent, statut et durée; les sous-investigations sont reliées à l’appel racine sans doublon. | La session devient un journal reproductible des appels utilisateur et de leurs sous-calculs. Tests sur succès, validation et chaîne garantie-vers-durée de vie. |
| **MCP-15** | `describe_api` aligné sur les paramètres MCP réellement appelables, avec plages séparées et valeurs autorisées. | La découverte et l’invocation décrivent désormais le même contrat. Les divergences relevées dans l’audit sont couvertes par régression. |

### Décisions de compatibilité et limites assumées

- L’enveloppe commune est additive : les champs historiques restent au premier niveau afin de laisser aux clients le temps de migrer.
- Les presets `chemistry_proxy_unscaled` ne sont volontairement pas « corrigés » par un facteur de capacité simpliste. Leur non-aptitude décisionnelle est désormais explicite; une future paramétrisation physique pourra lever cette restriction preset par preset.
- Une analyse de garantie qui dispose d’un ajustement acceptable reste un screening expérimental et conserve `decision_ready=false` jusqu’à corrélation avec des essais.
- Les profils véhicule restent synthétiques; le changement porte sur leur identité et leur provenance, pas sur une revendication réglementaire nouvelle.

### Stratégie de non-régression

Les tests ajoutés rejouent directement les cas révélateurs de l’audit : parsing unités, enveloppe commune, capacités du catalogue, plan exécutable, comparaison minimisée, stratégies de charge distinctes, vieillissement non identifiable, journal parent/enfant, profil synthétique et support des courbes. La suite complète est exécutée en deux groupes, rapide et lent, afin d’inclure les simulations PyBaMM sans masquer les contrats rapides.
