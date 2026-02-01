import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatInputProps {
  onSubmit: (message: string, ignoreDecay: boolean) => void;
  isLoading: boolean;
}

export function ChatInput({ onSubmit, isLoading }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [ignoreDecay, setIgnoreDecay] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSubmit(message, ignoreDecay);
      setMessage('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="flex gap-2">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Ask a question..."
          className="flex-1 min-h-[60px] resize-none"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
        />
        <Button type="submit" disabled={isLoading || !message.trim()}>
          {isLoading ? 'Thinking...' : 'Ask'}
        </Button>
      </div>
      <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
        <input
          type="checkbox"
          checked={ignoreDecay}
          onChange={(e) => setIgnoreDecay(e.target.checked)}
          className="rounded border-gray-300"
        />
        Include old documents
      </label>
    </form>
  );
}
