# Comparer simulation et essai cellule

`compare_test_data` réalise la première confrontation directe entre PyBaMM et
une mesure. Son périmètre initial est volontairement étroit : une décharge
cellule à courant constant.

## Entrées obligatoires

- un preset et la provenance textuelle de l'essai ;
- le temps en secondes et la tension en volts ;
- le courant constant imposé à la simulation, positif en décharge ;
- facultativement le courant mesuré et sa convention de signe ;
- la température ambiante et un identifiant d'essai facultatif.

Une trace doit comporter entre 2 et 2 000 points finis, avec un temps strictement
croissant. Le temps est ramené à zéro au premier échantillon. Un courant mesuré
négatif en décharge peut être déclaré avec `discharge_negative` ; il est alors
converti vers la convention canonique positive en décharge.

## Calcul publié

La tension simulée est interpolée aux instants de mesure seulement dans le
domaine temporel commun. La queue d'essai située après un arrêt PyBaMM est
exclue et la couverture devient `partial`. Aucune extrapolation n'est effectuée.
Les métriques sont actuellement non pondérées entre les instants de mesure ;
ce choix est publié dans `coverage.metric_weighting` afin de ne pas masquer
l'effet éventuel d'un échantillonnage irrégulier.

Les résidus suivent toujours :

> résidu = simulation − mesure

Le résultat fournit RMSE, MAE, biais et erreur absolue maximale de tension. Si
le courant mesuré existe, son RMSE et son biais sont aussi calculés. La trace
alignée reste disponible pour une future visualisation ou analyse de résidu.

Un seuil `voltage_rmse_limit_V` peut être fourni. Le résultat indique alors si
ce critère passe pour cette trace. Même lorsqu'il passe, l'appréciation conserve
une confiance `low` et `decision_ready=false` : satisfaire un seuil local ne
constitue pas une validation du modèle.

## Ce que ce résultat ne prouve pas

Cette comparaison n'ajuste aucun paramètre. L'état électrochimique initial de
l'essai est supposé identique à celui du jeu de paramètres sans pouvoir encore
le vérifier. Une faible RMSE sur la trace utilisée ne valide ni le preset comme
jumeau numérique de la cellule, ni le modèle hors de cette condition d'essai.

La prochaine étape scientifique devra séparer explicitement calibration et
validation sur des cellules, températures et C-rates indépendants.

`assessment.next_experiments` propose donc systématiquement le contrôle de
l'état initial, la métrologie et les répétitions, une matrice température/C-rate,
une séparation calibration-validation et l'analyse temporelle des résidus.
