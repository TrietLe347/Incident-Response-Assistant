/**
 * API Service — AI Incident Response Assistant
 * Communicates with the RAG Answer Service on Google Cloud Run.
 */

const ANSWER_SERVICE_URL =
  'https://answer-service-571628338947.us-central1.run.app';

/**
 * Query the RAG Answer Service.
 *
 * @param {string} query - The user's question
 * @returns {Promise<{ answer: string, sources: string[], latencyMs: number }>}
 */
export async function queryAnswerService(query) {
  if (!query || typeof query !== 'string' || query.trim().length === 0) {
    throw new Error('Query must be a non-empty string.');
  }

  const startTime = performance.now();

  const response = await fetch(ANSWER_SERVICE_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ query: query.trim() }),
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}`;
    try {
      const errorBody = await response.json();
      errorDetail = errorBody.message || errorBody.error || errorDetail;
    } catch {
      // ignore parse error, use status code only
    }
    throw new Error(`Answer service error: ${errorDetail}`);
  }

  const data = await response.json();
  const latencyMs = Math.round(performance.now() - startTime);

  return {
    answer: data.answer ?? 'No answer returned.',
    sources: Array.isArray(data.sources) ? data.sources : [],
    latencyMs,
  };
}
