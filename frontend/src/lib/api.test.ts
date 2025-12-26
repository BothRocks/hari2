import { describe, it, expect, vi, beforeEach } from 'vitest';
import { queryApi } from './api';

describe('queryApi.streamAsk', () => {
  const localStorageMock = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(),
  };

  beforeEach(() => {
    vi.resetAllMocks();
    Object.defineProperty(global, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });
    localStorageMock.getItem.mockReturnValue(null);
  });

  it('calls fetch with correct parameters', async () => {
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode('event: done\ndata: {}\n\n'),
            })
            .mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: unknown[] = [];
    await queryApi.streamAsk('test query', (event) => events.push(event));

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/query/stream'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ query: 'test query', max_iterations: 3 }),
      })
    );
  });

  it('parses SSE events and calls onEvent callback', async () => {
    const sseData = 'event: thinking\ndata: {"content":"analyzing"}\n\nevent: done\ndata: {"answer":"result"}\n\n';
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn()
            .mockResolvedValueOnce({
              done: false,
              value: new TextEncoder().encode(sseData),
            })
            .mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: unknown[] = [];
    await queryApi.streamAsk('test query', (event) => events.push(event));

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: 'thinking', data: { content: 'analyzing' } });
    expect(events[1]).toEqual({ type: 'done', data: { answer: 'result' } });
  });

  it('throws error when response is not ok', async () => {
    const mockResponse = {
      ok: false,
      status: 500,
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    await expect(queryApi.streamAsk('test query', vi.fn())).rejects.toThrow(
      'Stream request failed: 500'
    );
  });

  it('throws error when response body is null', async () => {
    const mockResponse = {
      ok: true,
      body: null,
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    await expect(queryApi.streamAsk('test query', vi.fn())).rejects.toThrow(
      'No response body'
    );
  });

  it('includes API key header when available', async () => {
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    // Set API key for this test
    localStorageMock.getItem.mockReturnValue('test-api-key');

    await queryApi.streamAsk('test query', vi.fn());

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-API-Key': 'test-api-key',
        }),
      })
    );
  });

  it('uses custom maxIterations parameter', async () => {
    const mockResponse = {
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValueOnce({ done: true, value: undefined }),
        }),
      },
    };

    global.fetch = vi.fn().mockResolvedValue(mockResponse);

    await queryApi.streamAsk('test query', vi.fn(), 5);

    expect(fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: JSON.stringify({ query: 'test query', max_iterations: 5 }),
      })
    );
  });
});
