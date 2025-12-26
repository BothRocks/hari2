import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';

interface Document {
  id: string;
  url?: string;
  title?: string;
  author?: string;
  published_date?: string;
  processing_status: string;
  quality_score?: number;
  quick_summary?: string;
  summary?: string;
  keywords?: string[];
  industries?: string[];
  metadata?: Record<string, unknown>;
  needs_review?: boolean;
  review_reasons?: string[];
  original_metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [editingTitle, setEditingTitle] = useState(false);
  const [editingAuthor, setEditingAuthor] = useState(false);
  const [titleValue, setTitleValue] = useState('');
  const [authorValue, setAuthorValue] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['document', id],
    queryFn: async () => {
      const response = await documentsApi.get(id!);
      return response.data as Document;
    },
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; author?: string }) =>
      documentsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      setEditingTitle(false);
      setEditingAuthor(false);
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: () => documentsApi.reprocess(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
    },
  });

  const markReviewedMutation = useMutation({
    mutationFn: () => documentsApi.markReviewed(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
    },
  });

  if (isLoading) {
    return (
      <div className="container mx-auto py-8">
        <div>Loading...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-red-500">Error loading document</div>
        <Button variant="outline" onClick={() => navigate('/admin')} className="mt-4">
          Back to Documents
        </Button>
      </div>
    );
  }

  const doc = data;

  const handleStartEditTitle = () => {
    setTitleValue(doc.title || '');
    setEditingTitle(true);
  };

  const handleStartEditAuthor = () => {
    setAuthorValue(doc.author || '');
    setEditingAuthor(true);
  };

  const handleSaveTitle = () => {
    updateMutation.mutate({ title: titleValue });
  };

  const handleSaveAuthor = () => {
    updateMutation.mutate({ author: authorValue });
  };

  const statusVariant = doc.processing_status === 'COMPLETED' ? 'default' : 'destructive';

  return (
    <div className="container mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <Button variant="ghost" onClick={() => navigate('/admin')} className="mb-2">
            &larr; Back to Documents
          </Button>
          <h1 className="text-2xl font-bold">{doc.title || 'Untitled Document'}</h1>
          {doc.url && (
            <a
              href={doc.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-500 hover:underline"
            >
              {doc.url}
            </a>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => reprocessMutation.mutate()}
            disabled={reprocessMutation.isPending}
          >
            {reprocessMutation.isPending ? 'Re-processing...' : 'Re-process'}
          </Button>
        </div>
      </div>

      {/* Needs Review Alert */}
      {doc.needs_review && (
        <Card className="border-yellow-500 bg-yellow-50">
          <CardHeader className="pb-2">
            <CardTitle className="text-yellow-800 flex items-center gap-2">
              <span>Needs Review</span>
              <Badge variant="outline" className="border-yellow-500 text-yellow-700">
                Review Required
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {doc.review_reasons && doc.review_reasons.length > 0 && (
              <div>
                <h4 className="font-medium text-yellow-800 mb-2">Review Reasons:</h4>
                <ul className="list-disc list-inside space-y-1">
                  {doc.review_reasons.map((reason, idx) => (
                    <li key={idx} className="text-yellow-700">{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            {doc.original_metadata && Object.keys(doc.original_metadata).length > 0 && (
              <div>
                <h4 className="font-medium text-yellow-800 mb-2">Original Metadata:</h4>
                <pre className="text-xs bg-yellow-100 p-2 rounded overflow-auto">
                  {JSON.stringify(doc.original_metadata, null, 2)}
                </pre>
              </div>
            )}
            <Button
              onClick={() => markReviewedMutation.mutate()}
              disabled={markReviewedMutation.isPending}
              className="bg-yellow-600 hover:bg-yellow-700"
            >
              {markReviewedMutation.isPending ? 'Marking...' : 'Mark as Reviewed'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Basic Info */}
      <Card>
        <CardHeader>
          <CardTitle>Document Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Title */}
          <div>
            <label className="text-sm font-medium text-gray-500">Title</label>
            {editingTitle ? (
              <div className="flex gap-2 mt-1">
                <Input
                  value={titleValue}
                  onChange={(e) => setTitleValue(e.target.value)}
                  placeholder="Enter title"
                />
                <Button onClick={handleSaveTitle} disabled={updateMutation.isPending}>
                  Save
                </Button>
                <Button variant="outline" onClick={() => setEditingTitle(false)}>
                  Cancel
                </Button>
              </div>
            ) : (
              <div
                className="mt-1 p-2 border rounded cursor-pointer hover:bg-gray-50"
                onClick={handleStartEditTitle}
              >
                {doc.title || <span className="text-gray-400">Click to add title</span>}
              </div>
            )}
          </div>

          {/* Author */}
          <div>
            <label className="text-sm font-medium text-gray-500">Author</label>
            {editingAuthor ? (
              <div className="flex gap-2 mt-1">
                <Input
                  value={authorValue}
                  onChange={(e) => setAuthorValue(e.target.value)}
                  placeholder="Enter author"
                />
                <Button onClick={handleSaveAuthor} disabled={updateMutation.isPending}>
                  Save
                </Button>
                <Button variant="outline" onClick={() => setEditingAuthor(false)}>
                  Cancel
                </Button>
              </div>
            ) : (
              <div
                className="mt-1 p-2 border rounded cursor-pointer hover:bg-gray-50"
                onClick={handleStartEditAuthor}
              >
                {doc.author || <span className="text-gray-400">Click to add author</span>}
              </div>
            )}
          </div>

          <Separator />

          {/* Read-only fields */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-500">Status</label>
              <div className="mt-1">
                <Badge variant={statusVariant}>{doc.processing_status}</Badge>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Quality Score</label>
              <div className="mt-1 font-medium">{doc.quality_score?.toFixed(0) || '-'}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Published Date</label>
              <div className="mt-1">{doc.published_date || '-'}</div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-500">Created</label>
              <div className="mt-1">{new Date(doc.created_at).toLocaleString()}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Summary */}
      {doc.quick_summary && (
        <Card>
          <CardHeader>
            <CardTitle>Quick Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{doc.quick_summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Full Summary */}
      {doc.summary && (
        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap">{doc.summary}</p>
          </CardContent>
        </Card>
      )}

      {/* Keywords and Industries */}
      <div className="grid grid-cols-2 gap-6">
        {doc.keywords && doc.keywords.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Keywords</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {doc.keywords.map((keyword, idx) => (
                  <Badge key={idx} variant="secondary">{keyword}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {doc.industries && doc.industries.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Industries</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {doc.industries.map((industry, idx) => (
                  <Badge key={idx} variant="outline">{industry}</Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Metadata */}
      {doc.metadata && Object.keys(doc.metadata).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Metadata</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-gray-100 p-4 rounded overflow-auto">
              {JSON.stringify(doc.metadata, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
