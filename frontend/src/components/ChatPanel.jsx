import React, { useState, useRef, useEffect } from 'react';

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Bonjour ! Je suis Nexus, votre agent à Mémoire Persistante Évolutive. Posez-moi des questions en lien avec mes connaissances, ou passez en mode Gouvernance pour alimenter ma mémoire.', auditTrail: [] }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedAuditTrail, setSelectedAuditTrail] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
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
      {/* Chat Area */}
      <div className="glass" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '20px', position: 'relative' }}>
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
                {msg.content}
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
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-color)' }}>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Posez une question ou ajoutez un fait (ex: STORE: Fact text)..."
            style={{ flex: 1 }}
            disabled={loading}
          />
          <button 
            type="submit" 
            className="glowing-btn" 
            style={{ padding: '0 24px', borderRadius: '8px', fontSize: '0.95rem' }}
            disabled={loading}
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
            animation: 'slideIn 0.3s ease-out'
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
