import React, { useState } from 'react';

/**
 * Formats a raw GCS source path into a human-readable document name.
 * e.g. "gs://bucket/policies/IR-Playbook-v3.pdf#chunk_12" → "IR-Playbook-v3.pdf · chunk 12"
 */
function formatSource(source) {
  if (!source) return source;
  // Strip gs://bucket/ prefix
  let s = source.replace(/^gs:\/\/[^/]+\//, '');
  // Extract filename from path
  const parts = s.split('/');
  let name = parts[parts.length - 1];
  // Format chunk suffix
  name = name.replace(/#chunk_(\d+)$/, ' · chunk $1');
  name = name.replace(/#page_(\d+)$/, ' · page $1');
  return name;
}

/**
 * Single icon for user avatar.
 */
function UserIcon() {
  return (
    <div className="flex-shrink-0 w-7 h-7 rounded-full bg-slate-600 border border-slate-500 flex items-center justify-center">
      <svg className="w-3.5 h-3.5 text-slate-300" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
      </svg>
    </div>
  );
}

/**
 * ARIA (assistant) icon with amber glow.
 */
function AssistantIcon({ isLoading }) {
  return (
    <div
      className={`flex-shrink-0 w-7 h-7 rounded-full border flex items-center justify-center ${
        isLoading
          ? 'border-amber-500 bg-amber-500/10 animate-pulse'
          : 'border-amber-500/50 bg-amber-500/10'
      }`}
      style={{
        boxShadow: '0 0 8px rgba(245,158,11,0.2)',
      }}
    >
      {/* Target/radar icon */}
      <svg className="w-3.5 h-3.5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="9"/>
        <circle cx="12" cy="12" r="4"/>
        <line x1="12" y1="3" x2="12" y2="7"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
        <line x1="3" y1="12" x2="7" y2="12"/>
        <line x1="17" y1="12" x2="21" y2="12"/>
      </svg>
    </div>
  );
}

/**
 * Typing animation — three amber dots.
 */
function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-amber-400"
          style={{
            animation: 'typingBounce 1.2s ease-in-out infinite',
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes typingBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

/**
 * Source document list — collapsible.
 */
function SourceList({ sources }) {
  const [open, setOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-white/5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors duration-200 group"
        aria-expanded={open}
        aria-label="Toggle source documents"
      >
        {/* Document stack icon */}
        <svg
          className="w-3 h-3 text-amber-500/60 group-hover:text-amber-400 transition-colors"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span className="font-mono uppercase tracking-wider" style={{ fontSize: '10px' }}>
          {sources.length} source{sources.length !== 1 ? 's' : ''}
        </span>
        <svg
          className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <ul className="mt-2 space-y-1 animate-fade-in">
          {sources.map((src, i) => (
            <li key={i} className="flex items-start gap-2 group">
              <span className="mt-0.5 w-1 h-1 flex-shrink-0 rounded-full bg-amber-500/40 group-hover:bg-amber-400/70 transition-colors mt-1.5" />
              <span
                className="font-mono text-slate-500 group-hover:text-slate-400 transition-colors break-all leading-relaxed"
                style={{ fontSize: '11px' }}
                title={src}
              >
                {formatSource(src)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Individual message bubble.
 * @param {{ message: { role: 'user'|'assistant', content: string, sources?: string[], latencyMs?: number, isLoading?: boolean, isError?: boolean, timestamp: Date } }} props
 */
export default function MessageBubble({ message }) {
  const isUser = message.role === 'user';
  const isError = message.isError;

  const timeStr = message.timestamp
    ? message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '';

  return (
    <div
      className={`flex items-start gap-3 w-full animate-slide-up ${
        isUser ? 'flex-row-reverse' : 'flex-row'
      }`}
    >
      {/* Avatar */}
      {isUser ? <UserIcon /> : <AssistantIcon isLoading={message.isLoading} />}

      {/* Bubble */}
      <div className={`flex flex-col max-w-[75%] min-w-0 ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Label row */}
        <div
          className={`flex items-center gap-2 mb-1 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
        >
          <span
            className={`font-mono uppercase tracking-widest ${isUser ? 'text-slate-500' : 'text-amber-500/80'}`}
            style={{ fontSize: '9px', letterSpacing: '0.12em' }}
          >
            {isUser ? 'operator' : 'aria'}
          </span>
          {timeStr && (
            <span className="text-slate-600" style={{ fontSize: '9px' }}>
              {timeStr}
            </span>
          )}
          {message.latencyMs && (
            <span
              className="font-mono text-slate-600"
              style={{ fontSize: '9px' }}
              title="Response latency"
            >
              {message.latencyMs}ms
            </span>
          )}
        </div>

        {/* Content card */}
        <div
          className={`relative rounded-2xl px-4 py-3 text-sm leading-relaxed w-full ${
            isUser
              ? 'bg-slate-700/40 border border-slate-600/40 text-slate-200 rounded-tr-sm'
              : isError
              ? 'bg-red-900/20 border border-red-500/30 text-red-300 rounded-tl-sm'
              : 'bg-surface-700 border border-white/5 text-slate-200 rounded-tl-sm'
          }`}
          style={
            !isUser && !isError
              ? { boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }
              : {}
          }
        >
          {/* Amber left accent bar for assistant messages */}
          {!isUser && !isError && (
            <div
              className="absolute left-0 top-3 bottom-3 w-px rounded-full"
              style={{ background: 'linear-gradient(to bottom, rgba(245,158,11,0.6), rgba(245,158,11,0.1))' }}
            />
          )}

          {/* Message content */}
          {message.isLoading ? (
            <TypingIndicator />
          ) : isError ? (
            <div className="flex items-start gap-2">
              <svg className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span>{message.content}</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}

          {/* Sources */}
          {!message.isLoading && !isUser && message.sources && (
            <SourceList sources={message.sources} />
          )}
        </div>
      </div>
    </div>
  );
}
