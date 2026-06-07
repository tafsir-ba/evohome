import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDataContext } from '../../context/DataContext';
import { useAuth } from '../../context/AuthContext';
import { AgentLayout } from '../../components/AgentLayout';
import { Button } from '../../components/ui/button';
import { ControlTower } from '../../components/dashboard/ControlTower';
import { Feed } from '../../components/Feed';
import { useWebSocket } from '../../hooks/useWebSocket';
import { LayoutList } from 'lucide-react';

/**
 * Agent home — command center: attention metrics + client feed (posts / media / docs).
 * Intentionally no command bar or “working context” strip; project/client filters live on /agent/feed when needed.
 */
export const AgentHomePage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { projects, refreshProjects } = useDataContext();
  const [feedKey, setFeedKey] = useState(0);

  const handleRefresh = () => {
    refreshProjects();
    setFeedKey((k) => k + 1);
  };

  const handleWebSocketMessage = useCallback((message) => {
    if (['activity_created', 'activity_reply', 'new_activity'].includes(message.type)) {
      setFeedKey((k) => k + 1);
    }
  }, []);

  useWebSocket(user?.user_id, handleWebSocketMessage);

  return (
    <AgentLayout>
      <div className="space-y-6 sm:space-y-8 pb-8 sm:pb-10" data-testid="agent-home-page">
        <ControlTower projectCount={projects.length} onRefresh={handleRefresh} />

        <section className="space-y-4" aria-labelledby="client-updates-heading">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <h2 id="client-updates-heading" className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                Share with clients
              </h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-xl">
                Post updates, photos, PDFs, and status notes. Buyers see these in their timeline.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:justify-end">
              <Button variant="outline" size="sm" onClick={() => navigate('/agent/feed')} className="w-full sm:w-auto shrink-0">
                <LayoutList className="w-4 h-4 mr-2" />
                Full feed &amp; filters
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate('/agent/documents')} className="w-full sm:w-auto shrink-0">
                Documents
              </Button>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card/40 p-4 sm:p-6 shadow-sm">
            <Feed isAgent embedded={false} compact highlightActivityId={null} key={feedKey} />
          </div>
        </section>
      </div>
    </AgentLayout>
  );
};

export default AgentHomePage;
