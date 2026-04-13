import { useState, useCallback } from 'react';
import { AgentLayout } from '../../components/AgentLayout';
import { Feed } from '../../components/Feed';
import { useAuth } from '../../context/AuthContext';
import { useWebSocket } from '../../hooks/useWebSocket';

/**
 * Agent Feed Page
 * 
 * Uses the shared Feed component with agent permissions:
 * - Full controls
 * - Post creation
 * - Multi-client targeting
 * - View all recipients
 * - Real-time updates via WebSocket
 */
export const AgentFeed = () => {
  const { user } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);

  // Handle WebSocket messages for real-time feed updates
  const handleWebSocketMessage = useCallback((message) => {
    // Refresh feed when relevant events occur
    if (['activity_created', 'activity_reply'].includes(message.type)) {
      setRefreshKey(prev => prev + 1);
    }
  }, []);

  useWebSocket(user?.user_id, handleWebSocketMessage);

  return (
    <AgentLayout>
      <Feed isAgent={true} embedded={false} mobileFab key={refreshKey} />
    </AgentLayout>
  );
};

export default AgentFeed;
