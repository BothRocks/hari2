import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChatPage } from './ChatPage';
import { queryApi } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  queryApi: {
    ask: vi.fn(),
    streamAsk: vi.fn(),
  },
}));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderWithProviders() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatPage />
    </QueryClientProvider>
  );
}

describe('ChatPage streaming', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('calls streamAsk when submitting a query', async () => {
    vi.mocked(queryApi.streamAsk).mockResolvedValue();

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(queryApi.streamAsk).toHaveBeenCalledWith('test query', expect.any(Function));
    });
  });

  it('displays thinking steps and answer after streaming completes', async () => {
    // Use a Promise-based mock to control timing
    let mockOnEvent: ((event: { type: string; data: Record<string, unknown> }) => void) | null = null;

    vi.mocked(queryApi.streamAsk).mockImplementation(async (_query, onEvent) => {
      mockOnEvent = onEvent;
      // Simulate streaming events
      onEvent({ type: 'thinking', data: { step: 'retrieve', message: 'Searching...' } });
      onEvent({ type: 'thinking', data: { step: 'evaluate', message: 'Evaluating...' } });
      onEvent({ type: 'chunk', data: { content: 'Answer text.' } });
      onEvent({ type: 'sources', data: { internal: [], external: [] } });
      onEvent({ type: 'done', data: { research_iterations: 0 } });
    });

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /ask/i }));

    // Wait for the mock to be called
    await waitFor(() => {
      expect(mockOnEvent).not.toBeNull();
    });

    // Wait for the final message with thinking steps
    await waitFor(() => {
      const thinkingStepsContainer = screen.queryByRole('status', { name: /processing steps/i });
      expect(thinkingStepsContainer).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('Searching...')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText('Evaluating...')).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/Answer text/)).toBeInTheDocument();
    });
  });

  it('displays inline errors without breaking', async () => {
    vi.mocked(queryApi.streamAsk).mockImplementation(async (_query, onEvent) => {
      onEvent({ type: 'thinking', data: { step: 'retrieve', message: 'Searching...' } });
      onEvent({ type: 'error', data: { step: 'research', message: 'Web search failed' } });
      onEvent({ type: 'chunk', data: { content: 'Fallback answer.' } });
      onEvent({ type: 'sources', data: { internal: [], external: [] } });
      onEvent({ type: 'done', data: { research_iterations: 0 } });
    });

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /ask/i }));

    // Wait for streamAsk to be called
    await waitFor(() => {
      expect(queryApi.streamAsk).toHaveBeenCalled();
    });

    // Both error and content should be visible in final state
    await waitFor(() => {
      expect(screen.getByText(/Web search failed/)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText(/Fallback answer/)).toBeInTheDocument();
    });
  });

  it('accumulates chunks into final content', async () => {
    vi.mocked(queryApi.streamAsk).mockImplementation(async (_query, onEvent) => {
      onEvent({ type: 'thinking', data: { step: 'retrieve', message: 'Searching...' } });
      onEvent({ type: 'chunk', data: { content: 'First ' } });
      onEvent({ type: 'chunk', data: { content: 'chunk.' } });
      onEvent({ type: 'sources', data: { internal: [], external: [] } });
      onEvent({ type: 'done', data: { research_iterations: 0 } });
    });

    renderWithProviders();

    const input = screen.getByPlaceholderText(/ask/i);
    await userEvent.type(input, 'test query');
    await userEvent.click(screen.getByRole('button', { name: /ask/i }));

    // Wait for streamAsk to be called
    await waitFor(() => {
      expect(queryApi.streamAsk).toHaveBeenCalled();
    });

    // Final content should have both chunks concatenated
    await waitFor(() => {
      expect(screen.getByText(/First chunk/)).toBeInTheDocument();
    });
  });
});
