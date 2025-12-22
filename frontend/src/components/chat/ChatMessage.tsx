import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Source {
  id: string | null;
  title: string | null;
  url: string | null;
}

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
}

export function ChatMessage({ role, content, sources }: ChatMessageProps) {
  return (
    <div className={`flex ${role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <Card className={`max-w-[80%] p-4 ${role === 'user' ? 'bg-primary text-primary-foreground' : ''}`}>
        <p className="whitespace-pre-wrap">{content}</p>
        {sources && sources.length > 0 && (
          <div className="mt-3 pt-3 border-t">
            <p className="text-xs text-muted-foreground mb-2">Sources:</p>
            <div className="flex flex-wrap gap-1">
              {sources.map((source, i) => (
                <Badge key={i} variant="outline" className="text-xs">
                  {source.title || 'Untitled'}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
