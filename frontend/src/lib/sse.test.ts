import { describe, it, expect } from 'vitest';
import { parseSSE, SSEEvent } from './sse';

describe('parseSSE', () => {
  it('parses single event', () => {
    const raw = 'event: thinking\ndata: {"step": "retrieve", "message": "Searching..."}\n\n';
    const events = parseSSE(raw);

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('thinking');
    expect(events[0].data.step).toBe('retrieve');
  });

  it('parses multiple events', () => {
    const raw =
      'event: thinking\ndata: {"step": "retrieve"}\n\n' +
      'event: chunk\ndata: {"content": "Hello"}\n\n';
    const events = parseSSE(raw);

    expect(events).toHaveLength(2);
    expect(events[0].type).toBe('thinking');
    expect(events[1].type).toBe('chunk');
  });

  it('handles partial events gracefully', () => {
    const raw = 'event: thinking\ndata: {"step"';
    const events = parseSSE(raw);

    expect(events).toHaveLength(0);
  });

  it('handles empty string', () => {
    const events = parseSSE('');
    expect(events).toHaveLength(0);
  });
});
