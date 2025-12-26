import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { documentsApi } from '@/lib/api';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export function DocumentsTable() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  });

  if (isLoading) return <div>Loading...</div>;

  const documents = data?.data.items || [];

  return (
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
        {documents.map((doc: any) => (
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
  );
}
