export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

/**
 * Parse raw SSE text into structured events.
 */
export function parseSSE(raw: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const lines = raw.split('\n');

  let currentType = '';
  let currentData = '';

  for (const line of lines) {
    if (line.startsWith('event: ')) {
      currentType = line.slice(7);
    } else if (line.startsWith('data: ')) {
      currentData = line.slice(6);
    } else if (line === '' && currentType && currentData) {
      try {
        events.push({
          type: currentType,
          data: JSON.parse(currentData),
        });
      } catch {
        // Skip malformed JSON
      }
      currentType = '';
      currentData = '';
    }
  }

  return events;
}
