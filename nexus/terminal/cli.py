import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Enforce project root in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from nexus.memory.networkx_store import NetworkXGraphStore
from nexus.memory.chromadb_store import ChromaDBStore
from nexus.memory.hybrid import HybridMemory
from nexus.llm.client import LLMClient
from nexus.graph import create_nexus_graph
from nexus.loops.distillation import DistillationLoop
from nexus.loops.oubli import OubliLoop

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    load_dotenv(os.path.join(project_root, ".env"), override=True)
    
    # Configure workspace persistence directories
    storage_dir = os.path.join(os.getcwd(), ".nexus_storage")
    os.makedirs(storage_dir, exist_ok=True)
    
    graph_path = os.path.join(storage_dir, "graph.json")
    chroma_path = os.path.join(storage_dir, "chromadb")
    
    # Instantiate concrete stores (ChromaDB and NetworkXGraphStore)
    graph_store = NetworkXGraphStore(filepath=graph_path)
    vector_store = ChromaDBStore(persist_directory=chroma_path)
    
    # Coordinate them via HybridMemory (Dependency Injection)
    memory = HybridMemory(graph_store=graph_store, vector_store=vector_store)
    
    # Instantiate LLM Client (autodetecting MiniMax parameters from .env)
    llm_client = LLMClient()
    
    # Compile the LangGraph workflow
    graph = create_nexus_graph(memory=memory, llm_client=llm_client)
    
    # Initialize background worker loops
    distill_loop = DistillationLoop(memory=memory, llm_client=llm_client)
    oubli_loop = OubliLoop(memory=memory)

    print("=" * 70)
    print("                 TERMINAL NEXUS : SYSTEME COGNITIF MPE                 ")
    print("=" * 70)
    print(" Instructions :")
    print("  - Tapez vos requêtes normales pour dialoguer avec Nexus.")
    print("  - Entrez '/diag' pour basculer en Mode Diagnostic (Vue du graphe).")
    print("  - Entrez '/gov'  pour basculer en Mode Gouvernance (Human-in-the-loop).")
    print("  - Entrez '/exit' pour quitter le terminal.")
    print("=" * 70)

    mode = "INTERACTION"
    thread_id = "nexus_main_thread"

    while True:
        try:
            prompt_str = f"[{mode}] Nexus > "
            user_input = input(prompt_str).strip()
            
            if not user_input:
                continue

            if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                print("Fermeture du Terminal Nexus. Au revoir!")
                break

            # Handle system commands
            if user_input.lower() == "/diag":
                run_diagnostic_menu(graph_store)
                continue
            elif user_input.lower() == "/gov":
                run_governance_menu(memory, distill_loop, oubli_loop)
                continue

            # Standard Interaction Mode through LangGraph orchestrator
            print("\n[Orchestrateur] Traitement de la requête dans la machine à états LangGraph...")
            config = {"configurable": {"thread_id": thread_id}}
            initial_state = {
                "messages": [{"role": "user", "content": user_input}],
                "current_query": user_input,
                "retrieved_context": "",
                "sufficiency_score": 1.0,
                "missing_knowledge_log": [],
                "audit_trail": [],
                "response": ""
            }

            final_state = graph.invoke(initial_state, config=config)
            
            # Print response
            print("\n" + "-" * 50)
            print("REPONSE NEXUS :")
            print(final_state.get("response", "Aucune réponse générée."))
            print("-" * 50)
            
            # Print audit trail (provenance)
            print("\nJOURNAL D'AUDIT (Chaîne de provenance) :")
            for step in final_state.get("audit_trail", []):
                print(f"  {step}")
            print("-" * 50 + "\n")

        except KeyboardInterrupt:
            print("\nInterruption détectée. Retour au menu.")
        except Exception as e:
            print(f"\nErreur lors du traitement de la requête : {str(e)}")

def run_diagnostic_menu(graph_store: NetworkXGraphStore):
    print("\n" + "=" * 60)
    print("                  MODE DIAGNOSTIC (Insight View)              ")
    print("=" * 60)
    
    nodes = graph_store.list_nodes()
    edges = graph_store.list_edges()
    
    print(f"Statistiques globales :")
    print(f" - Nombre de Noeuds sémantiques (Entités) : {len(nodes)}")
    print(f" - Nombre de Relations (Arêtes) : {len(edges)}")
    print("\n--- NOEUDS DE CONNAISSANCES ---")
    if not nodes:
        print("  Graphe sémantique vide.")
    for node in nodes:
        # Hide internal properties from simple list
        props = ", ".join(
            f"{k}: {v}" for k, v in node.properties.items() 
            if k not in ("text", "source", "access_count", "last_accessed")
        )
        prop_str = f" ({props})" if props else ""
        print(
            f"  * [{node.type}] ID: {node.id}{prop_str} "
            f"-> \"{node.properties.get('text', '')}\" [T={node.timestamp.isoformat()}]"
        )
        
    print("\n--- RELATIONS ET LIENS ---")
    if not edges:
        print("  Aucun lien sémantique enregistré.")
    for edge in edges:
        props = f" ({edge.properties})" if edge.properties else ""
        print(f"  * {edge.source} --({edge.type})--> {edge.target}{props}")
        
    print("=" * 60 + "\n")

def run_governance_menu(memory: HybridMemory, distill_loop: DistillationLoop, oubli_loop: OubliLoop):
    while True:
        print("\n" + "=" * 60)
        print("               MODE GOUVERNANCE (Human-in-the-loop)           ")
        print("=" * 60)
        print(" Actions manuelles disponibles :")
        print("  1. Ingestion forcée d'un fait (Node + Vector)")
        print("  2. Création manuelle d'une relation (Edge)")
        print("  3. Suppression d'un fait (Oubli forcé)")
        print("  4. Déclencher la Distillation (Consolidation cognitive)")
        print("  5. Déclencher le Nettoyage (Oubli LRU / Obsolescence)")
        print("  6. Retour au Mode Interactif")
        print("=" * 60)
        
        choice = input("Sélectionnez une option (1-6) > ").strip()
        
        if choice == "1":
            node_id = input("ID de l'entité (ex: john_doe) > ").strip()
            node_type = input("Type d'entité (ex: Person) > ").strip()
            text = input("Enoncé du fait à stocker > ").strip()
            ts_input = input("Date ISO (ex: 2026-06-01T12:00:00, optionnel - Enter pour UTC actuel) > ").strip()
            
            try:
                timestamp = datetime.fromisoformat(ts_input) if ts_input else datetime.utcnow()
                res = memory.add_fact(
                    node_id=node_id,
                    node_type=node_type,
                    text=text,
                    timestamp=timestamp,
                    source="manual_governance"
                )
                print(f"\n[Succès] Statut: {res['status']}. Détails: {res['audit']}")
            except ValueError:
                print("Format de date invalide.")
            
        elif choice == "2":
            source = input("ID Noeud Source > ").strip()
            target = input("ID Noeud Cible > ").strip()
            rel_type = input("Type de relation (ex: CONNAIT, APPARTIENT_A) > ").strip()
            memory.add_relationship(
                source_id=source,
                target_id=target,
                rel_type=rel_type,
                timestamp=datetime.utcnow()
            )
            print(f"\n[Succès] Relation créée : {source} --({rel_type})--> {target}")
            
        elif choice == "3":
            node_id = input("ID du noeud à effacer > ").strip()
            memory.graph_store.delete_node(node_id)
            memory.vector_store.delete(node_id)
            print(f"\n[Succès] Le noeud '{node_id}' a été retiré de la mémoire sémantique et vectorielle.")
            
        elif choice == "4":
            print("\n[Distillation] Consolidation cognitive en cours...")
            res = distill_loop.run_distillation()
            print(f"Statut : {res['status']}. Message : {res.get('message', '')}")
            if res.get("audit_log"):
                print("Journal d'audit de Distillation :")
                for log in res["audit_log"]:
                    print(f" - {log}")
                    
        elif choice == "5":
            print("\n[Forgetting] Lancement des règles d'hygiène de mémoire...")
            sub_choice = input("  Sélection : [1] LRU (limite de taille)  [2] Obsolescence temporelle > ").strip()
            if sub_choice == "1":
                limit = input("  Nombre max de faits à conserver > ").strip()
                try:
                    res = oubli_loop.enforce_lru(int(limit))
                    print(f"  Résultat : {res['status']}. {res['message']}")
                except ValueError:
                    print("  Limite invalide.")
            elif sub_choice == "2":
                age = input("  Age maximum autorisé pour les faits (en jours) > ").strip()
                try:
                    res = oubli_loop.enforce_temporal_decay(int(age))
                    print(f"  Résultat : {res['status']}. {res['message']}")
                except ValueError:
                    print("  Age invalide.")
                    
        elif choice == "6":
            print("Retour au mode interactif.")
            break
        else:
            print("Option invalide. Veuillez saisir un nombre entre 1 et 6.")

if __name__ == "__main__":
    main()
