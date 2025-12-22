import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { queryApi } from '@/lib/api';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: { id: string | null; title: string | null; url: string | null }[];
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);

  const queryMutation = useMutation({
    mutationFn: (query: string) => queryApi.ask(query),
    onSuccess: (response) => {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: response.data.answer,
          sources: response.data.sources,
        },
      ]);
    },
    onError: (error: Error) => {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${error.message}` },
      ]);
    },
  });

  const handleSubmit = (message: string) => {
    setMessages(prev => [...prev, { role: 'user', content: message }]);
    queryMutation.mutate(message);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <ScrollArea className="flex-1 pr-4">
        <div className="space-y-4 pb-4">
          {messages.length === 0 ? (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-2xl font-semibold mb-2">Welcome to HARI</h2>
              <p>Ask any question about your knowledge base</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <ChatMessage key={i} {...msg} />
            ))
          )}
        </div>
      </ScrollArea>
      <div className="pt-4 border-t">
        <ChatInput onSubmit={handleSubmit} isLoading={queryMutation.isPending} />
      </div>
    </div>
  );
}
