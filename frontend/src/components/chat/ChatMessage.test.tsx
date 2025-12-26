import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatMessage } from './ChatMessage';

describe('ChatMessage', () => {
  it('renders sources as clickable links', () => {
    const sources = [
      { id: '1', title: 'Tech Report', url: 'https://example.com/report.pdf' },
      { id: '2', title: 'AI Guide', url: 'https://ai.com/guide' },
    ];

    render(
      <ChatMessage role="assistant" content="Test answer" sources={sources} />
    );

    const link1 = screen.getByRole('link', { name: /Tech Report/i });
    expect(link1).toHaveAttribute('href', 'https://example.com/report.pdf');
    expect(link1).toHaveAttribute('target', '_blank');

    const link2 = screen.getByRole('link', { name: /AI Guide/i });
    expect(link2).toHaveAttribute('href', 'https://ai.com/guide');
  });

  it('renders source without url as non-link', () => {
    const sources = [{ id: '1', title: 'No URL Source', url: null }];

    render(
      <ChatMessage role="assistant" content="Test" sources={sources} />
    );

    expect(screen.getByText('No URL Source')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /No URL Source/i })).not.toBeInTheDocument();
  });

  it('renders user messages differently from assistant messages', () => {
    const { container: userContainer } = render(
      <ChatMessage role="user" content="User question" />
    );

    expect(userContainer.querySelector('.justify-end')).toBeInTheDocument();
  });

  it('renders assistant messages on the left', () => {
    const { container } = render(
      <ChatMessage role="assistant" content="Assistant response" />
    );

    expect(container.querySelector('.justify-start')).toBeInTheDocument();
  });

  it('renders Untitled for sources without title', () => {
    const sources = [{ id: '1', title: null, url: 'https://example.com' }];

    render(
      <ChatMessage role="assistant" content="Test" sources={sources} />
    );

    expect(screen.getByText('Untitled')).toBeInTheDocument();
  });

  it('renders local paths as non-links', () => {
    const sources = [
      { id: '1', title: 'Local File', url: 'AGIC 2026/some-file.pdf' },
    ];

    render(
      <ChatMessage role="assistant" content="Test" sources={sources} />
    );

    expect(screen.getByText('Local File')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Local File/i })).not.toBeInTheDocument();
  });
});
