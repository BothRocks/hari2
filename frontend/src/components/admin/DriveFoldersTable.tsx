import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface DriveFolder {
  id: string;
  google_folder_id: string;
  name: string;
  is_active: boolean;
  last_sync_at: string | null;
  created_at: string;
  pending_count: number;
  failed_count: number;
  completed_count: number;
}

interface DriveFoldersTableProps {
  folders: DriveFolder[];
  onSync: (id: string, processFiles: boolean) => void;
  onDelete: (id: string) => void;
  onRetryFailed: (id: string) => void;
}

export function DriveFoldersTable({ folders, onSync, onDelete, onRetryFailed }: DriveFoldersTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Google Folder ID</TableHead>
          <TableHead>Files</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Last Sync</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {folders.map((folder) => (
          <TableRow key={folder.id}>
            <TableCell className="font-medium">{folder.name}</TableCell>
            <TableCell className="font-mono text-sm">{folder.google_folder_id}</TableCell>
            <TableCell className="space-x-2">
              {folder.completed_count > 0 && (
                <Badge variant="secondary" className="bg-green-100 text-green-800">
                  {folder.completed_count} ok
                </Badge>
              )}
              {folder.pending_count > 0 && (
                <Badge variant="secondary" className="bg-blue-100 text-blue-800 cursor-pointer" onClick={() => onSync(folder.id, true)}>
                  {folder.pending_count} pending
                </Badge>
              )}
              {folder.failed_count > 0 && (
                <Badge variant="secondary" className="bg-red-100 text-red-800 cursor-pointer" onClick={() => onRetryFailed(folder.id)}>
                  {folder.failed_count} failed
                </Badge>
              )}
              {folder.completed_count === 0 && folder.pending_count === 0 && folder.failed_count === 0 && (
                <span className="text-muted-foreground text-sm">-</span>
              )}
            </TableCell>
            <TableCell>
              <Badge className={folder.is_active ? 'bg-green-500' : 'bg-gray-500'}>
                {folder.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </TableCell>
            <TableCell>
              {folder.last_sync_at
                ? new Date(folder.last_sync_at).toLocaleString()
                : 'Never'}
            </TableCell>
            <TableCell className="space-x-2">
              <Button variant="outline" size="sm" onClick={() => onSync(folder.id, false)}>
                Sync Only
              </Button>
              <Button variant="default" size="sm" onClick={() => onSync(folder.id, true)}>
                Sync & Process
              </Button>
              <Button variant="ghost" size="sm" onClick={() => onDelete(folder.id)}>
                Delete
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
