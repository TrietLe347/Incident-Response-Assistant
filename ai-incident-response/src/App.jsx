import React, { useState, useCallback, useEffect } from 'react';
import ChatWindow from './components/ChatWindow.jsx';
import ChatInput from './components/ChatInput.jsx';
import { queryAnswerService } from './services/api.js';

let msgIdCounter = 0;
function nextId() {
  return ++msgIdCounter;
}

function StatusBadge({ isLoading }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          isLoading ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'
        }`}
        style={{
          boxShadow: isLoading
            ? '0 0 6px rgba(245,158,11,0.6)'
            : '0 0 6px rgba(52,211,153,0.6)',
        }}
      />
      <span className="font-mono text-slate-500 uppercase tracking-widest" style={{ fontSize: '9px' }}>
        {isLoading ? 'processing' : 'ready'}
      </span>
    </div>
  );
}

function ClearButton({ onClear, disabled }) {
  return (
    <button
      onClick={onClear}
      disabled={disabled}
      title="Clear conversation"
      aria-label="Clear conversation"
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-400/40"
    >
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
      <span style={{ fontSize: '10px' }} className="font-mono uppercase tracking-wide">Clear</span>
    </button>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    function handler(e) { setInputValue(e.detail); }
    window.addEventListener('aria:suggestion', handler);
    return () => window.removeEventListener('aria:suggestion', handler);
  }, []);

  const sendMessage = useCallback(async () => {
    const query = inputValue.trim();
    if (!query || isLoading) return;

    const userMsg = {
      id: nextId(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    const assistantId = nextId();
    const loadingMsg = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isLoading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);
    setInputValue('');
    setIsLoading(true);

    const startTime = performance.now();

    try {
      const { answer, sources, latencyMs } = await queryAnswerService(query, {
        // Called when sources arrive early — show them before answer is complete
        onSources: (sources) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, sources } : m
            )
          );
        },
        // Called for each streamed chunk — append text progressively
        onChunk: (text) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content + text, isLoading: false }
                : m
            )
          );
        },
      });

      // Final update: ensure complete answer + latency
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: answer, sources, latencyMs, isLoading: false }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content:
                  err.message ||
                  'Unable to reach the answer service. Please check your connection and try again.',
                isLoading: false,
                isError: true,
              }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [inputValue, isLoading]);

  function handleClear() {
    if (isLoading) return;
    setMessages([]);
    setInputValue('');
  }

  return (
    <div
      className="min-h-screen w-full flex flex-col grid-bg noise-overlay"
      style={{ background: 'var(--surface-950)' }}
    >
      <div className="fixed top-0 left-0 right-0 h-64 pointer-events-none radial-glow z-0" />

      <header
        className="relative z-10 flex-shrink-0 flex items-center justify-between px-4 sm:px-6 py-3.5 border-b"
        style={{
          background: 'rgba(6,6,8,0.8)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg border border-amber-500/40 flex items-center justify-center"
            style={{ background: 'rgba(245,158,11,0.08)', boxShadow: '0 0 12px rgba(245,158,11,0.15)' }}
          >
            <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="3" x2="12" y2="7" />
              <line x1="12" y1="17" x2="12" y2="21" />
              <line x1="3" y1="12" x2="7" y2="12" />
              <line x1="17" y1="12" x2="21" y2="12" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono text-sm font-medium text-slate-200 tracking-wide">ARIA</h1>
              <span
                className="px-1.5 py-0.5 rounded font-mono uppercase tracking-widest text-amber-500/80 border border-amber-500/20"
                style={{ fontSize: '8px', background: 'rgba(245,158,11,0.05)' }}
              >
                RAG
              </span>
            </div>
            <p className="text-slate-600 leading-none" style={{ fontSize: '10px' }}>
              AI Incident Response Assistant
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge isLoading={isLoading} />
          {messages.length > 0 && (
            <ClearButton onClear={handleClear} disabled={isLoading} />
          )}
        </div>
      </header>

      <main className="relative z-10 flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full overflow-hidden">
          <ChatWindow messages={messages} />
          <div className="flex-shrink-0 px-4 pb-5 pt-2">
            <ChatInput
              value={inputValue}
              onChange={setInputValue}
              onSend={sendMessage}
              isLoading={isLoading}
              disabled={isLoading}
            />
            <p className="text-center text-slate-700 mt-2.5 font-mono" style={{ fontSize: '9px' }}>
              Powered by Gemini · Vertex AI · Google Cloud Run
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}