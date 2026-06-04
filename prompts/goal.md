# Projet : Agent à Mémoire Persistante Évolutive (MPE)

## Vision

Développer un agent autonome capable d'une *"continuité d'existence"* à travers les sessions, les lectures de documents et les interactions, en rupture avec le paradigme du RAG statique.

## Objectifs Clés

- **Plasticité Cognitive** : Intégrer de nouvelles connaissances et invalider les informations obsolètes sans réentraînement (*Non-Gradient Adaptation*).
- **Autonomie de Gestion** : L'agent conserve sa mémoire (*hygiène cognitive*) via des cycles de distillation et de nettoyage.
- **Intégrité Temporelle** : Arbitrer les contradictions entre informations à travers le temps en utilisant le horodatage (*timestamping*) et la source de vérité la plus récente.
- **Auditabilité des Workflow** : Capacité à fournir une chaîne de preuve (*provenance*) pour chaque décision critique.

## KPIs de Succès

| Indicateur | Description |
| --- | --- |
| **Indice de Cohérence Temporelle** | Capacité à détecter et résoudre une contradiction entre deux informations à $T_1$ et $T_2$. |
| **Taux de rétention critique** | Capacité à restituer une information après $t$ périodes d'inactivité. |
| **Score d'Auditabilité** | Taux de succès de l'agent à justifier une réponse en citant la chaîne de preuves (*provenance*). |