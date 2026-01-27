import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { JobsTable } from '@/components/admin/JobsTable';
import { jobsApi } from '@/lib/api';

interface JobStats {
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

interface JobLog {
  id: string;
  level: string;
  message: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

interface JobDetail {
  id: string;
  job_type: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  logs: JobLog[];
}

const levelColors: Record<string, string> = {
  INFO: 'bg-blue-500',
  WARNING: 'bg-yellow-500',
  ERROR: 'bg-red-500',
};

export function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [jobsRes, statsRes] = await Promise.all([
        jobsApi.list({ status: statusFilter, page, pageSize }),
        jobsApi.getStats(),
      ]);
      setJobs(jobsRes.data.items);
      setTotal(jobsRes.data.total);
      setStats(statsRes.data);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleRetry(id: string) {
    await jobsApi.retry(id);
    loadData();
  }

  async function handleBulkRetry() {
    await jobsApi.bulkRetry();
    loadData();
  }

  async function handleArchive(filter: 'all' | 'failed' | 'completed') {
    const labels = { all: 'todos los jobs', failed: 'los jobs failed', completed: 'los jobs completed' };
    if (!confirm(`Archivar ${labels[filter]}?`)) return;
    await jobsApi.archive(filter);
    setPage(1);
    loadData();
  }

  async function handleViewDetails(job: { id: string }) {
    try {
      const res = await jobsApi.getJob(job.id);
      setSelectedJob(res.data);
      setDialogOpen(true);
    } catch (err) {
      console.error('Failed to load job details:', err);
    }
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Background Jobs</h1>
        <Button onClick={loadData}>Refresh</Button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          {Object.entries(stats).map(([key, value]) => (
            <Card key={key} className="cursor-pointer" onClick={() => { setStatusFilter(key === statusFilter ? undefined : key); setPage(1); }}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm capitalize">{key}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{value}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        {stats?.failed && stats.failed > 0 && (
          <Button variant="outline" onClick={handleBulkRetry}>
            Retry All Failed ({stats.failed})
          </Button>
        )}
        <Button variant="outline" onClick={() => handleArchive('all')}>
          Archivar todos
        </Button>
        <Button variant="outline" onClick={() => handleArchive('completed')}>
          Archivar completed
        </Button>
        <Button variant="outline" onClick={() => handleArchive('failed')}>
          Archivar failed
        </Button>
      </div>

      {/* Jobs table */}
      <Card>
        <CardContent className="pt-6">
          <JobsTable
            jobs={jobs}
            onRetry={handleRetry}
            onViewDetails={handleViewDetails}
          />
          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <span className="text-sm text-muted-foreground">
                Pagina {page} de {totalPages} ({total} jobs)
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                  Anterior
                </Button>
                <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Job Details Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Job Details</DialogTitle>
          </DialogHeader>
          {selectedJob && (
            <div className="space-y-4">
              {/* Job Info */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-muted-foreground">Type:</span> {selectedJob.job_type}</div>
                <div><span className="text-muted-foreground">Status:</span> {selectedJob.status}</div>
                <div><span className="text-muted-foreground">Created:</span> {new Date(selectedJob.created_at).toLocaleString()}</div>
                {selectedJob.completed_at && (
                  <div><span className="text-muted-foreground">Completed:</span> {new Date(selectedJob.completed_at).toLocaleString()}</div>
                )}
              </div>

              {/* Payload */}
              <div>
                <h4 className="text-sm font-medium mb-1">Payload</h4>
                <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                  {JSON.stringify(selectedJob.payload, null, 2)}
                </pre>
              </div>

              {/* Logs */}
              <div>
                <h4 className="text-sm font-medium mb-1">Logs ({selectedJob.logs.length})</h4>
                <ScrollArea className="h-[300px] border rounded">
                  <div className="p-2 space-y-2">
                    {selectedJob.logs.map((log) => (
                      <div key={log.id} className="text-xs border-b pb-2 last:border-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge className={levelColors[log.level] || 'bg-gray-500'} variant="secondary">
                            {log.level}
                          </Badge>
                          <span className="text-muted-foreground">
                            {new Date(log.created_at).toLocaleTimeString()}
                          </span>
                        </div>
                        <div>{log.message}</div>
                        {log.details && (
                          <pre className="mt-1 text-xs bg-muted p-1 rounded overflow-x-auto">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))}
                    {selectedJob.logs.length === 0 && (
                      <div className="text-muted-foreground text-center py-4">No logs yet</div>
                    )}
                  </div>
                </ScrollArea>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
