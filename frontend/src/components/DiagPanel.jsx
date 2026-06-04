import React, { useState, useEffect } from 'react';

export default function DiagPanel() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [deficiencies, setDeficiencies] = useState([]);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resolvingNodeId, setResolvingNodeId] = useState(null);
  const [resolveText, setResolveText] = useState('');
  const [resolveType, setResolveType] = useState('Concept');

  const fetchData = async () => {
    setLoading(true);
    try {
      // Fetch graph nodes & edges
      const graphRes = await fetch('http://localhost:8000/api/graph');
      const gData = await graphRes.json();
      setGraphData(gData);

      // Fetch deficiencies (Unknown shell nodes)
      const defRes = await fetch('http://localhost:8000/api/deficiencies');
      const dData = await defRes.json();
      setDeficiencies(dData.deficiencies || []);
    } catch (e) {
      console.error("Failed to load diagnostic data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleResolveGap = async (nodeId) => {
    if (!resolveText.trim()) return;

    try {
      const response = await fetch('http://localhost:8000/api/facts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_id: nodeId,
          node_type: resolveType,
          text: resolveText,
          source: 'diagnostic_gap_resolver'
        })
      });

      if (response.ok) {
        setResolvingNodeId(null);
        setResolveText('');
        fetchData(); // Refresh graph and deficiencies
      } else {
        alert("Erreur lors de la résolution de la carence.");
      }
    } catch (err) {
      alert("Erreur réseau : " + err.message);
    }
  };

  // Node coloring function
  const getNodeColor = (type) => {
    switch (type.toUpperCase()) {
      case 'PERSON': return '#ec4899'; // pink
      case 'COMPANY': return '#06b6d4'; // cyan
      case 'FACT':
      case 'FACTUALSTATEMENT': return '#8b5cf6'; // purple
      case 'UNKNOWN': return '#f59e0b'; // orange (carence)
      default: return '#10b981'; // green
    }
  };

  // Layout calculations for nodes positioned on a circle
  const centerX = 280;
  const centerY = 190;
  const radius = 120;
  const nodeRadius = 15;

  const positionedNodes = graphData.nodes.map((node, index) => {
    const angle = graphData.nodes.length > 1 
      ? (index / graphData.nodes.length) * 2 * Math.PI 
      : 0;
    const x = graphData.nodes.length > 1 ? centerX + radius * Math.cos(angle) : centerX;
    const y = graphData.nodes.length > 1 ? centerY + radius * Math.sin(angle) : centerY;
    return { ...node, x, y };
  });

  const nodeMap = positionedNodes.reduce((acc, node) => {
    acc[node.id] = node;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', gap: '20px' }}>
      {/* Left panel: Deficiencies */}
      <div className="glass" style={{ width: '300px', display: 'flex', flexDirection: 'column', padding: '20px', overflow: 'hidden' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '14px' }} className="gradient-text">Carences de Mémoire</h3>
        
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {deficiencies.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              ✓ Aucune carence identifiée. La cohérence relationnelle est optimale.
            </div>
          ) : (
            deficiencies.map((nodeId, idx) => (
              <div 
                key={idx} 
                className="glass" 
                style={{ 
                  padding: '12px', 
                  border: '1px solid rgba(245, 158, 11, 0.25)', 
                  background: 'rgba(245, 158, 11, 0.03)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--warning)' }}>⚠️ Noeud Orphelin</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>ID: {nodeId}</span>
                </div>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  Ce concept est lié par des relations mais n'a pas de contenu sémantique.
                </div>
                
                {resolvingNodeId === nodeId ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                    <input 
                      type="text" 
                      placeholder="Type d'entité (ex: Person)" 
                      value={resolveType} 
                      onChange={(e) => setResolveType(e.target.value)}
                      style={{ fontSize: '0.8rem', padding: '6px 10px' }}
                    />
                    <textarea 
                      placeholder="Contenu du fait sémantique..."
                      value={resolveText}
                      onChange={(e) => setResolveText(e.target.value)}
                      rows={2}
                      style={{ fontSize: '0.8rem', padding: '6px 10px', resize: 'none' }}
                    />
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button 
                        onClick={() => handleResolveGap(nodeId)}
                        className="glowing-btn"
                        style={{ flex: 1, padding: '4px 0', fontSize: '0.8rem', borderRadius: '4px' }}
                      >
                        Enregistrer
                      </button>
                      <button 
                        onClick={() => setResolvingNodeId(null)}
                        style={{ flex: 1, padding: '4px 0', fontSize: '0.8rem', borderRadius: '4px', background: 'none', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', cursor: 'pointer' }}
                      >
                        Annuler
                      </button>
                    </div>
                  </div>
                ) : (
                  <button 
                    onClick={() => setResolvingNodeId(nodeId)}
                    className="glowing-btn"
                    style={{ padding: '6px 0', fontSize: '0.82rem', borderRadius: '6px', marginTop: '4px' }}
                  >
                    Résoudre la carence
                  </button>
                )}
              </div>
            ))
          )}
        </div>
        <button 
          onClick={fetchData}
          style={{ width: '100%', padding: '10px 0', background: 'none', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', borderRadius: '8px', cursor: 'pointer', marginTop: '10px', fontSize: '0.9rem', fontWeight: 500 }}
        >
          🔄 Rafraîchir
        </button>
      </div>

      {/* Right panel: Knowledge Graph Visualisation */}
      <div className="glass" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '20px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }} className="gradient-text">Graphe des Connaissances</h3>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Cliquez sur un nœud pour afficher ses propriétés</span>
        </div>

        {/* SVG Drawing Area */}
        <div style={{ flex: 1, background: 'rgba(0, 0, 0, 0.25)', border: '1px solid var(--border-color)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}>
          {graphData.nodes.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
              Base de connaissances vide. Veuillez ingérer des faits.
            </div>
          ) : (
            <svg width="100%" height="100%" viewBox="0 0 560 380" style={{ display: 'block' }}>
              {/* Arrowhead marker definition */}
              <defs>
                <marker 
                  id="arrow" 
                  viewBox="0 0 10 10" 
                  refX="23" 
                  refY="5" 
                  markerWidth="5" 
                  markerHeight="5" 
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.3)" />
                </marker>
              </defs>

              {/* Draw Edges */}
              {graphData.edges.map((edge, idx) => {
                const sourceNode = nodeMap[edge.source];
                const targetNode = nodeMap[edge.target];
                if (!sourceNode || !targetNode) return null;

                return (
                  <g key={`edge-${idx}`}>
                    <line 
                      x1={sourceNode.x} 
                      y1={sourceNode.y} 
                      x2={targetNode.x} 
                      y2={targetNode.y} 
                      stroke="rgba(255, 255, 255, 0.15)"
                      strokeWidth="1.5"
                      markerEnd="url(#arrow)"
                    />
                    {/* Tiny edge label */}
                    <text
                      x={(sourceNode.x + targetNode.x) / 2}
                      y={(sourceNode.y + targetNode.y) / 2 - 4}
                      fill="var(--text-secondary)"
                      fontSize="8"
                      textAnchor="middle"
                      style={{ pointerEvents: 'none', background: '#0a0b12' }}
                    >
                      {edge.type}
                    </text>
                  </g>
                );
              })}

              {/* Draw Nodes */}
              {positionedNodes.map((node, idx) => (
                <g 
                  key={`node-${idx}`} 
                  style={{ cursor: 'pointer' }}
                  onClick={() => setHoveredNode(hoveredNode === node ? null : node)}
                >
                  <circle 
                    cx={node.x} 
                    cy={node.y} 
                    r={nodeRadius} 
                    fill={getNodeColor(node.type)}
                    stroke="rgba(255,255,255,0.8)"
                    strokeWidth={hoveredNode?.id === node.id ? 2.5 : 1}
                    style={{ transition: 'all 0.2s ease' }}
                  />
                  <text 
                    x={node.x} 
                    y={node.y + 4} 
                    fill="#fff" 
                    fontSize="9" 
                    fontWeight="600" 
                    textAnchor="middle"
                    style={{ pointerEvents: 'none' }}
                  >
                    {node.id.substring(0, 3).toUpperCase()}
                  </text>
                  <text 
                    x={node.x} 
                    y={node.y + 26} 
                    fill="var(--text-primary)" 
                    fontSize="9.5" 
                    textAnchor="middle"
                    style={{ pointerEvents: 'none' }}
                  >
                    {node.id}
                  </text>
                </g>
              ))}
            </svg>
          )}

          {/* Floater Node Tooltip details */}
          {hoveredNode && (
            <div 
              className="glass" 
              style={{
                position: 'absolute',
                bottom: '12px',
                left: '12px',
                right: '12px',
                padding: '12px 16px',
                background: 'rgba(10, 11, 18, 0.95)',
                border: '1px solid var(--primary)',
                animation: 'fadeIn 0.2s ease-out'
              }}
            >
              <style>{`
                @keyframes fadeIn {
                  from { opacity: 0; transform: translateY(10px); }
                  to { opacity: 1; transform: translateY(0); }
                }
              `}</style>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: getNodeColor(hoveredNode.type) }}>
                  [{hoveredNode.type.toUpperCase()}] {hoveredNode.id}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Ingest: {new Date(hoveredNode.timestamp).toLocaleString()}
                </span>
              </div>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: '1.4' }}>
                {hoveredNode.properties.text || "Aucun fait textuel lié."}
              </p>
              {hoveredNode.properties.source && (
                <div style={{ fontSize: '0.78rem', color: 'var(--secondary)', marginTop: '4px', fontWeight: 500 }}>
                  Source : {hoveredNode.properties.source}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
