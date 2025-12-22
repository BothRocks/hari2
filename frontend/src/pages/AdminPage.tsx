import { DocumentsTable } from '@/components/admin/DocumentsTable';
import { QualityChart } from '@/components/admin/QualityChart';
import { Separator } from '@/components/ui/separator';

export function AdminPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-muted-foreground">Manage documents and monitor quality</p>
      </div>

      <QualityChart />

      <Separator />

      <div>
        <h2 className="text-xl font-semibold mb-4">Documents</h2>
        <DocumentsTable />
      </div>
    </div>
  );
}
