import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatPanel() {
  const [sessions, setSessionsList] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Bonjour ! Je suis Nexus, votre agent à Mémoire Persistante Évolutive. Posez-moi des questions en lien avec mes connaissances, ou passez en mode Gouvernance pour alimenter ma mémoire.', auditTrail: [] }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedAuditTrail, setSelectedAuditTrail] = useState(null);
  const [committing, setCommitting] = useState(false);
  const [commitResult, setCommitResult] = useState(null);
  
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const fetchSessions = async (autoSelectId = null) => {
    try {
      const response = await fetch('http://localhost:8000/api/sessions');
      if (response.ok) {
        const data = await response.json();
        setSessionsList(data.sessions);
        
        if (autoSelectId && autoSelectId !== currentSessionId) {
          loadSession(autoSelectId);
        } else if (data.sessions.length > 0 && !currentSessionId) {
          loadSession(data.sessions[0].id);
        } else if (data.sessions.length === 0) {
          handleNewChat();
        }
      }
    } catch (e) {
      console.error("Error fetching sessions:", e);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  const loadSession = async (sessionId) => {
    setCurrentSessionId(sessionId);
    setCommitResult(null);
    setSelectedAuditTrail(null);
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.messages && data.messages.length > 0) {
          setMessages(data.messages);
        } else {
          setMessages([
            { role: 'assistant', content: 'Nouvelle conversation démarrée ! Comment puis-je vous aider ?', auditTrail: [] }
          ]);
        }
      }
    } catch (e) {
      console.error("Error loading session:", e);
    }
  };

  const handleNewChat = async () => {
    setCommitResult(null);
    setSelectedAuditTrail(null);
    try {
      const response = await fetch('http://localhost:8000/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Nouvelle conversation' })
      });
      if (response.ok) {
        const data = await response.json();
        setSessionsList(prev => [data, ...prev]);
        setCurrentSessionId(data.id);
        setMessages([
          { role: 'assistant', content: 'Bonjour ! Je suis Nexus, votre agent à Mémoire Persistante Évolutive. Posez-moi des questions en lien avec mes connaissances, ou passez en mode Gouvernance pour alimenter ma mémoire.', auditTrail: [] }
        ]);
      }
    } catch (e) {
      console.error("Error creating session:", e);
    }
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    if (!window.confirm("Voulez-vous vraiment supprimer cette conversation ?")) return;
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        setSessionsList(prev => prev.filter(s => s.id !== sessionId));
        if (currentSessionId === sessionId) {
          const remaining = sessions.filter(s => s.id !== sessionId);
          if (remaining.length > 0) {
            loadSession(remaining[0].id);
          } else {
            handleNewChat();
          }
        }
      }
    } catch (e) {
      console.error("Error deleting session:", e);
    }
  };

  const handleRenameSession = async (sessionId, currentTitle) => {
    const newTitle = window.prompt("Entrez le nouveau titre de la conversation :", currentTitle);
    if (!newTitle || !newTitle.trim()) return;
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${sessionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
      });
      if (response.ok) {
        setSessionsList(prev => prev.map(s => s.id === sessionId ? { ...s, title: newTitle } : s));
      }
    } catch (e) {
      console.error("Error renaming session:", e);
    }
  };

  const handleCommitToMpe = async () => {
    if (!currentSessionId) return;
    setCommitting(true);
    setCommitResult(null);
    try {
      const response = await fetch(`http://localhost:8000/api/sessions/${currentSessionId}/commit`, {
        method: 'POST'
      });
      const data = await response.json();
      if (response.ok) {
        setCommitResult({
          success: true,
          message: data.message,
          facts: data.facts_committed || [],
          relations: data.relations_committed || []
        });
      } else {
        setCommitResult({
          success: false,
          message: data.detail || "Une erreur s'est produite lors de l'enregistrement."
        });
      }
    } catch (e) {
      setCommitResult({
        success: false,
        message: `Erreur de connexion : ${e.message}`
      });
    } finally {
      setCommitting(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading || !currentSessionId) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userMessage,
          session_id: currentSessionId
        })
      });

      if (!response.ok) {
        throw new Error('Erreur de communication avec le serveur backend.');
      }

      const data = await response.json();
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: data.response,
        auditTrail: data.audit_trail || []
      }]);
      
      // Update session title list if needed
      fetchSessions(currentSessionId);
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Erreur : Impossible de contacter le backend Nexus. Assurez-vous que le serveur FastAPI est démarré sur le port 8000. Detail: ${error.message}`,
        auditTrail: []
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', gap: '20px' }}>
      {/* Sessions Sidebar */}
      <div className="glass" style={{ width: '280px', display: 'flex', flexDirection: 'column', padding: '16px', gap: '16px', flexShrink: 0 }}>
        <button 
          onClick={handleNewChat} 
          className="glowing-btn" 
          style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
        >
          ➕ Nouvelle Discussion
        </button>
        
        <div className="custom-scroll" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }}>
          {sessions.map(s => {
            const isActive = s.id === currentSessionId;
            return (
              <div 
                key={s.id}
                onClick={() => loadSession(s.id)}
                className="glass-interactive"
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.01)',
                  border: isActive ? '1px solid var(--primary)' : '1px solid rgba(255, 255, 255, 0.04)',
                  transition: 'all 0.2s ease'
                }}
              >
                <span style={{ 
                  fontSize: '0.88rem', 
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  flex: 1,
                  marginRight: '8px',
                  fontWeight: isActive ? 600 : 400
                }}>
                  💬 {s.title}
                </span>
                
                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                  <button 
                    onClick={(e) => { e.stopPropagation(); handleRenameSession(s.id, s.title); }}
                    style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                    title="Renommer"
                  >
                    ✏️
                  </button>
                  <button 
                    onClick={(e) => handleDeleteSession(s.id, e)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '0.85rem' }}
                    title="Supprimer"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Chat Area */}
      <div className="glass" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '20px', position: 'relative' }}>
        
        {/* Chat Header / MPE Action */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '12px', flexShrink: 0 }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '60%' }}>
            {sessions.find(s => s.id === currentSessionId)?.title || "Conversation"}
          </h2>
          <button 
            onClick={handleCommitToMpe}
            disabled={committing || messages.length <= 1}
            className="glowing-btn"
            style={{ 
              padding: '8px 14px', 
              borderRadius: '6px', 
              fontSize: '0.85rem', 
              opacity: (committing || messages.length <= 1) ? 0.6 : 1,
              cursor: (committing || messages.length <= 1) ? 'not-allowed' : 'pointer'
            }}
          >
            💾 {committing ? "Consolidation..." : "Enregistrer dans la MPE"}
          </button>
        </div>

        {/* If commit result is present, show a banner */}
        {commitResult && (
          <div className="glass" style={{ 
            padding: '12px 16px', 
            marginBottom: '12px', 
            borderRadius: '8px', 
            background: commitResult.success ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
            border: commitResult.success ? '1px solid var(--success)' : '1px solid var(--danger)',
            fontSize: '0.88rem',
            flexShrink: 0
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: commitResult.success ? 'var(--success)' : 'var(--danger)' }}>
              <span>{commitResult.success ? "✨ Enregistrement MPE Réussi !" : "⚠️ Erreur d'enregistrement"}</span>
              <button style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '1rem' }} onClick={() => setCommitResult(null)}>✕</button>
            </div>
            <p style={{ marginTop: '4px', color: 'var(--text-primary)' }}>{commitResult.message}</p>
            {commitResult.facts && commitResult.facts.length > 0 && (
              <div style={{ marginTop: '8px', fontSize: '0.82rem' }}>
                <span style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Faits consolidés :</span>
                <ul style={{ marginLeft: '18px', marginTop: '4px', color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  {commitResult.facts.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '6px', paddingBottom: '20px' }}>
          {messages.map((msg, index) => (
            <div 
              key={index} 
              style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '75%',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div 
                className="glass" 
                style={{
                  padding: '12px 18px',
                  borderRadius: msg.role === 'user' ? '18px 18px 2px 18px' : '18px 18px 18px 2px',
                  background: msg.role === 'user' 
                    ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(6, 182, 212, 0.15) 100%)' 
                    : 'rgba(255, 255, 255, 0.03)',
                  border: msg.role === 'user'
                    ? '1px solid rgba(139, 92, 246, 0.3)'
                    : '1px solid rgba(255, 255, 255, 0.08)',
                  color: '#fff',
                  fontSize: '0.98rem',
                  lineHeight: '1.5'
                }}
              >
                <div className="markdown-content">
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
              
              {msg.role === 'assistant' && msg.auditTrail && msg.auditTrail.length > 0 && (
                <button 
                  onClick={() => setSelectedAuditTrail(selectedAuditTrail === msg.auditTrail ? null : msg.auditTrail)}
                  style={{
                    alignSelf: 'flex-start',
                    background: 'none',
                    border: 'none',
                    color: 'var(--secondary)',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 4px',
                    fontWeight: 500
                  }}
                >
                  🔍 {selectedAuditTrail === msg.auditTrail ? "Masquer la chaîne de preuves" : "Voir la chaîne de preuves (Audit)"}
                </button>
              )}
            </div>
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 18px' }}>
              <div className="spinner" style={{
                width: '18px',
                height: '18px',
                border: '2px solid rgba(255,255,255,0.1)',
                borderTopColor: 'var(--primary)',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }}></div>
              <style>{`
                @keyframes spin {
                  0% { transform: rotate(0deg); }
                  100% { transform: rotate(360deg); }
                }
              `}</style>
              <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Nexus réfléchit...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-color)', flexShrink: 0 }}>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez une question ou ajoutez un fait (ex: STORE: Fact text)..."
            style={{ flex: 1 }}
            disabled={loading || !currentSessionId}
          />
          <button 
            type="submit" 
            className="glowing-btn" 
            style={{ padding: '0 24px', borderRadius: '8px', fontSize: '0.95rem' }}
            disabled={loading || !currentSessionId}
          >
            Envoyer
          </button>
        </form>
      </div>

      {/* Side Audit Panel */}
      {selectedAuditTrail && (
        <div 
          className="glass" 
          style={{ 
            width: '320px', 
            display: 'flex', 
            flexDirection: 'column', 
            padding: '20px', 
            borderLeft: '1px solid var(--border-color)',
            animation: 'slideIn 0.3s ease-out',
            flexShrink: 0
          }}
        >
          <style>{`
            @keyframes slideIn {
              from { transform: translateX(50px); opacity: 0; }
              to { transform: translateX(0); opacity: 1; }
            }
          `}</style>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }} className="gradient-text">Chaîne de Provenance</h3>
            <button 
              onClick={() => setSelectedAuditTrail(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.1rem' }}
            >
              ✕
            </button>
          </div>
          <div className="custom-scroll" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {selectedAuditTrail.map((step, sIdx) => {
              let isProvenance = step.startsWith("[Provenance]");
              let isDiagnostic = step.startsWith("[Diagnostic]");
              let isRoute = step.startsWith("[Diagnostic Router]");
              
              let bubbleBg = "rgba(255, 255, 255, 0.02)";
              let borderCol = "var(--border-color)";
              let labelCol = "var(--text-muted)";
              
              if (isProvenance) {
                bubbleBg = "rgba(6, 182, 212, 0.05)";
                borderCol = "rgba(6, 182, 212, 0.15)";
                labelCol = "var(--secondary)";
              } else if (isDiagnostic || isRoute) {
                bubbleBg = "rgba(245, 158, 11, 0.05)";
                borderCol = "rgba(245, 158, 11, 0.15)";
                labelCol = "var(--warning)";
              }
              
              return (
                <div 
                  key={sIdx}
                  style={{
                    background: bubbleBg,
                    border: `1px solid ${borderCol}`,
                    borderRadius: '8px',
                    padding: '10px 12px',
                    fontSize: '0.88rem',
                    lineHeight: '1.4',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: labelCol, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {isProvenance ? "Similarité Sémantique / Subgraphe" : isDiagnostic || isRoute ? "Hygiène / Diagnostic" : "Inférence"}
                  </span>
                  <div style={{ color: 'var(--text-primary)' }}>
                    {step.replace(/^\[Provenance\]\s*/, "").replace(/^\[Diagnostic\]\s*/, "").replace(/^\[Diagnostic Router\]\s*/, "")}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
