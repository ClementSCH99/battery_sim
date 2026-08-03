# Physique et validation

## Position scientifique

`battery_sim` ne transforme pas une simulation en vérité expérimentale. Une
conclusion doit toujours distinguer :

- les entrées mesurées ou issues d’une publication ;
- les hypothèses de modèle et de paramétrage ;
- les sorties directement simulées ;
- les métriques dérivées ;
- le domaine de validité et les données manquantes.

Un preset de littérature est une référence reproductible. Un preset synthétique
ou générique n’est pas le jumeau numérique d’une cellule commerciale.

## Convention électrique

La convention canonique est :

- courant positif : décharge ;
- courant négatif : charge.

Le protocole, les traces d’essai et l’adaptateur PyBaMM doivent publier
explicitement toute conversion de signe.

## Niveaux de modèle

- `SPM` : premier choix pour tension, courant, SOC et métriques globales ;
- `SPMe` : requis lorsque les états de l’électrolyte sont importants ;
- `DFN` : réservé aux besoins électrochimiques résolus par électrode ;
- thermique `isothermal` par défaut, `lumped` lorsque l’échauffement cellule
  doit être estimé simplement.

Le niveau le plus simple est recommandé tant qu’un signal ou une hypothèse ne
justifie pas un modèle plus riche.

## Références disponibles

### NMC — Chen2020

`NMC_CHEN_LGM50` utilise le jeu PyBaMM `Chen2020`. C’est la référence prioritaire
pour la Phase 1 électrique : tension, capacité, énergie et comportement de
décharge doivent être établis avant les outils de décision.

### LFP — Prada2013

`LFP_PRADA_2P3AH` fournit une référence LFP reproductible et un contrepoint de
chimie. Elle ne représente pas une cellule commerciale particulière.

### Vieillissement — O’Kane2022

Le chemin O’Kane est conservé comme référence expérimentale pour SEI, plating
et perte de matière active. Il ne justifie pas encore une prédiction de garantie
ou de durée de vie commerciale.

## Ce que les tests prouvent

Les tests de référence contrôlent notamment :

- exécution reproductible des cas NMC et LFP ;
- bornes et tendances de tension, capacité, énergie et température ;
- cohérence des protocoles et de la convention de courant ;
- présence des diagnostics et erreurs dans `SimulationRun` ;
- provenance du jeu de paramètres.

Ils ne prouvent pas :

- la précision sur une cellule projet sans données d’essai ;
- la sûreté d’un pack ;
- la dispersion d’un assemblage 96s2p ;
- la validité d’une extrapolation de vieillissement longue durée ;
- une température pack sans modèle de refroidissement et géométrie appropriés.

## Comparaison aux essais

Une comparaison simulation–essai exige au minimum temps, tension et protocole
documentés. Courant mesuré, température, SOC initial, préconditionnement,
identification cellule et métadonnées renforcent la preuve.

Les résidus publiés sont des mesures d’accord sur le domaine couvert par les
données. Ils ne constituent pas automatiquement une validation du modèle.

## Promotion d’une capacité

Une capacité ne passe de `experimental` à `core` qu’avec :

1. un besoin d’ingénierie précis ;
2. des hypothèses et unités documentées ;
3. un domaine de validité ;
4. une référence ou un essai traçable ;
5. un contrat de sortie explicable ;
6. des tests et une revue physique.
