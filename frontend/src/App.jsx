import React, { useState } from 'react';
import ChatPanel from './components/ChatPanel';
import DiagPanel from './components/DiagPanel';
import GovPanel from './components/GovPanel';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      width: '100vw',
      padding: '24px',
      gap: '20px',
      overflow: 'hidden'
    }}>
      {/* Header Hub */}
      <header className="glass" style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '12px 24px',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)',
            boxShadow: '0 0 10px var(--primary-glow)'
          }} />
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '0.5px' }} className="gradient-text">
            NEXUS // MPE Dashboard
          </h1>
        </div>

        {/* Tab Navigation Menu */}
        <nav style={{ display: 'flex', gap: '8px' }}>
          {[
            { id: 'chat', label: '💬 Interaction Chat' },
            { id: 'diag', label: '📊 Diagnostic Graphe' },
            { id: 'gov', label: '🛡️ Gouvernance & Boucles' }
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  background: isActive ? 'rgba(255, 255, 255, 0.05)' : 'transparent',
                  border: '1px solid',
                  borderColor: isActive ? 'var(--primary)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  padding: '8px 16px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '0.9rem',
                  fontWeight: 500,
                  transition: 'all 0.3s ease',
                  boxShadow: isActive ? '0 0 12px var(--border-glow)' : 'none'
                }}
                className={isActive ? '' : 'glass-interactive'}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
        
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 500 }}>
          v1.0.0 // LOCAL-FIRST
        </div>
      </header>

      {/* Main Workspace Dashboard Content */}
      <main style={{
        flex: 1,
        minHeight: 0, /* Important for nested scrolls to work inside flex boxes */
        display: 'flex',
        overflow: 'hidden'
      }}>
        {activeTab === 'chat' && <ChatPanel />}
        {activeTab === 'diag' && <DiagPanel />}
        {activeTab === 'gov' && <GovPanel />}
      </main>
    </div>
  );
}
