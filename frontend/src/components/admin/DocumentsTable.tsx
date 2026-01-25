import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { documentsApi } from '@/lib/api';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChevronLeft, ChevronRight, Search } from 'lucide-react';

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
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const pageSize = 20;

  const { data, isLoading } = useQuery({
    queryKey: ['documents', showNeedsReview, page, search],
    queryFn: () => documentsApi.list({
      needsReview: showNeedsReview ? true : undefined,
      page,
      pageSize,
      search: search || undefined,
    }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  };

  if (isLoading) return <div>Loading...</div>;

  const documents = data?.data.items || [];
  const total = data?.data.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-4">
          <form onSubmit={handleSearch} className="flex items-center space-x-2">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search title or author..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-8 w-64"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="needs-review"
              checked={showNeedsReview}
              onChange={(e) => { setShowNeedsReview(e.target.checked); setPage(1); }}
              className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
            />
            <label htmlFor="needs-review" className="text-sm font-medium">
              Needs review only
            </label>
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          {total} documents
        </div>
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
    {totalPages > 1 && (
      <div className="flex items-center justify-between mt-4">
        <div className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    )}
    </div>
  );
}
