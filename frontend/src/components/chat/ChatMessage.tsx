import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink } from 'lucide-react';

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

// Check if URL is a valid external link (http/https)
function isValidExternalUrl(url: string | null): url is string {
  return url !== null && (url.startsWith('http://') || url.startsWith('https://'));
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
                isValidExternalUrl(source.url) ? (
                  <a
                    key={source.id || i}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1"
                  >
                    <Badge variant="outline" className="text-xs hover:bg-accent cursor-pointer">
                      {source.title || 'Untitled'}
                      <ExternalLink className="h-3 w-3 ml-1" />
                    </Badge>
                  </a>
                ) : (
                  <Badge key={source.id || i} variant="outline" className="text-xs">
                    {source.title || 'Untitled'}
                  </Badge>
                )
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
