import { useState, useCallback, useRef } from 'react';
import { queryApi } from '@/lib/api';
import { SSEEvent } from '@/lib/sse';
import { ChatInput } from '@/components/chat/ChatInput';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ThinkingSteps, ThinkingStep } from '@/components/chat/ThinkingSteps';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';

interface Source {
  id: string | null;
  title: string | null;
  url: string | null;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  thinkingSteps?: ThinkingStep[];
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentThinking, setCurrentThinking] = useState<ThinkingStep[]>([]);
  const [currentContent, setCurrentContent] = useState('');

  // Use refs to access current values in callback without recreating it
  const currentContentRef = useRef('');
  const currentThinkingRef = useRef<ThinkingStep[]>([]);

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.type === 'thinking') {
      const data = event.data as { step: string; message: string };
      const newStep = { step: data.step, message: data.message };
      currentThinkingRef.current = [...currentThinkingRef.current, newStep];
      setCurrentThinking([...currentThinkingRef.current]);
    } else if (event.type === 'error') {
      const data = event.data as { step: string; message: string };
      const newStep = { step: data.step, message: data.message, isError: true };
      currentThinkingRef.current = [...currentThinkingRef.current, newStep];
      setCurrentThinking([...currentThinkingRef.current]);
    } else if (event.type === 'chunk') {
      const data = event.data as { content: string };
      currentContentRef.current = currentContentRef.current + data.content;
      setCurrentContent(currentContentRef.current);
    } else if (event.type === 'sources') {
      const data = event.data as { internal: Source[]; external: Source[] };
      const allSources = [...(data.internal || []), ...(data.external || [])];
      // Capture current values before resetting (refs could be mutated before render)
      const finalContent = currentContentRef.current;
      const finalThinkingSteps = [...currentThinkingRef.current];
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: finalContent,
          sources: allSources,
          thinkingSteps: finalThinkingSteps,
        },
      ]);
      // Reset refs for next query
      currentContentRef.current = '';
      currentThinkingRef.current = [];
      setCurrentThinking([]);
      setCurrentContent('');
    } else if (event.type === 'done') {
      setIsLoading(false);
    }
  }, []);

  const handleSubmit = async (message: string) => {
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: message }]);
    setIsLoading(true);

    // Reset streaming state
    currentContentRef.current = '';
    currentThinkingRef.current = [];
    setCurrentThinking([]);
    setCurrentContent('');

    try {
      await queryApi.streamAsk(message, handleEvent);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}` },
      ]);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <ScrollArea className="flex-1 pr-4">
        <div className="space-y-4 pb-4">
          {messages.length === 0 && !isLoading ? (
            <div className="text-center text-muted-foreground py-12">
              <h2 className="text-2xl font-semibold mb-2">Welcome to HARI</h2>
              <p>Ask any question about your knowledge base</p>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                <div key={i}>
                  {msg.role === 'assistant' && msg.thinkingSteps && msg.thinkingSteps.length > 0 && (
                    <ThinkingSteps steps={msg.thinkingSteps} />
                  )}
                  <ChatMessage role={msg.role} content={msg.content} sources={msg.sources} />
                </div>
              ))}
              {isLoading && (
                <div>
                  <ThinkingSteps steps={currentThinking} isLoading={true} />
                  {currentContent && (
                    <Card className="max-w-[80%] p-4">
                      <p className="whitespace-pre-wrap">{currentContent}</p>
                    </Card>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </ScrollArea>
      <div className="pt-4 border-t">
        <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
    </div>
  );
}
