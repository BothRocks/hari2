import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { DriveFoldersTable } from '@/components/admin/DriveFoldersTable';
import { driveApi } from '@/lib/api';
import { AxiosError } from 'axios';

export function DrivePage() {
  const [folders, setFolders] = useState([]);
  const [serviceEmail, setServiceEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [newFolderId, setNewFolderId] = useState('');
  const [newFolderName, setNewFolderName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [foldersRes, serviceRes] = await Promise.all([
        driveApi.listFolders(),
        driveApi.getServiceAccount().catch(() => ({ data: { email: null } })),
      ]);
      setFolders(foldersRes.data.folders);
      setServiceEmail(serviceRes.data.email);
    } catch (err) {
      const axiosError = err as AxiosError<{ detail: string }>;
      setError(axiosError.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }

  async function handleAddFolder() {
    if (!newFolderId.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await driveApi.createFolder(newFolderId.trim(), newFolderName.trim() || undefined);
      setNewFolderId('');
      setNewFolderName('');
      await loadData();
    } catch (err) {
      const axiosError = err as AxiosError<{ detail: string }>;
      setError(axiosError.response?.data?.detail || 'Failed to add folder');
    } finally {
      setAdding(false);
    }
  }

  async function handleSync(id: string, processFiles: boolean) {
    setError(null);
    try {
      await driveApi.syncFolder(id, processFiles);
      await loadData();
    } catch (err) {
      const axiosError = err as AxiosError<{ detail: string }>;
      setError(axiosError.response?.data?.detail || 'Failed to sync folder');
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this folder?')) return;
    setError(null);
    try {
      await driveApi.deleteFolder(id);
      await loadData();
    } catch (err) {
      const axiosError = err as AxiosError<{ detail: string }>;
      setError(axiosError.response?.data?.detail || 'Failed to delete folder');
    }
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Google Drive Sync</h1>
        <Button onClick={loadData} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </Button>
      </div>

      {/* Error display */}
      {error && (
        <div className="bg-destructive/15 text-destructive px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Service account info */}
      {serviceEmail && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Service Account</CardTitle>
            <CardDescription>Share your folders with this email address</CardDescription>
          </CardHeader>
          <CardContent>
            <code className="bg-muted px-2 py-1 rounded">{serviceEmail}</code>
          </CardContent>
        </Card>
      )}

      {/* Add folder form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Add Folder</CardTitle>
          <CardDescription>Enter a Google Drive folder URL or ID to start syncing</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-4">
          <Input
            placeholder="Folder URL or ID"
            value={newFolderId}
            onChange={(e) => setNewFolderId(e.target.value)}
            className="max-w-md"
            disabled={adding}
          />
          <Input
            placeholder="Name (optional)"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            className="max-w-xs"
            disabled={adding}
          />
          <Button onClick={handleAddFolder} disabled={adding || !newFolderId.trim()}>
            {adding ? 'Adding...' : 'Add Folder'}
          </Button>
        </CardContent>
      </Card>

      {/* Folders table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Registered Folders</CardTitle>
        </CardHeader>
        <CardContent>
          {folders.length > 0 ? (
            <DriveFoldersTable
              folders={folders}
              onSync={handleSync}
              onDelete={handleDelete}
            />
          ) : (
            <p className="text-muted-foreground">No folders registered yet.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
