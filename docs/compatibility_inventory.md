# Inventaire de compatibilité

Cet inventaire empêche les couches transitoires de devenir permanentes.

| Élément actuel | Raison | Décision |
|---|---|---|
| `core/application_services.py` | Réexport des services extraits | Supprimer pendant la restructuration après migration des imports |
| `core/investigation_tools.py` | Réexports et contrats historiques mélangés | Séparer contrats utiles et supprimer les réexports |
| `core/parameter_sweep.py` | Façade typée au-dessus du service canonique | Déplacer les contrats utiles dans `application/sweep` puis supprimer |
| `core/agent_api.py` | Façade historique Python/LLM et composition du backend | Remplacer par une façade Python courte hors du core |
| `interface/agent_api.py` | Réexport du `core.agent_api` | Remplacer par le point d'entrée public final |
| helpers privés de `PyBaMMBackend` | Compatibilité avec anciens tests/appels | Supprimer après migration vers l'adaptateur restructuré |
| `Environment.temperature_C` et ancien alias ambiant | Ancien contrat de température | Conserver jusqu'à migration des appels, puis retirer explicitement |
| booléens historiques de `DegradationConfig` | Ancienne sélection des sous-modèles | Convertir vers une configuration explicite puis retirer |
| alias `Result.energy_delivered()` | Ancien nom de résultat | Remplacer par le vocabulaire canonique |
| `create_simulation_run()` | Adaptation d'un `Result` nu | Supprimer lorsque tous les chemins retournent directement `SimulationRun` |
| outils véhicule | Fonctionnalités générées hors périmètre actuel | Déplacer sous `experimental`, sans import depuis le noyau |

## Règle de suppression

Chaque élément sera supprimé dans un commit dédié pendant la phase de
restructuration. Un shim ne peut survivre à cette phase que si un consommateur
externe réel est identifié.
