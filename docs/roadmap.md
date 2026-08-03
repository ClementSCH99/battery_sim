# Feuille de route de récupération

La stratégie est de construire une trajectoire compréhensible et toujours exécutable. Chaque phase doit réduire la dette avant d'ajouter de nouvelles capacités.

## Phase 0 — Reprendre le contrôle (en cours)

- [x] Vérifier l'état Git et la structure réelle.
- [x] Vérifier les contrats d'architecture déjà en place.
- [x] Établir une suite de tests rapide distincte des études PyBaMM longues.
- [x] Formaliser la commande de développement avec une suite rapide séparée des études PyBaMM marquées `slow`.
- [x] Définir la direction produit et la carte des responsabilités.
- [x] Dériver la découverte des outils de la façade réelle.
- [x] Permettre l'injection du backend dans `AgentAPI`.
- [x] Classer les capacités agent en `core` ou `experimental` selon leur preuve physique actuelle.
- [x] Constituer un jeu minimal de simulations LFP/NMC avec provenance et invariants physiques documentés.

## Phase 1 — Stabiliser le noyau scientifique

Objectif : une simulation cellule courte, reproductible et explicable de bout en bout.

- [x] clarifier la provenance des références LFP Prada2013 et NMC Chen2020 ;
- [x] séparer température ambiante, température initiale et température cellule calculée ;
- [x] documenter et tester la convention de signe courant/puissance ;
- [x] vérifier l'alignement des unités entre extraction backend et catalogue des signaux ;
- [x] extraire la transformation solution PyBaMM → signaux canoniques hors de `PyBaMMBackend` ;
- [x] scinder construction PyBaMM, extraction des résultats et observabilité hors de `PyBaMMBackend` ;
- [x] ajouter des cas de référence LFP et NMC pour une décharge CC ;
- [x] étendre les références aux protocoles repos et CC-CV.

Critère de sortie : pour chaque cas de référence, le dépôt explique les hypothèses, reproduit le résultat et détecte une régression physique grossière.

## Phase 2 — Simplifier l'application

Objectif : rendre chaque cas d'usage lisible dans un module court.

- [x] créer le point d'entrée public `interface/agent_api.py` utilisé par MCP ;
- [x] extraire les handlers de simulation, catalogue cellule et pré-validation ;
- [x] extraire les handlers de comparaison et sensibilité ;
- [x] extraire le handler de session ;
- [x] extraire les outils expérimentaux de vieillissement et garantie ;
- [x] extraire les outils expérimentaux pack, sélection cellule et autonomie ;
- [x] extraire les outils expérimentaux de recharge, fenêtre opératoire et derating ;
- [x] remplacer `application_services.py` par des services ciblés et un shim de compatibilité ;
- [x] réduire `investigation_tools.py` en modules ciblés et simplifier `parameter_sweep.py` autour du service canonique ;
- [x] séparer métadonnées du domaine et découverte des outils dans `api_schema.py`.

Critère de sortie : le chemin d'une requête MCP vers PyBaMM se suit sans ouvrir un fichier de plus de 500 lignes.

## Phase 3 — Recentrer le MCP

Objectif : exposer un petit ensemble d'outils fiables pour l'investigation cellule.

- [x] publier un statut de maturité et un domaine de validité par réponse d'outil ;
- [x] exposer d'abord découverte, simulation, comparaison et sensibilité ;
- [x] unifier les erreurs MCP et ajouter un identifiant de simulation ;
- [x] rendre les hypothèses visibles dans chaque réponse ;
- [x] tester le protocole MCP séparément des longues simulations PyBaMM.

Critère de sortie : un client MCP peut découvrir, exécuter et interpréter une étude sans connaître les détails internes et sans recevoir une confiance injustifiée.

## Phase 4 — Construire l'assistant électrochimique

Objectif : passer d'une collection d'outils à une méthode d'investigation guidée.

- [x] définir un contrat de plan d'expérience non exécutable et traçable ;
- [x] demander ou proposer les hypothèses structurées manquantes ;
- [x] proposer le modèle minimal selon les signaux requis ;
- [x] produire un handoff exact vers `run_simulation` pour les plans cœur compatibles ;
- [x] transformer de manière conservatrice et traçable une question libre en champs d'expérience ;
- [x] définir un contrat sourcé de trace d'essai cellule ;
- [x] comparer une décharge CC simulée et mesurée sans extrapolation cachée ;
- [x] produire une conclusion bornée avec niveau de confiance et prochaines expériences pour la comparaison essai ;
- généraliser l'évaluation de preuve aux comparaisons multi-conditions et aux autres investigations cœur.

## Phase 5 — Réintroduire les fonctions avancées

Optimisation de charge, vieillissement, garantie, pack et véhicule seront promus un par un seulement après :

1. définition de la décision d'ingénierie visée ;
2. liste des hypothèses et paramètres requis ;
3. domaine de validité ;
4. cas de référence ;
5. contrat de sortie ;
6. revue physique et tests.

Une fonction non validée peut rester expérimentale ; elle ne doit pas être présentée comme une prédiction d'ingénierie fiable.
