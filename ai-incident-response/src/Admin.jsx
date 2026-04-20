import React, { useState, useRef } from 'react';

const UPLOAD_SERVICE_URL = 'https://us-central1-cs-cloud-elamin.cloudfunctions.net/upload_document';

function LockIcon() {
  return (
    <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg className="w-8 h-8 text-amber-400/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
    </svg>
  );
}

// ── Login screen ─────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    if (!password.trim()) return;
    onLogin(password);
    setError('Wrong password. Try again.');
    setPassword('');
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
      style={{ background: 'var(--surface-950)' }}>
      <div
        className="w-full max-w-sm rounded-2xl border p-8"
        style={{ background: 'rgba(17,19,24,0.9)', borderColor: 'rgba(255,255,255,0.07)' }}
      >
        <div className="flex flex-col items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-xl border border-amber-500/40 flex items-center justify-center"
            style={{ background: 'rgba(245,158,11,0.08)' }}>
            <LockIcon />
          </div>
          <h1 className="font-mono text-slate-200 text-lg font-medium">Admin access</h1>
          <p className="text-slate-500 text-sm text-center">Enter the admin password to upload policy documents</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Password"
            className="w-full px-4 py-3 rounded-xl bg-slate-800/50 border border-white/10 text-slate-200 placeholder-slate-600 text-sm outline-none focus:border-amber-500/40"
          />
          {error && <p className="text-red-400 text-xs text-center">{error}</p>}
          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-medium text-sm transition-colors"
          >
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Upload file row ───────────────────────────────────────────────────────────
function FileRow({ file, status, message }) {
  const statusColor = {
    pending: 'text-slate-500',
    uploading: 'text-amber-400',
    success: 'text-emerald-400',
    error: 'text-red-400',
  }[status];

  const statusLabel = {
    pending: 'Pending',
    uploading: 'Uploading...',
    success: 'Uploaded',
    error: 'Failed',
  }[status];

  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-white/5 bg-slate-800/30">
      <svg className="w-4 h-4 text-red-400 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
        <path d="M7 3a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5H7zm5 1.5L16.5 9H12V4.5z"/>
      </svg>
      <span className="flex-1 text-slate-300 text-sm truncate">{file.name}</span>
      <span className="text-xs font-mono text-slate-600">{(file.size / 1024).toFixed(0)}KB</span>
      <span className={`text-xs font-mono ${statusColor}`}>{statusLabel}</span>
    </div>
  );
}

// ── Main admin page ───────────────────────────────────────────────────────────
function AdminPage({ password }) {
  const [files, setFiles] = useState([]);
  const [fileStatuses, setFileStatuses] = useState({});
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [summary, setSummary] = useState(null);
  const inputRef = useRef(null);

  function addFiles(newFiles) {
    const pdfs = Array.from(newFiles).filter(f => f.name.endsWith('.pdf'));
    if (pdfs.length === 0) return;
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name));
      const unique = pdfs.filter(f => !existing.has(f.name));
      return [...prev, ...unique];
    });
    setFileStatuses(prev => {
      const updated = { ...prev };
      pdfs.forEach(f => { if (!updated[f.name]) updated[f.name] = 'pending'; });
      return updated;
    });
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    addFiles(e.dataTransfer.files);
  }

  function removeFile(name) {
    setFiles(prev => prev.filter(f => f.name !== name));
    setFileStatuses(prev => {
      const updated = { ...prev };
      delete updated[name];
      return updated;
    });
  }

  async function uploadAll() {
    if (files.length === 0 || isUploading) return;
    setIsUploading(true);
    setSummary(null);

    let succeeded = 0;
    let failed = 0;

    for (const file of files) {
      if (fileStatuses[file.name] === 'success') continue;

      setFileStatuses(prev => ({ ...prev, [file.name]: 'uploading' }));

      try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(UPLOAD_SERVICE_URL, {
          method: 'POST',
          headers: { 'X-Admin-Password': password },
          body: formData,
        });

        if (res.ok) {
          setFileStatuses(prev => ({ ...prev, [file.name]: 'success' }));
          succeeded++;
        } else {
          const data = await res.json();
          setFileStatuses(prev => ({ ...prev, [file.name]: 'error' }));
          failed++;
        }
      } catch {
        setFileStatuses(prev => ({ ...prev, [file.name]: 'error' }));
        failed++;
      }
    }

    setIsUploading(false);
    setSummary({ succeeded, failed });
  }

  const pendingCount = files.filter(f => fileStatuses[f.name] === 'pending').length;
  const canUpload = pendingCount > 0 && !isUploading;

  return (
    <div className="min-h-screen" style={{ background: 'var(--surface-950)' }}>
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: 'rgba(255,255,255,0.05)', background: 'rgba(6,6,8,0.8)' }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg border border-amber-500/40 flex items-center justify-center"
            style={{ background: 'rgba(245,158,11,0.08)' }}>
            <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/>
              <line x1="12" y1="3" x2="12" y2="7"/><line x1="12" y1="17" x2="12" y2="21"/>
              <line x1="3" y1="12" x2="7" y2="12"/><line x1="17" y1="12" x2="21" y2="12"/>
            </svg>
          </div>
          <div>
            <h1 className="font-mono text-sm font-medium text-slate-200">ARIA Admin</h1>
            <p className="text-slate-600" style={{ fontSize: '10px' }}>Policy document management</p>
          </div>
        </div>
        <a href="/" className="text-xs font-mono text-slate-500 hover:text-slate-300 transition-colors">
          ← Back to ARIA
        </a>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10">
        <h2 className="text-slate-200 text-xl font-medium mb-2">Upload policy documents</h2>
        <p className="text-slate-500 text-sm mb-8">
          PDF files uploaded here are automatically ingested, chunked, and embedded into the vector index. New documents are searchable within 2–3 minutes.
        </p>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed cursor-pointer transition-all duration-200 py-12 mb-6"
          style={{
            borderColor: isDragging ? 'rgba(245,158,11,0.5)' : 'rgba(255,255,255,0.08)',
            background: isDragging ? 'rgba(245,158,11,0.04)' : 'transparent',
          }}
        >
          <UploadIcon />
          <div className="text-center">
            <p className="text-slate-300 text-sm font-medium">Drop PDF files here</p>
            <p className="text-slate-600 text-xs mt-1">or click to browse</p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={e => addFiles(e.target.files)}
          />
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="flex flex-col gap-2 mb-6">
            {files.map(file => (
              <div key={file.name} className="relative group">
                <FileRow file={file} status={fileStatuses[file.name]} />
                {fileStatuses[file.name] === 'pending' && (
                  <button
                    onClick={() => removeFile(file.name)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Summary */}
        {summary && (
          <div className={`rounded-xl px-4 py-3 text-sm mb-6 ${summary.failed > 0 ? 'bg-red-900/20 border border-red-500/20 text-red-300' : 'bg-emerald-900/20 border border-emerald-500/20 text-emerald-300'}`}>
            {summary.succeeded > 0 && `${summary.succeeded} file${summary.succeeded !== 1 ? 's' : ''} uploaded successfully. `}
            {summary.failed > 0 && `${summary.failed} file${summary.failed !== 1 ? 's' : ''} failed.`}
            {summary.succeeded > 0 && ' Documents will be searchable in 2–3 minutes.'}
          </div>
        )}

        {/* Upload button */}
        <button
          onClick={uploadAll}
          disabled={!canUpload}
          className={`w-full py-3 rounded-xl font-medium text-sm transition-all ${
            canUpload
              ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 cursor-pointer'
              : 'bg-slate-800 text-slate-600 cursor-not-allowed'
          }`}
        >
          {isUploading
            ? 'Uploading...'
            : pendingCount > 0
            ? `Upload ${pendingCount} file${pendingCount !== 1 ? 's' : ''}`
            : 'No files to upload'}
        </button>
      </main>
    </div>
  );
}

// ── Root component with auth gate ─────────────────────────────────────────────
export default function Admin() {
  const [password, setPassword] = useState(null);
  const [authError, setAuthError] = useState(false);

  const CORRECT_PASSWORD = 'aria-admin-2026';

  function handleLogin(attempt) {
    if (attempt === CORRECT_PASSWORD) {
      setPassword(attempt);
      setAuthError(false);
    } else {
      setAuthError(true);
    }
  }

  if (!password) {
    return <LoginScreen onLogin={handleLogin} showError={authError} />;
  }

  return <AdminPage password={password} />;
}