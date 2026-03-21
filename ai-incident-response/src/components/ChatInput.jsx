import React, { useRef, useEffect } from 'react';

/**
 * ChatInput — sticky input bar at the bottom.
 * Supports Enter to send, Shift+Enter for newlines, auto-resize, and keyboard accessibility.
 */
export default function ChatInput({ value, onChange, onSend, isLoading, disabled }) {
  const textareaRef = useRef(null);

  // Auto-resize textarea up to a max height
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }, [value]);

  // Focus input on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && !isLoading && value.trim()) {
        onSend();
      }
    }
  }

  const canSend = !disabled && !isLoading && value.trim().length > 0;

  return (
    <div
      className="relative flex items-end gap-3 p-3 rounded-2xl border transition-all duration-200"
      style={{
        background: 'rgba(17,19,24,0.9)',
        borderColor: isLoading
          ? 'rgba(245,158,11,0.35)'
          : value.trim()
          ? 'rgba(245,158,11,0.25)'
          : 'rgba(255,255,255,0.07)',
        boxShadow: value.trim()
          ? '0 0 0 1px rgba(245,158,11,0.1), 0 4px 20px rgba(0,0,0,0.4)'
          : '0 4px 20px rgba(0,0,0,0.3)',
      }}
    >
      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe the incident or ask a policy question…"
        disabled={isLoading}
        rows={1}
        aria-label="Chat input"
        className="flex-1 resize-none bg-transparent text-slate-200 placeholder-slate-600 text-sm leading-relaxed outline-none py-1 min-h-[24px] max-h-[160px] font-sans"
        style={{ scrollbarWidth: 'none' }}
      />

      {/* Right side buttons */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Hint text */}
        {!isLoading && value.trim() && (
          <span className="hidden sm:block font-mono text-slate-600 select-none" style={{ fontSize: '10px' }}>
            ↵ send
          </span>
        )}

        {/* Send button */}
        <button
          onClick={onSend}
          disabled={!canSend}
          aria-label="Send message"
          className={`
            relative w-8 h-8 rounded-xl flex items-center justify-center
            transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/50
            ${canSend
              ? 'bg-amber-500 hover:bg-amber-400 text-surface-950 shadow-amber-sm hover:shadow-amber-md cursor-pointer'
              : 'bg-surface-600 text-slate-600 cursor-not-allowed'
            }
          `}
          style={{
            boxShadow: canSend ? '0 0 12px rgba(245,158,11,0.3)' : 'none',
          }}
        >
          {isLoading ? (
            /* Loading spinner */
            <svg
              className="w-3.5 h-3.5 animate-spin-slow"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path d="M12 3v3m0 12v3M3 12h3m12 0h3m-3.3-6.7-2.1 2.1M8.4 15.6l-2.1 2.1m0-10.7 2.1 2.1m7.2 7.2 2.1 2.1" />
            </svg>
          ) : (
            /* Arrow up icon */
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path d="M5 12l7-7 7 7M12 5v14" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
