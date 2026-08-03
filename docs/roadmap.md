# Feuille de route de reprise

Cette feuille de route remplace la liste historique de fonctionnalités terminées.
Elle décrit le niveau de preuve à construire pour faire de `battery_sim` un outil
interne d'aide à la calibration BMS.

## Cap produit

`battery_sim` doit aider un ingénieur validation EV à :

1. comprendre l'influence des conditions et paramètres cellule ;
2. simuler tension, capacité, puissance, température et vieillissement ;
3. comparer simulation et essai avec des métriques simples ;
4. générer des données pour tester un modèle équivalent 2RC ;
5. traduire ensuite les résultats cellule en décisions BMS et études pack.

La priorité est l'explicabilité puis la précision. PyBaMM est le seul moteur
prévu. L'API Python est prioritaire ; MCP reste expérimental jusqu'à
stabilisation du noyau.

## Périmètre initial

- une cellule NMC documentée, puis une cellule LFP ;
- décharge CC avant profil de mission ;
- modèle électrothermique le plus simple capable de fournir les signaux requis ;
- température principalement entre 10 et 55 °C, avec quelques essais sous 0 °C ;
- SOC de 0 à 100 %, en séparant domaine demandé et domaine validé ;
- charge jusqu'à 2 C ;
- décharge continue jusqu'à 3 C, puis impulsions plus élevées ;
- échauffement du module dans une condition thermique mesurée ;
- vieillissement en cyclage étudié d'abord de manière comparative ;
- convention publique cible : courant de décharge négatif.

Le pack est pertinent après validation du modèle cellule. Le véhicule est hors
périmètre.

## Règles de preuve

Chaque résultat doit distinguer :

- **simulé** : sortie directe du modèle ;
- **dérivé** : calcul effectué à partir des sorties ;
- **supposé** : valeur imposée sans preuve expérimentale ;
- **mesuré** : donnée d'essai avec provenance.

Chaque étude publie le jeu de paramètres, le modèle, les conditions initiales,
le protocole, les conventions, les limites et la version de PyBaMM.

Une entrée impossible ou une combinaison physique incompatible bloque
l'exécution. Une extrapolation ou un domaine insuffisamment validé produit un
avertissement et marque le résultat comme exploratoire.

Une recherche bibliographique démontre provenance et plausibilité. Une
validation exige en plus une comparaison à des données indépendantes.

## Phase 0 — Sécuriser et inventorier

- [x] créer une branche de récupération ;
- [x] enregistrer l'état interrompu dans un checkpoint non audité ;
- [x] établir la matrice des responsabilités et dépendances ;
- [x] classer chaque API en `core`, `experimental` ou `legacy` ;
- [x] identifier les couches de compatibilité supprimables ;
- [x] définir les règles de dépendance et de taille des modules ;
- [x] verrouiller une version de PyBaMM pendant la validation.

Critère de sortie : le chemin API → modèle → PyBaMM → résultat est explicable,
et chaque module du noyau possède une responsabilité unique.

## Phase 0.5 — Restructurer le dépôt

Objectif : rendre les frontières visibles dans l'arborescence avant d'ajouter
des données ou de modifier la physique.

- [ ] adopter un layout standard `src/battery_sim/` ;
- [ ] découper le noyau en `core/cell`, `core/experiment`, `core/result` et
  `core/simulation` ;
- [ ] déplacer les cas d'usage vers `application/` ;
- [ ] déplacer les références et traces d'essai vers `validation/` ;
- [ ] renommer `backend/` en `infrastructure/pybamm/` ;
- [ ] séparer API Python, presenters et MCP sous `interfaces/` ;
- [ ] isoler les outils non validés sous `experimental/` ;
- [ ] définir une API Python publique courte depuis `battery_sim` ;
- [ ] supprimer les couches de compatibilité sans consommateur externe ;
- [ ] découper tous les modules à 300 lignes maximum ;
- [ ] mettre à jour packaging, documentation et tests ;
- [ ] vérifier les suites rapide, architecture et références physiques.

Critère de sortie : le package installé provient uniquement de `src/`, les
dépendances suivent les règles documentées et aucun module de production ne
dépasse 300 lignes.

## Phase 1 — Référence NMC électrique

- [ ] identifier la cellule commerciale et sa fiche technique ;
- [ ] créer un manifeste de données et de métadonnées ;
- [ ] importer courant, tension et température depuis CSV ou NDJSON ;
- [ ] représenter SOC, tension et préconditionnement initiaux ;
- [ ] appliquer la convention de décharge négative de bout en bout ;
- [ ] choisir automatiquement le modèle le plus simple, avec justification ;
- [ ] comparer essai et simulation sans extrapolation ;
- [ ] calculer erreur RMS/max de tension, capacité et instant de coupure ;
- [ ] conserver les courbes comme références de non-régression.

Critère de sortie : une commande Python reproduit l'étude, publie ses hypothèses
et explique les principaux écarts.

## Phase 2 — Référence thermique

- [ ] documenter températures ambiante et initiale, position du capteur et montage ;
- [ ] documenter les conditions de contact et refroidissement connues ;
- [ ] vérifier la cohérence des propriétés thermiques du paramétrage ;
- [ ] comparer température maximale et élévation de température ;
- [ ] convertir de façon traçable le courant pack en courant cellule ;
- [ ] signaler les conclusions impossibles sans modèle thermique pack.

Critère de sortie : l'erreur thermique est quantifiée face à au moins une mesure
indépendante et le domaine de validité est explicite.

## Phase 3 — Évaluation d'un 2RC

- [ ] définir la grille SOC × température × SOH × sens du courant ;
- [ ] générer des profils PyBaMM traçables ;
- [ ] importer les sorties du 2RC sans l'identifier automatiquement ;
- [ ] comparer 2RC, PyBaMM et essai quand les trois existent ;
- [ ] publier RMSE, erreur maximale et erreur pendant les impulsions ;
- [ ] définir le format d'une éventuelle table BMS.

Critère de sortie : les domaines où le 2RC est suffisant ou insuffisant sont
visibles sans traiter PyBaMM comme une vérité expérimentale.

## Phase 4 — Vieillissement comparatif

- [ ] choisir un paramétrage NMC compatible avec les mécanismes étudiés ;
- [ ] documenter SEI, perte de lithium, perte de matière active et lithium plating ;
- [ ] comparer 4,1 V, 4,2 V et 4,3 V lorsque le paramétrage le permet ;
- [ ] simuler d'abord des centaines de cycles ;
- [ ] distinguer classement relatif et prédiction absolue ;
- [ ] ajouter des données de vieillissement lorsqu'elles deviennent disponibles.

Critère de sortie : l'outil explique une tendance comparative, les mécanismes
activés et la faiblesse de la preuve.

## Phase 5 — Variabilité pack 96s2p

- [ ] définir les distributions de capacité, résistance, SOC et température ;
- [ ] propager statistiquement ces dispersions ;
- [ ] étudier la cellule limitante et la puissance disponible ;
- [ ] comparer aux températures pack disponibles ;
- [ ] reporter partage de courant 2p, équilibrage et réseau thermique tant que les
  données ne montrent pas qu'ils sont nécessaires.

Critère de sortie : les hypothèses statistiques sont visibles et une conclusion
pack n'est jamais présentée comme une sortie directe du modèle cellule.

## Politique des outils existants

Les outils actuels de véhicule, sélection, garantie, optimisation et screening
restent accessibles comme `experimental` ou `legacy`. Ils ne font pas partie du
parcours recommandé et ne peuvent être promus sans besoin d'ingénierie, provenance,
domaine de validité, données indépendantes, critères d'acceptation et revue physique.

## Méthode de développement

- une décision discutée avant chaque changement physique ou d'API ;
- un petit commit par décision ;
- tests logiciels rapides à chaque commit ;
- cas scientifique ciblé pour tout changement de physique ;
- validation du propriétaire pour les ruptures d'API ;
- aucun nouvel outil sans besoin réel, hypothèses et preuve.
