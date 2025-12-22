import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface Job {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface JobsTableProps {
  jobs: Job[];
  onRetry: (id: string) => void;
  onViewDetails: (job: Job) => void;
}

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-500',
  running: 'bg-blue-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
};

export function JobsTable({ jobs, onRetry, onViewDetails }: JobsTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => (
          <TableRow key={job.id}>
            <TableCell className="font-mono text-sm">{job.job_type}</TableCell>
            <TableCell>
              <Badge className={statusColors[job.status] || 'bg-gray-500'}>
                {job.status}
              </Badge>
            </TableCell>
            <TableCell>{new Date(job.created_at).toLocaleString()}</TableCell>
            <TableCell className="space-x-2">
              <Button variant="ghost" size="sm" onClick={() => onViewDetails(job)}>
                Logs
              </Button>
              {job.status === 'failed' && (
                <Button variant="outline" size="sm" onClick={() => onRetry(job.id)}>
                  Retry
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
