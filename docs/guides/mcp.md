# Guide MCP

MCP expose les mêmes cas d’usage que l’API Python, avec validation des entrées,
contrat de maturité et réponses JSON. Il ne contient aucun calcul physique.

## Vérifier le serveur

```bash
.venv/bin/python -c "from battery_sim.interfaces.mcp import mcp; print('MCP OK')"
```

## Lancer manuellement

Le lanceur stable reste à la racine pour les clients externes :

```bash
.venv/bin/python mcp_server.py
```

## Configuration d’un client

Exemple générique :

```json
{
  "command": "/chemin/vers/battery_sim/.venv/bin/python",
  "args": ["/chemin/vers/battery_sim/mcp_server.py"]
}
```

Utiliser des chemins absolus. Le processus doit démarrer depuis un environnement
où le package est installé en mode éditable.

## Parcours recommandé

1. `describe_api` pour connaître les outils et leur maturité ;
2. `plan_experiment` pour rendre explicites modèle, protocole et signaux ;
3. confirmation humaine des valeurs proposées ;
4. `run_simulation` ;
5. lecture du contrat, des hypothèses, erreurs et diagnostics ;
6. comparaison ou sensibilité seulement sur des scénarios homogènes.

## Maturité

- `core` : parcours prioritaire revu et documenté ;
- `experimental` : exploration disponible, preuve insuffisante pour une
  décision d’ingénierie ;
- `legacy` : compatibilité temporaire, hors parcours recommandé.

Chaque réponse MCP rappelle sa maturité et son domaine de validité.

## Dépannage

- erreur d’import : réinstaller avec `.venv/bin/python -m pip install -e .` ;
- chemin introuvable : utiliser les chemins absolus dans le client ;
- outil absent : appeler `describe_api` et vérifier sa maturité ;
- erreur de validation : corriger les unités, bornes ou noms de presets ;
- résultat inattendu : exécuter le même cas via l’API Python et inspecter
  `SimulationRun`.

Les implémentations sont sous `src/battery_sim/interfaces/mcp/`. Le fichier
`mcp_server.py` de la racine est uniquement un lanceur compatible.
