import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { JobsTable } from '@/components/admin/JobsTable';
import { jobsApi } from '@/lib/api';

interface JobStats {
  pending: number;
  running: number;
  completed: number;
  failed: number;
}

export function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState<JobStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  async function loadData() {
    setLoading(true);
    try {
      const [jobsRes, statsRes] = await Promise.all([
        jobsApi.list(statusFilter),
        jobsApi.getStats(),
      ]);
      setJobs(jobsRes.data.jobs);
      setStats(statsRes.data);
    } finally {
      setLoading(false);
    }
  }

  async function handleRetry(id: string) {
    await jobsApi.retry(id);
    loadData();
  }

  async function handleBulkRetry() {
    await jobsApi.bulkRetry();
    loadData();
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
            <Card key={key} className="cursor-pointer" onClick={() => setStatusFilter(key === statusFilter ? undefined : key)}>
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
      {stats?.failed && stats.failed > 0 && (
        <Button variant="outline" onClick={handleBulkRetry}>
          Retry All Failed ({stats.failed})
        </Button>
      )}

      {/* Jobs table */}
      <Card>
        <CardContent className="pt-6">
          <JobsTable
            jobs={jobs}
            onRetry={handleRetry}
            onViewDetails={(job) => console.log('View:', job)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
