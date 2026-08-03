# Planifier avant de simuler

`plan_experiment` est la première brique de l'assistant électrochimique. Il ne
lance aucun calcul. Il transforme une question et ses éventuels arguments
structurés en proposition que l'ingénieur peut relire avant de consommer du
temps de simulation.

## Contrat du plan

Chaque plan possède un `plan_id` et rend visibles :

- la question d'ingénierie originale ;
- la cellule, le modèle, la température, le protocole et les signaux proposés ;
- la justification du niveau de modèle ;
- les entrées encore manquantes ;
- les valeurs proposées qui demandent confirmation ;
- les hypothèses et limites ;
- la capacité — ou non — du MCP actuel à exécuter exactement la proposition.

Quand cette capacité existe, `execution.tool` et `execution.arguments` forment
un handoff déterministe vers `run_simulation`. Ils ne déclenchent toujours
aucun calcul : le client doit d'abord faire confirmer les valeurs proposées.

`ready_for_execution` signifie seulement que les entrées obligatoires sont
présentes. Si `requires_confirmation` est vrai, l'agent doit encore faire
valider les valeurs proposées. Un plan ne contient jamais de résultat simulé.

## Sélection de modèle initiale

La première politique reste volontairement simple et testable :

| Signaux demandés | Modèle proposé |
|---|---|
| tension, courant, SOC et métriques globales | SPM |
| états de l'électrolyte | SPMe |
| signaux résolus par électrode | DFN |

Demander un signal thermique propose aussi un modèle thermique lumped.

## Interprétation conservatrice de la question

Le serveur reconnaît un vocabulaire français/anglais limité : noms exacts de
presets, SPM/SPMe/DFN, décharge/repos/charge CC-CV, températures numériques et
un premier groupe de signaux. Chaque extraction conserve le fragment et les
indices exacts dans la question.

Le serveur ne transforme pas « très froid » en une température et ne mappe pas
une référence commerciale inconnue vers un preset générique. `1C` reste un
C-rate et n'est pas interprété comme 1 °C. Tout texte non reconnu demeure non
interprété.

Un argument structuré peut surcharger une extraction, mais une contradiction
est publiée dans `traceability.conflicts`, fait passer le plan au statut
`conflict` et exige une confirmation.

## Protocoles proposés

Trois intentions sont reconnues : `cc_discharge`, `rest` et `cccv_charge`.
Les valeurs de référence (1C, 600 s de repos, SOC initial, seuil CC-CV) sont
toujours classées comme valeurs proposées à confirmer, jamais comme faits.
