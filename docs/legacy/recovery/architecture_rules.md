# Règles d'architecture

Ces règles sont des contraintes de développement, pas une description idéale.
Elles s'appliquent à tout nouveau code et sont protégées par
`tests/test_architecture.py`.

## Direction des dépendances

La direction cible est :

```text
interfaces → application → core ← infrastructure
```

- `core` contient les contrats et règles métier stables. Il ne dépend ni d'une
  interface, ni de PyBaMM.
- `application` orchestre les cas d'usage à partir des contrats du `core`.
- `infrastructure` implémente les ports du `core`, notamment avec PyBaMM.
- `interfaces` traduit Python ou MCP vers les cas d'usage. Elle ne calcule pas
  de résultat scientifique.
- `experimental` peut dépendre du noyau, mais le noyau ne dépend jamais de lui.

La composition du backend concret vit dans `battery_sim/composition.py`.
Aucune exception n'autorise le noyau à importer une interface ou PyBaMM.

## Responsabilité

Un module possède une raison principale de changer. En particulier :

- les contrats de simulation ne formatent pas les réponses ;
- l'adaptateur PyBaMM ne décide pas de la maturité produit ;
- le calcul scientifique n'est pas placé dans MCP ;
- les outils expérimentaux ne sont pas importés par le noyau stable ;
- les réexports de compatibilité ne contiennent aucune logique.

## Taille

- chaque module Python de production est limité à 300 lignes ;
- aucune exception ou budget transitoire n'est autorisé ;
- la règle couvre l'intégralité de `src/battery_sim` récursivement.

## API et maturité

Chaque outil agent déclare exactement un statut :

- `core` : nécessaire au parcours prioritaire et suffisamment maîtrisé pour être
  présenté par défaut ;
- `experimental` : callable pour exploration, sans preuve suffisante pour une
  décision d'ingénierie ;
- `legacy` : conservé temporairement pour migration, absent du parcours recommandé.

Une API ne passe en `core` qu'avec besoin, provenance, domaine de validité,
contrat de sortie, test et revue physique.

## Changements

- une décision physique ou une rupture d'API par commit ;
- aucune nouvelle couche de compatibilité sans date ou phase de suppression ;
- aucune dépendance ajoutée sans justification ;
- la suite d'architecture et la suite rapide doivent passer avant chaque commit ;
- la version de PyBaMM reste verrouillée pendant l'établissement des références.
