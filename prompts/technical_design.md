# Design Technique : Système de Mémoire Persistante Évolutive (Architecture Modulaire)

## 1\. Architecture d'Orchestration (LangGraph)

# 

L'agent est conçu comme une application orchestrée par **LangGraph**, favorisant une séparation claire entre la logique de décision (LLM) et la gestion de l'état (State Management).

### Structure du Graphe

# 

-   **Orchestrateur (Supervisor) :** Point d'entrée unique qui route les requêtes vers les sous-modules appropriés.
    
-   **Nodes Modulaires :**
    
    -   **Inference Node :** Gère la communication avec le LLM.
        
    -   **Memory Router :** Détermine si une information doit être stockée, résumée ou si une recherche est nécessaire.
        
    -   **Action/Tools Nodes :** Exécute les recherches de documents (RAG) et les mises à jour de la mémoire.
        
-   **State Management :** L'état global est persistant (via `Checkpoints`), permettant de conserver le contexte mental de l'agent sur le long terme, indépendamment des sessions utilisateur.
    

## 2\. Cycle de Vie de la Mémoire (Les 3 Boucles)

# 

Les boucles de mémoire sont implémentées comme des services asynchrones ou des nœuds de contrôle indépendants :

1.  **Boucle de Distillation (Background Worker) :**
    
    -   Rôle : Analyse les logs d'interactions et les nouveaux documents pour extraire des invariants sémantiques.
        
    -   Implémentation : Tâche asynchrone qui condense les informations pour mettre à jour le graphe de connaissances global.
        
2.  **Boucle de Diagnostic (Router Logic) :**
    
    -   Rôle : Évalue en temps réel si le contexte fourni est suffisant pour répondre à la requête utilisateur.
        
    -   Implémentation : Nœud de conditionnement dans le graphe. Si le score de pertinence est insuffisant, le graphe redirige vers une tâche de recherche profonde.
        
3.  **Boucle d'Oubli (Cleanup Service) :**
    
    -   Rôle : Maintien de l'hygiène cognitive.
        
    -   Implémentation : Politique de rétention basée sur la fréquence d'accès (LRU) ou l'obsolescence temporelle.
        

## 3\. Interface de Pilotage : Le "Terminal Nexus"

# 

Pour interagir avec le système MPE, l'interface utilisateur est conçue comme un **Terminal Nexus** :

-   **Mode Interaction :** Permet à l'utilisateur de poser des questions directes à l'agent ("Nexus"). L'agent répond en puisant dans sa mémoire persistante consolidée.
    
-   **Mode Diagnostic (Insight View) :** Permet de visualiser les "carences" de mémoire identifiées par le système et de consulter le graphe de connaissances actuel.
    
-   **Mode Gouvernance (Human-in-the-loop) :** Possibilité pour l'utilisateur de valider, corriger ou invalider des connexions sémantiques au sein du graphe pour guider l'auto-évolution de l'agent.
    

## 4\. Stratégie d'Implémentation & Scalabilité (Approche "Vibe Coding")

# 

Pour maximiser la vélocité de développement tout en assurant une robustesse de niveau production :

-   **Orchestration :** LangGraph couplé à `PostgresSaver` pour une gestion native de la persistance de l'état du graphe.
    
-   **Couche de Persistance Unifiée (PostgreSQL + pgvector) :**
    
    -   **Approche :** Utiliser PostgreSQL comme source unique de vérité.
        
    -   **Avantage :** Gestion unifiée des Checkpoints (LangGraph), des vecteurs (pgvector) et des relations (via extensions graphe ou structures JSONB).
        
-   **Prototypage Rapide (Local-First) :**
    
    -   Utilisation de `ChromaDB` (in-memory) et `NetworkX` pour le développement local rapide.
        
    -   Bascule transparente vers une instance PostgreSQL managée (ex: Supabase, Neon) pour le déploiement.
        
-   **Cloud-Native & Observabilité :**
    
    -   Architecture découplée via micro-services.
        
    -   Monitoring orienté "décisions agentiques" pour tracer l'évolution de la mémoire.
        
-   **Interopérabilité :** API-first permettant une intégration native dans les systèmes bancaires existants.