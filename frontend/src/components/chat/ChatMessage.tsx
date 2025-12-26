import ReactMarkdown from 'react-markdown';
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
        {role === 'assistant' ? (
          <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0 prose-headings:my-3 prose-headings:font-semibold prose-pre:my-2">
            <ReactMarkdown
              components={{
                code: ({ children, className, ...props }) => {
                  const isBlock = className?.includes('language-') || String(children).includes('\n');
                  return isBlock ? (
                    <pre className="bg-muted p-3 rounded-md overflow-x-auto">
                      <code {...props}>{children}</code>
                    </pre>
                  ) : (
                    <code className="bg-muted px-1 py-0.5 rounded text-sm" {...props}>
                      {children}
                    </code>
                  );
                },
                pre: ({ children }) => <>{children}</>,
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{content}</p>
        )}
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
