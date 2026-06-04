import React, { useState, useEffect } from 'react';

export default function GovPanel() {
  // Fact ingestion fields
  const [nodeId, setNodeId] = useState('');
  const [nodeType, setNodeType] = useState('Person');
  const [factText, setFactText] = useState('');
  const [factSource, setFactSource] = useState('');
  
  // Relation ingestion fields
  const [sourceId, setSourceId] = useState('');
  const [targetId, setTargetId] = useState('');
  const [relType, setRelType] = useState('CONNECTED_TO');

  // Loop settings
  const [maxNodes, setMaxNodes] = useState(10);
  const [maxAge, setMaxAge] = useState(30);

  // Console output log
  const [consoleLogs, setConsoleLogs] = useState(['Console d\'administration prête...']);

  // Ignored security vulnerability list
  const [ignoredList, setIgnoredList] = useState([]);

  // PDF upload fields
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const addLog = (msg) => {
    const timestamp = new Date().toLocaleTimeString();
    setConsoleLogs(prev => [`[${timestamp}] ${msg}`, ...prev]);
  };

  const handleUploadPDF = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setIsUploading(true);
    addLog(`Upload PDF: Envoi de '${selectedFile.name}' (${(selectedFile.size / 1024).toFixed(1)} KB)...`);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('http://localhost:8000/api/ingest/pdf', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      if (response.ok && data.success) {
        addLog(`PDF Ingest: Succès! ID du document: '${data.document_id}'. ${data.chunks_count} fragments ingérés.`);
        setSelectedFile(null);
      } else {
        addLog(`ERROR PDF Ingest: ${data.detail || 'Erreur inconnue'}`);
      }
    } catch (err) {
      addLog(`ERROR PDF Ingest Connection: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        setSelectedFile(file);
        addLog(`Fichier sélectionné par dépôt: ${file.name}`);
      } else {
        addLog(`Fichier ignoré (seuls les PDF sont acceptés)`);
      }
    }
  };

  const fetchSecurityAudits = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/security/ignored');
      const data = await res.json();
      setIgnoredList(data.entries || []);
    } catch (e) {
      console.error("Failed to load ignored registry:", e);
    }
  };

  useEffect(() => {
    fetchSecurityAudits();
  }, []);

  const handleIngestFact = async (e) => {
    e.preventDefault();
    if (!nodeId.trim() || !factText.trim()) return;

    try {
      const response = await fetch('http://localhost:8000/api/facts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_id: nodeId,
          node_type: nodeType,
          text: factText,
          source: factSource || 'web_governance'
        })
      });
      
      const data = await response.json();
      addLog(`Fact Ingest: ID='${nodeId}', Status=${data.status}. Details: ${data.audit}`);
      
      // Reset form
      setNodeId('');
      setFactText('');
      setFactSource('');
    } catch (err) {
      addLog(`ERROR Fact Ingest: ${err.message}`);
    }
  };

  const handleIngestRelation = async (e) => {
    e.preventDefault();
    if (!sourceId.trim() || !targetId.trim()) return;

    try {
      const response = await fetch('http://localhost:8000/api/relationships', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: sourceId,
          target_id: targetId,
          rel_type: relType
        })
      });
      
      const data = await response.json();
      if (data.success) {
        addLog(`Relation Created: '${sourceId}' --(${relType})--> '${targetId}'`);
        setSourceId('');
        setTargetId('');
      }
    } catch (err) {
      addLog(`ERROR Relation Ingest: ${err.message}`);
    }
  };

  const handleTriggerDistillation = async () => {
    addLog("Déclenchement manuel de la Distillation...");
    try {
      const response = await fetch('http://localhost:8000/api/distill', { method: 'POST' });
      const data = await response.json();
      if (data.status === 'success') {
        addLog(`Distillation Terminée. Fusions effectuées: ${data.merges_executed}. Arêtes créées: ${data.edges_added}.`);
        if (data.audit_log && data.audit_log.length > 0) {
          data.audit_log.forEach(log => addLog(` - ${log}`));
        }
      } else {
        addLog(`Distillation passée ou échouée: ${data.message || 'raison inconnue'}`);
      }
    } catch (err) {
      addLog(`ERROR Distillation: ${err.message}`);
    }
  };

  const handleTriggerLRU = async () => {
    addLog(`Déclenchement du nettoyage LRU (limite max = ${maxNodes})...`);
    try {
      const response = await fetch('http://localhost:8000/api/oubli/lru', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_nodes: parseInt(maxNodes) })
      });
      const data = await response.json();
      addLog(`LRU Cleanup: Status=${data.status}. Details: ${data.message}`);
      if (data.deleted_nodes && data.deleted_nodes.length > 0) {
        addLog(` Noeuds supprimés: [${data.deleted_nodes.join(', ')}]`);
      }
    } catch (err) {
      addLog(`ERROR LRU Cleanup: ${err.message}`);
    }
  };

  const handleTriggerDecay = async () => {
    addLog(`Déclenchement de l'obsolescence (âge max = ${maxAge} jours)...`);
    try {
      const response = await fetch('http://localhost:8000/api/oubli/decay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_age_days: parseInt(maxAge) })
      });
      const data = await response.json();
      addLog(`Decay Cleanup: Status=${data.status}. Details: ${data.message}`);
      if (data.deleted_nodes && data.deleted_nodes.length > 0) {
        addLog(` Noeuds supprimés par obsolescence: [${data.deleted_nodes.join(', ')}]`);
      }
    } catch (err) {
      addLog(`ERROR Decay Cleanup: ${err.message}`);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', gap: '20px', overflowY: 'auto', paddingRight: '6px' }}>
      
      {/* Top Section: Ingestion Forms */}
      <div style={{ display: 'flex', gap: '20px' }}>
        {/* Fact Ingestion */}
        <form onSubmit={handleIngestFact} className="glass" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }} className="gradient-text">Ingérer un Fait Sémantique</h3>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input 
              type="text" 
              placeholder="ID Unique (ex: acme_inc)" 
              value={nodeId}
              onChange={(e) => setNodeId(e.target.value)}
              style={{ flex: 1 }}
              required
            />
            <input 
              type="text" 
              placeholder="Type (ex: Company)" 
              value={nodeType}
              onChange={(e) => setNodeType(e.target.value)}
              style={{ width: '140px' }}
              required
            />
          </div>
          <textarea 
            placeholder="Énoncé du fait sémantique à indexer..." 
            value={factText}
            onChange={(e) => setFactText(e.target.value)}
            rows={2}
            required
          />
          <input 
            type="text" 
            placeholder="Source Document / Origine (optionnel)" 
            value={factSource}
            onChange={(e) => setFactSource(e.target.value)}
          />
          <button type="submit" className="glowing-btn" style={{ padding: '8px 0', borderRadius: '6px', fontSize: '0.9rem' }}>
            Enregistrer le Noeud
          </button>
        </form>

        {/* Relation Ingestion */}
        <form onSubmit={handleIngestRelation} className="glass" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }} className="gradient-text">Créer une Connexion Relationnelle</h3>
          <input 
            type="text" 
            placeholder="Noeud Source ID (ex: john_doe)" 
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            required
          />
          <input 
            type="text" 
            placeholder="Noeud Cible ID (ex: acme_inc)" 
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            required
          />
          <input 
            type="text" 
            placeholder="Type de Relation (ex: TRAVAILLE_A)" 
            value={relType}
            onChange={(e) => setRelType(e.target.value)}
            required
          />
          <button type="submit" className="glowing-btn" style={{ padding: '8px 0', borderRadius: '6px', fontSize: '0.9rem', marginTop: 'auto' }}>
            Créer la Relation
          </button>
        </form>

        {/* PDF Ingestion */}
        <form onSubmit={handleUploadPDF} className="glass" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }} className="gradient-text">Ingérer un Document PDF</h3>
          <div 
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            style={{
              flex: 1,
              border: `2px dashed ${isDragOver ? 'var(--secondary)' : 'var(--border-color)'}`,
              borderRadius: '8px',
              padding: '15px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: isDragOver ? 'rgba(6, 182, 212, 0.05)' : 'rgba(0, 0, 0, 0.2)',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              textAlign: 'center',
              minHeight: '110px'
            }}
            onClick={() => document.getElementById('pdf-file-input').click()}
          >
            <input 
              id="pdf-file-input"
              type="file" 
              accept=".pdf"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setSelectedFile(e.target.files[0]);
                  addLog(`Fichier sélectionné : ${e.target.files[0].name}`);
                }
              }}
              style={{ display: 'none' }}
            />
            {selectedFile ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: 'var(--success)', fontSize: '1.5rem' }}>📄</span>
                <span style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)', wordBreak: 'break-all' }}>
                  {selectedFile.name}
                </span>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </span>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: 'var(--text-muted)', fontSize: '1.5rem' }}>📥</span>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  Glissez-déposez un PDF ici ou cliquez pour parcourir
                </span>
              </div>
            )}
          </div>
          <button 
            type="submit" 
            className="glowing-btn" 
            style={{ 
              padding: '8px 0', 
              borderRadius: '6px', 
              fontSize: '0.9rem', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              gap: '8px',
              opacity: selectedFile && !isUploading ? 1 : 0.6,
              cursor: selectedFile && !isUploading ? 'pointer' : 'not-allowed'
            }}
            disabled={!selectedFile || isUploading}
          >
            {isUploading ? (
              <>
                <span style={{
                  width: '14px',
                  height: '14px',
                  border: '2px solid rgba(255,255,255,0.3)',
                  borderTopColor: '#fff',
                  borderRadius: '50%',
                  animation: 'spin 1s linear infinite',
                  display: 'inline-block'
                }}></span>
                Ingestion en cours...
              </>
            ) : "Ingérer le Document"}
          </button>
        </form>
      </div>

      {/* Middle Section: Loops and Logs Console */}
      <div style={{ display: 'flex', gap: '20px' }}>
        {/* Cognitive Loops Control Panel */}
        <div className="glass" style={{ width: '320px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }} className="gradient-text">Contrôles des Boucles Actives</h3>
          
          <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>Distillation : Consolider la mémoire</span>
            <button onClick={handleTriggerDistillation} className="glowing-btn" style={{ width: '100%', padding: '6px 0', borderRadius: '6px', fontSize: '0.82rem' }}>
              Exécuter la Distillation
            </button>
          </div>

          <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>Oubli LRU : Carence par taille maximum</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                type="number" 
                value={maxNodes}
                onChange={(e) => setMaxNodes(e.target.value)}
                style={{ width: '80px', padding: '4px 8px', fontSize: '0.82rem' }}
                placeholder="Nodes"
              />
              <button onClick={handleTriggerLRU} className="glowing-btn" style={{ flex: 1, padding: '4px 0', borderRadius: '6px', fontSize: '0.82rem' }}>
                Nettoyer par LRU
              </button>
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>Obsolescence : Éliminer les faits obsolètes</span>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                type="number" 
                value={maxAge}
                onChange={(e) => setMaxAge(e.target.value)}
                style={{ width: '80px', padding: '4px 8px', fontSize: '0.82rem' }}
                placeholder="Jours"
              />
              <button onClick={handleTriggerDecay} className="glowing-btn" style={{ flex: 1, padding: '4px 0', borderRadius: '6px', fontSize: '0.82rem' }}>
                Appliquer l'Obsolescence
              </button>
            </div>
          </div>
        </div>

        {/* Console Box */}
        <div className="glass" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column', height: '240px', overflow: 'hidden' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '8px' }} className="gradient-text">Console logs</h3>
          <div 
            className="custom-scroll" 
            style={{ 
              flex: 1, 
              background: 'rgba(0,0,0,0.4)', 
              borderRadius: '6px', 
              padding: '10px 14px', 
              fontSize: '0.82rem', 
              fontFamily: 'monospace', 
              color: 'var(--secondary)', 
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column-reverse',
              gap: '4px'
            }}
          >
            {consoleLogs.map((log, idx) => (
              <div key={idx} style={{ wordBreak: 'break-all' }}>{log}</div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Section: Security Audit Log Table */}
      <div className="glass" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }} className="gradient-text">Registre des Audits de Sécurité (Suppressions Semgrep)</h3>
        {ignoredList.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', padding: '10px' }}>
            Aucune règle de sécurité n'est actuellement supprimée ou ignorée.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '8px' }}>Régle</th>
                  <th style={{ padding: '8px' }}>Fichier</th>
                  <th style={{ padding: '8px' }}>Justification de la suppression</th>
                  <th style={{ padding: '8px' }}>Date de suppression</th>
                </tr>
              </thead>
              <tbody>
                {ignoredList.map((entry, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '8px', color: 'var(--accent)', fontWeight: 500 }}>{entry.ruleId}</td>
                    <td style={{ padding: '8px', color: 'var(--text-primary)' }}>{entry.filePath.split('\\').pop().split('/').pop()}</td>
                    <td style={{ padding: '8px', color: 'var(--text-secondary)' }}>{entry.reason}</td>
                    <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{new Date(entry.timestamp).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
