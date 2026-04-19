/**
 * API Service — ARIA Incident Response Assistant
 * Supports Server-Sent Events (SSE) streaming from the answer service.
 */
const ANSWER_SERVICE_URL = 'https://us-central1-cs-cloud-elamin.cloudfunctions.net/answer';


/**
 * Query the RAG Answer Service with streaming.
 *
 * Calls onChunk(text) for each streamed token.
 * Calls onSources(sources) when sources arrive (early, before answer).
 * Returns { answer, sources, latencyMs } when complete.
 *
 * @param {string} query
 * @param {{ onChunk?: (text: string) => void, onSources?: (sources: string[]) => void }} callbacks
 * @returns {Promise<{ answer: string, sources: string[], latencyMs: number }>}
 */
export async function queryAnswerService(query, { onChunk, onSources } = {}) {
  if (!query || typeof query !== 'string' || query.trim().length === 0) {
    throw new Error('Query must be a non-empty string.');
  }

  const startTime = performance.now();

  const response = await fetch(ANSWER_SERVICE_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ query: query.trim(), stream: true }),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errorBody = await response.json();
      errorDetail = errorBody.message || errorBody.error || errorDetail;
    } catch {
      // ignore parse error
    }
    throw new Error(`Answer service error: ${errorDetail}`);
  }

  const contentType = response.headers.get('content-type') || '';

  // --- Streaming path ---
  if (contentType.includes('text/event-stream') && response.body) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullAnswer = '';
    let sources = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // keep incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let event;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }

        if (event.type === 'sources') {
          sources = event.sources || [];
          onSources?.(sources);
        } else if (event.type === 'chunk') {
          fullAnswer += event.text;
          onChunk?.(event.text);
        } else if (event.type === 'done') {
          fullAnswer = event.answer || fullAnswer;
          sources = event.sources || sources;
        } else if (event.type === 'error') {
          throw new Error(event.message || 'Streaming error from server');
        }
      }
    }

    const latencyMs = Math.round(performance.now() - startTime);
    return { answer: fullAnswer, sources, latencyMs };
  }

  // --- Non-streaming fallback (JSON response) ---
  const data = await response.json();
  const latencyMs = Math.round(performance.now() - startTime);
  return {
    answer: data.answer ?? 'No answer returned.',
    sources: Array.isArray(data.sources) ? data.sources : [],
    latencyMs,
  };
}
