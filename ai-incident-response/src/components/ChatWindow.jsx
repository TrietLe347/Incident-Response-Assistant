import React, { useRef, useEffect } from 'react';
import MessageBubble from './MessageBubble.jsx';

/**
 * ChatWindow — scrollable message list.
 * Auto-scrolls to the latest message.
 */
export default function ChatWindow({ messages }) {
  const bottomRef = useRef(null);
  const containerRef = useRef(null);

  // Auto-scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-12 select-none">
        {/* Decorative radar icon */}
        <div className="relative mb-8">
          {/* Outer rings */}
          <div
            className="absolute inset-0 rounded-full border border-amber-500/10"
            style={{ width: '120px', height: '120px', transform: 'translate(-50%,-50%)', top:'50%', left:'50%', animation: 'ping 3s ease-in-out infinite' }}
          />
          <div
            className="absolute inset-0 rounded-full border border-amber-500/15"
            style={{ width: '80px', height: '80px', transform: 'translate(-50%,-50%)', top:'50%', left:'50%', animation: 'ping 3s ease-in-out 1s infinite' }}
          />
          <div
            className="w-16 h-16 rounded-full border border-amber-500/30 flex items-center justify-center"
            style={{ boxShadow: '0 0 20px rgba(245,158,11,0.1)' }}
          >
            <svg className="w-7 h-7 text-amber-400/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="3" x2="12" y2="7" />
              <line x1="12" y1="17" x2="12" y2="21" />
              <line x1="3" y1="12" x2="7" y2="12" />
              <line x1="17" y1="12" x2="21" y2="12" />
            </svg>
          </div>
        </div>

        <p className="font-mono text-amber-400/80 mb-2 tracking-widest uppercase" style={{ fontSize: '11px' }}>
          ARIA · Active
        </p>
        <h2 className="text-slate-300 text-lg font-medium text-center mb-3">
          AI Incident Response Assistant
        </h2>
        <p className="text-slate-600 text-sm text-center max-w-sm leading-relaxed">
          Ask about incident response procedures, escalation paths,
          containment strategies, or policy requirements.
        </p>

        {/* Suggestion chips */}
        <div className="mt-8 flex flex-wrap justify-center gap-2 max-w-md">
          {[
            'What is the containment procedure for a ransomware attack?',
            'Who should be notified in a Severity 1 incident?',
            'How do we handle a data breach affecting PII?',
            'What are our recovery time objectives?',
          ].map((q) => (
            <SuggestionChip key={q} text={q} />
          ))}
        </div>

        <style>{`
          @keyframes ping {
            0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.5; }
            50% { transform: translate(-50%, -50%) scale(1.15); opacity: 0.15; }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto chat-scroll px-4 py-6"
    >
      <div className="max-w-2xl mx-auto space-y-5">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

/**
 * Clickable suggestion chip — dispatches a custom event to pre-fill the input.
 */
function SuggestionChip({ text }) {
  function handleClick() {
    window.dispatchEvent(new CustomEvent('aria:suggestion', { detail: text }));
  }

  return (
    <button
      onClick={handleClick}
      className="px-3 py-1.5 rounded-full text-xs text-slate-500 hover:text-slate-300 border border-white/5 hover:border-amber-500/25 bg-surface-800 hover:bg-surface-700 transition-all duration-200 text-left"
    >
      {text}
    </button>
  );
}
