import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThinkingSteps } from './ThinkingSteps';

describe('ThinkingSteps', () => {
  it('renders thinking steps', () => {
    const steps = [
      { step: 'retrieve', message: 'Searching...', isError: false },
      { step: 'evaluate', message: 'Evaluating...', isError: false },
    ];

    render(<ThinkingSteps steps={steps} />);

    expect(screen.getByText('Searching...')).toBeInTheDocument();
    expect(screen.getByText('Evaluating...')).toBeInTheDocument();
  });

  it('renders error steps with warning style', () => {
    const steps = [
      { step: 'research', message: 'Web search failed...', isError: true },
    ];

    render(<ThinkingSteps steps={steps} />);

    const errorElement = screen.getByText('Web search failed...');
    expect(errorElement.closest('div')).toHaveClass('text-yellow-600');
  });

  it('renders nothing when no steps', () => {
    const { container } = render(<ThinkingSteps steps={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
