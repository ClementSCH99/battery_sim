# Documentation de battery_sim

Cette page est le point d’entrée canonique. Les documents listés ici décrivent
l’état actuel du projet ; tout ce qui se trouve sous `legacy/` est historique.

## Parcours de lecture recommandé

1. [Direction du projet](project_direction.md) — pourquoi le produit existe,
   pour qui et quelles décisions il doit éclairer.
2. [Architecture](architecture.md) — responsabilités, dépendances et contrats
   de simulation.
3. [Physique et validation](physics_and_validation.md) — ce que les modèles
   prouvent, leurs limites et les références disponibles.
4. [Roadmap](roadmap.md) — phases terminées et prochaines priorités.

Ces quatre documents suffisent pour comprendre profondément l’état du projet.

## Guides

- [Démarrage et API Python](guides/getting_started.md)
- [Planifier avant de simuler](guides/experiment_planning.md)
- [Comparer simulation et essai](guides/test_comparison.md)
- [Configurer et utiliser MCP](guides/mcp.md)

## Source de vérité

- le code exécutable et les tests priment sur la prose ;
- `SimulationRun` est le résultat canonique d’une exécution ;
- les capacités non validées sont explicitement `experimental` ;
- les décisions scientifiques doivent préciser hypothèses, unités, provenance
  et domaine de validité ;
- PyBaMM reste l’unique moteur supporté.

## Historique

[L’index legacy](legacy/README.md) explique le classement des anciens audits,
rapports, matrices et documents de migration. Ils sont conservés pour la
traçabilité, pas comme documentation d’utilisation.
