import { useQuery } from '@tanstack/react-query';
import { adminApi } from '@/lib/api';
import { Card } from '@/components/ui/card';

export function QualityChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['quality-report'],
    queryFn: () => adminApi.qualityReport(),
  });

  if (isLoading) return <div>Loading...</div>;

  const report = data?.data;
  const grades = report?.grade_distribution || {};

  return (
    <Card className="p-4">
      <h3 className="font-semibold mb-4">Quality Distribution</h3>
      <div className="flex gap-4">
        {['A', 'B', 'C', 'D'].map(grade => (
          <div key={grade} className="text-center">
            <div className="text-2xl font-bold">{grades[grade] || 0}</div>
            <div className="text-sm text-muted-foreground">Grade {grade}</div>
          </div>
        ))}
      </div>
      <div className="mt-4 pt-4 border-t">
        <p className="text-sm text-muted-foreground">
          Total: {report?.total_documents || 0} documents |
          Avg Score: {report?.average_score?.toFixed(1) || 0}
        </p>
      </div>
    </Card>
  );
}
