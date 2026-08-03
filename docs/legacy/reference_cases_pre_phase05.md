# Cas de référence scientifiques

Les cas de référence vérifient que le noyau conserve des comportements électrochimiques et numériques essentiels. Ils sont définis dans `core/reference_cases.py` et testés dans `tests/test_reference_cases.py`.

## Ce qu'ils prouvent

- le jeu de paramètres réellement utilisé est enregistré dans `SimulationMetadata` ;
- le courant et la puissance sont positifs en décharge ;
- les signaux temps, tension, courant, puissance, énergie et capacité existent ;
- temps et capacité imposée par le protocole sont conservés ;
- la tension reste dans le domaine du jeu de paramètres ;
- une courte décharge ne termine pas à une tension supérieure à sa tension chargée initiale.
- un repos isotherme conserve courant, énergie et capacité nuls sans dérive de tension artificielle ;
- une charge CC-CV respecte le signe négatif en charge, la coupure tension et le courant de fin de taper.

## Ce qu'ils ne prouvent pas

- une corrélation avec une cellule commerciale particulière ;
- la précision à fort C-rate, basse température ou proche des limites SOC ;
- la validité des modèles de vieillissement ;
- une tolérance utilisable pour une validation produit ou une homologation.

## LFP — Prada2013

| Élément | Valeur |
|---|---|
| Preset | `LFP_PRADA_2P3AH` |
| Jeu PyBaMM | `Prada2013` |
| Modèle | SPM |
| Protocole | décharge 0,5 C pendant 300 s |
| État initial | SOC 80 %, ambiance isotherme 25 °C |
| Fenêtre de tension | 2,0–3,6 V |

Ce cas remplace `Marquis2019` comme référence LFP. `Marquis2019` emploie une fonction OCV positive LiCoO₂ et ne doit pas être présenté comme une paramétrisation LFP.

`Prada2013` ne contient ni les propriétés cellule/collecteurs nécessaires aux modèles thermiques PyBaMM, ni le jeu complet de paramètres de dégradation. Le backend refuse donc explicitement ces options au lieu d'inventer des propriétés manquantes. Les études thermiques utilisent `Chen2020` et les smoke tests de vieillissement utilisent `OKane2022`.

## NMC — Chen2020

| Élément | Valeur |
|---|---|
| Preset | `NMC_CHEN_LGM50` |
| Jeu PyBaMM | `Chen2020` (LG M50) |
| Modèle | SPM |
| Protocole | décharge 0,5 C pendant 300 s |
| État initial | SOC 80 %, ambiance isotherme 25 °C |
| Fenêtre de tension | 2,5–4,2 V |

## Références de protocole — Chen2020

Deux cas complètent les décharges constantes :

| Cas | Protocole | État initial | Invariants principaux |
|---|---|---|---|
| `nmc_chen_spm_rest` | repos 300 s | SOC 50 %, 25 °C isotherme | courant, énergie et capacité nuls ; dérive tension ≤ 10 µV |
| `nmc_chen_spm_1c_cccv_charge` | CC 1 C jusqu'à 4,2 V, puis CV jusqu'à 0,05 C | SOC 20 %, 25 °C isotherme | courant négatif, tension ≤ 4,202 V, courant final au seuil de taper |

L'efficacité aller-retour n'est exposée ni pour une charge seule ni pour une
décharge seule : les deux flux d'énergie doivent avoir été observés. Une petite
tolérance numérique de 10 µV est appliquée au diagnostic des limites tension,
afin de ne pas transformer l'erreur d'arrondi du solveur en défaut physique.

## Chemin de vieillissement expérimental — O'Kane2022

`tests/test_degradation_reference.py` vérifie séparément que `NMC_OKANE_AGING`
produit bien une capacité de décharge par cycle sur trois cycles partiels à
0,5 C et 50 % de profondeur nominale. Ce test prouve que le chemin PyBaMM de
vieillissement est exécutable et que la provenance de l'extrapolation est
visible. Il ne valide ni la pente observée, ni la loi linéaire, ni une durée de
vie réelle.

## Baseline observée

Avec PyBaMM 25.12.2, les cas produisent la baseline informative suivante :

| Cas | Tension initiale → finale | Capacité déchargée | Énergie déchargée |
|---|---:|---:|---:|
| LFP Prada2013 | 3,2705 → 3,2372 V | 0,095833 Ah | 0,311767 Wh |
| NMC Chen2020 | 3,9821 → 3,9034 V | 0,208333 Ah | 0,820932 Wh |

Les références de protocole donnent également :

| Cas | Durée | Tension initiale → finale | Résultat intégré |
|---|---:|---:|---:|
| Repos NMC | 300 s | 3,75087 → 3,75087 V | 0 Ah, 0 Wh |
| Charge CC-CV NMC | 4 766,47 s | 3,58815 → 4,20000 V | 4,09373 Ah chargés, 16,35985 Wh chargés |

Ces valeurs servent au diagnostic humain. Les tests automatisés privilégient les invariants et des bornes physiques robustes afin de ne pas figer les détails numériques d'une version de solveur.

## Exécution

```bash
pytest tests/test_reference_cases.py -v
pytest tests/test_degradation_reference.py -v
```

Ces tests invoquent PyBaMM et portent le marqueur `slow`. Les contrôles de définition et de provenance peuvent être exécutés sans simulation avec :

```bash
pytest tests/test_reference_cases.py -m "not slow" -v
```
