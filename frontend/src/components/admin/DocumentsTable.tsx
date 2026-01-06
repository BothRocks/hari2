import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { documentsApi } from '@/lib/api';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface Document {
  id: string;
  title?: string;
  url?: string;
  processing_status: string;
  quality_score?: number;
}

export function DocumentsTable() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [showNeedsReview, setShowNeedsReview] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['documents', showNeedsReview],
    queryFn: () => documentsApi.list(1, 20, undefined, showNeedsReview ? true : undefined),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  });

  if (isLoading) return <div>Loading...</div>;

  const documents = data?.data.items || [];

  return (
    <div>
      <div className="flex items-center space-x-2 mb-4">
        <input
          type="checkbox"
          id="needs-review"
          checked={showNeedsReview}
          onChange={(e) => setShowNeedsReview(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
        />
        <label htmlFor="needs-review" className="text-sm font-medium">
          Show only documents needing review
        </label>
      </div>
      <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Title</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Quality</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((doc: Document) => (
          <TableRow key={doc.id}>
            <TableCell
              className="font-medium cursor-pointer hover:underline"
              onClick={() => navigate(`/admin/documents/${doc.id}`)}
            >
              {doc.title || doc.url || 'Untitled'}
            </TableCell>
            <TableCell>
              <Badge variant={doc.processing_status === 'completed' ? 'default' : 'destructive'}>
                {doc.processing_status}
              </Badge>
            </TableCell>
            <TableCell>{doc.quality_score?.toFixed(0) || '-'}</TableCell>
            <TableCell>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => deleteMutation.mutate(doc.id)}
              >
                Delete
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
    </div>
  );
}
