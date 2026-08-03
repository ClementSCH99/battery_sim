# Direction du projet

## Pourquoi battery_sim existe

`battery_sim` doit devenir un **assistant d'investigation électrochimique de cellule** : un ingénieur formule une question, l'assistant construit une expérience PyBaMM traçable, exécute la simulation, contrôle la qualité du résultat et explique ce que le modèle permet — ou ne permet pas — de conclure.

Le produit n'est donc ni un simple wrapper Python autour de PyBaMM, ni un catalogue de calculateurs EV. Sa valeur vient de la chaîne complète :

> question d'ingénierie → hypothèses explicites → expérience reproductible → résultat vérifié → interprétation avec limites

## Utilisateur principal

L'utilisateur de référence est un ingénieur cellule, validation ou performance qui connaît les batteries mais ne souhaite pas manipuler directement toute l'API PyBaMM pour chaque étude.

Les décisions pack et véhicule restent utiles comme contexte, mais elles ne doivent pas diluer le cœur scientifique du projet. Une estimation d'autonomie ou un dimensionnement pack ne devient fiable que si les hypothèses cellule et système sont clairement séparées.

## Trois objectifs produit

1. **Exécuter une expérience cellule fiable**
   - cellule et jeu de paramètres identifiés ;
   - modèle électrochimique choisi et justifié ;
   - protocole, température, état initial et solveur explicites ;
   - résultat et erreurs regroupés dans un contrat unique.

2. **Aider à investiguer**
   - comparer des scénarios ;
   - faire varier un paramètre ;
   - analyser les limites tension, température et dégradation ;
   - conserver les hypothèses et la provenance de chaque exécution.

3. **Expliquer avec discipline scientifique**
   - distinguer valeur simulée, valeur dérivée et hypothèse ;
   - signaler les sorties indisponibles selon le modèle ;
   - ne jamais présenter un preset générique comme la représentation validée d'une cellule commerciale ;
   - rendre la simulation reproductible avant de produire une recommandation.

## Périmètre de référence

Le premier produit cohérent se limite volontairement à six capacités :

- découvrir les cellules, modèles, protocoles et signaux disponibles ;
- construire un plan d'expérience explicite avant tout calcul ;
- exécuter une simulation cellule ;
- comparer plusieurs scénarios homogènes ;
- réaliser une analyse de sensibilité simple ;
- expliquer le résultat, ses erreurs et ses limites.

Les outils d'optimisation de charge, durée de vie, garantie, autonomie, dimensionnement pack et sélection de cellule restent dans le dépôt pendant le refactoring. Ils sont considérés comme **expérimentaux** jusqu'à ce que leur modèle physique, leurs hypothèses et leur contrat de sortie soient revus.

## Principes de développement

- Une seule représentation canonique d'une demande de simulation : `Simulation` aujourd'hui, renommable plus tard en `SimulationRequest` si cela améliore réellement la compréhension.
- Un seul résultat canonique : `SimulationRun`, qui contient les signaux, métadonnées, diagnostics et erreurs.
- PyBaMM est un adaptateur d'exécution, pas le domaine métier.
- Le serveur MCP traduit et valide ; il ne porte pas les calculs scientifiques.
- Les capacités annoncées sont dérivées du code exécutable et testées contre lui.
- Chaque nouveau cas d'usage doit documenter ses hypothèses physiques, ses unités, son domaine de validité et un test de référence.
- La simplicité et la compréhension du propriétaire du projet priment sur le nombre d'outils exposés.

## Critère de réussite

Le projet est de nouveau maîtrisable lorsqu'un développeur peut répondre rapidement à ces questions :

1. Où est définie l'intention physique ?
2. Où PyBaMM est-il appelé ?
3. Quel objet sort de toute simulation ?
4. Où une capacité agent est-elle orchestrée ?
5. Quelles hypothèses rendent un résultat valide ou invalide ?

La carte d'architecture répond à ces questions pour l'état actuel. La feuille de route concentre désormais la suite sur la validation électrique NMC, puis thermique et vieillissement.
