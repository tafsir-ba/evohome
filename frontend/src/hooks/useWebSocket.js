import { useState, useEffect, useCallback, useRef } from 'react';
import { toast } from 'sonner';

const WS_URL = process.env.REACT_APP_BACKEND_URL?.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/ws';

// Get token from cookie or localStorage for WebSocket auth
const getAuthToken = () => {
  // Try localStorage first (where login stores it)
  const stored = localStorage.getItem('auth_token');
  if (stored) return stored;
  
  // Fallback: try to get from cookie (session_token)
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'session_token') return value;
  }
  return null;
};

export const useWebSocket = (userId, onMessage) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const pingIntervalRef = useRef(null);

  const connect = useCallback(() => {
    if (!userId || wsRef.current?.readyState === WebSocket.OPEN) return;

    // Get auth token for secure WebSocket connection
    const token = getAuthToken();
    if (!token) {
      console.warn('No auth token available for WebSocket connection');
      return;
    }

    try {
      // Pass token as query parameter for authentication
      const ws = new WebSocket(`${WS_URL}/${userId}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('WebSocket connected');
        
        // Start ping interval to keep connection alive
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping');
          }
        }, 30000);
      };

      ws.onmessage = (event) => {
        if (event.data === 'pong') return; // Ignore pong responses
        
        try {
          const message = JSON.parse(event.data);
          setLastMessage(message);
          
          // Call custom handler if provided
          if (onMessage) {
            onMessage(message);
          }
          
          // Show toast notification based on event type
          if (message.type === 'document_sent') {
            toast.info(`New ${message.data.type}: ${message.data.title}`, {
              description: `CHF ${message.data.amount?.toLocaleString('de-CH')}`,
              action: {
                label: 'View',
                onClick: () => window.location.reload()
              }
            });
          } else if (message.type === 'quote_approved') {
            toast.success('Quote Approved!', {
              description: `${message.data.buyer_name} approved "${message.data.title}"`
            });
          } else if (message.type === 'quote_rejected') {
            toast.error('Quote Declined', {
              description: `${message.data.buyer_name} declined "${message.data.title}"`
            });
          } else if (message.type === 'change_requested') {
            toast.warning('Change Requested', {
              description: `${message.data.buyer_name} requested changes to "${message.data.title}"`
            });
          } else if (message.type === 'payment_confirmed') {
            toast.success('Payment Confirmed!', {
              description: `Invoice "${message.data.title}" has been marked as paid`
            });
          } else if (
            (message.type === 'vault_updated' || message.type === 'vault_shared') &&
            !message.data?.removed
          ) {
            toast.info('Document vault updated', {
              description: message.data?.title ? `"${message.data.title}"` : 'Your agent shared a file with you',
            });
          } else if (message.type === 'decision_updated' && message.data?.event === 'sent') {
            toast.info('New decision from your agent', {
              description: message.data?.title ? `"${message.data.title}"` : 'Open Decisions to respond',
            });
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        console.log('WebSocket disconnected');
        
        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        // Attempt to reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect WebSocket...');
          connect();
        }, 5000);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [userId, onMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (userId) {
      connect();
    }
    
    return () => {
      disconnect();
    };
  }, [userId, connect, disconnect]);

  return {
    isConnected,
    lastMessage,
    connect,
    disconnect
  };
};

export default useWebSocket;
