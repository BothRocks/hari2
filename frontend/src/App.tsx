import { Routes, Route } from 'react-router-dom';
import { Layout } from '@/components/layout/Layout';
import { ChatPage } from '@/pages/ChatPage';
import { AdminPage } from '@/pages/AdminPage';
import { JobsPage } from '@/pages/JobsPage';
import { AuthProvider } from '@/contexts/AuthContext';

function App() {
  return (
    <AuthProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </Layout>
    </AuthProvider>
  );
}

export default App;
