# Décisions de reprise

Ce document conserve les décisions prises avec le propriétaire du projet. Il ne
remplace pas les preuves scientifiques propres à chaque étude.

## Produit

- outil interne pour un ingénieur test et validation EV ;
- aide à la calibration BMS par exploration explicable et précise ;
- utilisateur unique avec quelques heures de revue disponibles par semaine ;
- API Python prioritaire, MCP expérimental ;
- PyBaMM comme unique moteur ;
- véhicule hors périmètre, pack conservé ;
- NMC avant LFP ;
- outils historiques conservés mais isolés comme expérimentaux.

## Questions cibles

- influence de la tension maximale de charge sur le vieillissement ;
- dispersion attendue et cellule limitante dans un pack 96s2p ;
- échauffement pendant un profil de mission ;
- maintien de la température cellule sous 55 °C ;
- génération de données pour évaluer la précision d'un modèle 2RC.

## Physique

- électrothermique dès le premier cas utile ;
- décharge CC mesurée avant profil de mission ;
- vieillissement en cyclage avant vieillissement calendaire ;
- comparaison relative avant prédiction absolue de vieillissement ;
- modèle le plus simple par défaut, plus complexe sur demande ou nécessité ;
- courant de décharge négatif dans le contrat public cible ;
- résultats classés comme simulés, dérivés, supposés ou mesurés ;
- entrées impossibles bloquantes, extrapolations accompagnées d'avertissements.

## Validation

- données d'essai CSV ou NDJSON avec métadonnées ;
- courant pack, tension et température disponibles pour le premier profil NMC ;
- préconditionnement, température ambiante et position capteur disponibles ;
- cellule testée dans un module ;
- métriques initiales : erreur RMS/max de tension, capacité, instant de coupure,
  température maximale, élévation thermique et conservation charge/énergie ;
- seuils d'acceptation fixés après observation des premières données.

## Développement

- état interrompu préservé dans un checkpoint Git non audité ;
- changements petits, simples et commités séparément ;
- discussion avant rupture d'API ou changement physique ;
- conservation des tests scientifiquement ou logiciellement pertinents.
