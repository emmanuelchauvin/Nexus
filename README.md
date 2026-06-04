# Nexus : Mémoire Persistante Évolutive (MPE)

Nexus est un agent cognitif autonome doté d'une **Mémoire Persistante Évolutive (MPE)** orchestrée par une machine à états **LangGraph**. En rupture avec le paradigme RAG statique classique, Nexus intègre et consolide de nouvelles connaissances en continu, arbitre dynamiquement les contradictions temporelles et maintient une hygiène cognitive autonome via des boucles de contrôle dédiées.

---

## 🚀 Fonctionnalités Clés

1. **Plasticité Cognitive (*Non-Gradient Adaptation*)** : Intégration de connaissances en continu et invalidation des faits obsolètes sans réentraînement de l'architecture LLM.
2. **Mémoire Hybride Temporelle-Sémantique** : Combinaison d'une base vectorielle (`ChromaDB`) pour la similarité sémantique et d'un graphe relationnel (`NetworkX`) pour modéliser le contexte connexe et les entités.
3. **Arbitrage Temporel Intègre** : Si deux faits se contredisent, Nexus applique une résolution chronologique : l'information la plus récente ($T_2 > T_1$) l'emporte, et le changement est tracé dans le journal d'audit.
4. **Les 3 Boucles Cognitives** :
   - **Boucle de Diagnostic** : Évalue la suffisance du contexte pour répondre à une question. En cas de carence, le flux bifurque vers un nœud d'alerte.
   - **Boucle de Distillation** : Consolide, fusionne les entités redondantes et crée de nouveaux liens logiques.
   - **Boucle d'Oubli** : Élimine les connaissances obsolètes ou les moins consultées (politiques LRU et expiration temporelle) pour éviter la saturation.
5. **Terminal Nexus Multi-mode** : Interface interactive offrant un mode discussion classique avec chaîne de preuves, un mode diagnostic visuel du graphe et un mode gouvernance (*Human-in-the-loop*).
6. **Ingestion Documentaire (PDF)** : Extraction automatique de texte à partir de documents PDF, découpage en fragments sémantiques séquentiels liés (`PART_OF`, `NEXT`) et indexation directe dans la mémoire hybride (vectorielle + graphe).

---

## 🛠️ Structure du Projet

```text
c:\Devs\Memoire-evolutive\
├── requirements.txt              # Dépendances du projet
├── README.md                     # Documentation générale
├── .env                          # Configuration des clés d'API (non versionné)
├── backend/
│   └── app.py                    # Serveur FastAPI pour l'API REST
├── frontend/                     # Interface Graphique ReactJS
│   ├── package.json              # Dépendances NPM du frontend
│   ├── src/
│   │   ├── App.jsx               # Composant principal du Dashboard (navigation par onglets)
│   │   ├── index.css             # Styles CSS (Design Glassmorphism et Thème sombre)
│   │   └── components/
│   │       ├── ChatPanel.jsx     # Console de conversation avec audit trail (LangGraph logs)
│   │       ├── DiagPanel.jsx     # Visualisation interactive du graphe (SVG) et diagnostic
│   │       └── GovPanel.jsx      # Ingestion manuelle, règles et table d'audit Semgrep
├── nexus/
│   ├── __init__.py
│   ├── state.py                  # Schéma d'état AgentState de la machine LangGraph
│   ├── graph.py                  # Orchestrateur de nœuds et compilation du graphe
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── interfaces.py         # Interfaces abstraites (GraphStore, VectorStore)
│   │   ├── networkx_store.py     # Implémentation graphe NetworkX + Persistance JSON
│   │   ├── chromadb_store.py     # Implémentation vectorielle ChromaDB
│   │   └── hybrid.py             # Coordinateur Hybride et Arbitrage Temporel
│   ├── loops/
│   │   ├── __init__.py
│   │   ├── diagnostic.py         # Évaluation de suffisance (Diagnostic Loop)
│   │   ├── distillation.py       # Tâches de fusion et d'invariants (Distillation Loop)
│   │   └── oubli.py              # Règles d'hygiène et capacité LRU (Oubli Loop)
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py             # Client d'API OpenAI/MiniMax encapsulé et sécurisé
│   └── terminal/
│       ├── __init__.py
│       └── cli.py                # Terminal Interactif CLI
└── tests/
    ├── conftest.py               # Fixtures pytest et InMemoryVectorStore déterministe
    ├── test_connection_minimax.py# Script de diagnostic de connexion LLM
    ├── test_temporal_conflict.py # Tests de résolution de conflits chronologiques
    ├── test_audit.py             # Tests de génération de chaîne de provenance
    ├── test_diagnostic.py        # Tests de détection de carence de mémoire
    └── test_resilience.py        # Tests de saturation de mémoire et oubli LRU
```

---

## ⚙️ Installation et Configuration

### 1. Prérequis
- Python 3.10+
- Node.js (avec npm) pour exécuter l'interface graphique
- Un environnement virtuel configuré dans le dossier `.venv`

### 2. Configuration des variables d'environnement
Créez un fichier `.env` à la racine du projet avec les clés d'accès de votre fournisseur LLM (le modèle de raisonnement de pointe **MiniMax-M3** est configuré par défaut) :
```env
MINIMAX_API_KEY=sk-api-...
OPENAI_API_KEY=${MINIMAX_API_KEY}
OPENAI_BASE_URL=https://api.minimax.io/v1
MINIMAX_MODEL=MiniMax-M3
```

### 3. Installation des dépendances
Activez votre environnement virtuel et installez les librairies requises pour le noyau Python et le backend :
```bash
.venv/Scripts/pip install -r requirements.txt
```

Pour installer les dépendances de l'interface graphique :
```bash
npm --prefix frontend install
```

---

## 💻 Utilisation du Terminal Nexus

Lancez l'interface interactive en ligne de commande :
```bash
.venv/Scripts/python -m nexus.terminal.cli
```

### Les différents modes du Terminal :
- **Mode Interaction (par défaut)** : Posez vos questions normalement. L'agent répondra en utilisant sa mémoire contextuelle et affichera la **Chaîne de Provenance (Audit Trail)** détaillant précisément les sources et les timestamps de chaque information exploitée.
- **Mode Diagnostic (`/diag`)** : Affiche les statistiques globales de la mémoire, la liste des concepts sémantiques enregistrés et toutes les relations actives du graphe de connaissances.
- **Mode Gouvernance (`/gov`)** : Offre un contrôle manuel (*Human-in-the-loop*) pour forcer l'ingestion de faits, créer des liens logiques, supprimer des nœuds, ou déclencher manuellement les boucles de **Distillation** et d'**Oubli**.

---

## 🖥️ Utilisation de l'Interface Graphique (Web Dashboard)

Le projet intègre une interface graphique moderne structurée en trois onglets principaux :
- **💬 Interaction Chat** : Permet de discuter avec Nexus et de consulter en temps réel la **Chaîne de Provenance (Audit Trail)** détaillant les sources exploitées.
- **📊 Diagnostic Graphe** : Affiche une vue interactive du graphe sémantique en SVG, ainsi que la liste des concepts détectés comme "carences" (référencés sans type précis).
- **🛡️ Gouvernance & Boucles** : Offre des contrôles d'administration pour injecter des faits ou relations, **importer un document PDF par glisser-déposer**, exécuter manuellement les boucles de distillation/oubli LRU/obsolescence, et auditer les alertes de sécurité ignorées.

### 1. Lancer le serveur Backend (FastAPI)
Exécutez la commande suivante à la racine du projet :
```bash
.venv/Scripts/python -m uvicorn backend.app:app --reload --port 8000
```
Le backend sera disponible à l'adresse [http://localhost:8000](http://localhost:8000).

### 2. Lancer le client Frontend (React / Vite)
Exécutez la commande suivante à la racine du projet pour lancer le serveur de développement :
```bash
npm --prefix frontend run dev
```
L'interface sera accessible par défaut à l'adresse [http://localhost:5173](http://localhost:5173).

---

## 🔒 Sécurité et Audit (Conformité SecureCoder)

Le code respecte strictement les bonnes pratiques de sécurité :
- Les appels d'API vers OpenAI/MiniMax incluent un identifiant unique `user` pour faciliter le suivi des abus de service (CWE-778).
- Tous les retours d'API sont enveloppés dans des blocs de gestion d'erreur robustes et vérifient l'état de refus du modèle (`refusal`) avant d'accéder au contenu de la réponse (CWE-252).
- Le rapport d'audit de sécurité et d'analyse PoC est consigné dans le document de suivi de projet.

---

## 🧪 Lancement des Tests Unitaires

Pour valider l'intégrité fonctionnelle et les règles de mémoire, lancez `pytest` :
```bash
.venv/Scripts/python -m pytest -v
```
Les tests unitaires s'exécutent de façon isolée et déterministe grâce à une implémentation mockée en mémoire de la base vectorielle.
