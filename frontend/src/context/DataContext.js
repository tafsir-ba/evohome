import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from './AuthContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

// Storage key prefix for persisting selection (user-specific)
const STORAGE_KEY_PREFIX = 'evohome_selected_project_';

// Get user-specific storage key
const getStorageKey = (userId) => userId ? `${STORAGE_KEY_PREFIX}${userId}` : null;

/**
 * DataContext - SINGLE SOURCE OF TRUTH for project data.
 * 
 * Key optimizations:
 * 1. Deduplication of fetches via fetchingRef
 * 2. Skip re-fetch if same user (lastUserIdRef) 
 * 3. Memoized context value to prevent consumer re-renders
 * 4. Mounted check to prevent state updates after unmount
 */
const DataContext = createContext(null);

export const useDataContext = () => {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useDataContext must be used within DataProvider');
  }
  return context;
};

export const DataProvider = ({ children }) => {
  const { user } = useAuth();
  
  // Core state
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectIdState] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Refs to prevent duplicate fetches and track state
  const fetchingRef = useRef(false);
  const lastUserIdRef = useRef(null);
  const mountedRef = useRef(true);
  
  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // Get storage key for current user - memoized
  const storageKey = useMemo(() => getStorageKey(user?.user_id), [user?.user_id]);
  
  // Setter that persists to localStorage
  const setSelectedProjectId = useCallback((projectId) => {
    const value = projectId || '';
    setSelectedProjectIdState(value);
    if (storageKey && value) {
      try {
        localStorage.setItem(storageKey, value);
      } catch {}
    }
  }, [storageKey]);
  
  // Fetch projects - with deduplication
  const fetchProjects = useCallback(async () => {
    // Prevent duplicate fetches
    if (fetchingRef.current) return;
    if (!storageKey) {
      setLoading(false);
      return;
    }
    
    fetchingRef.current = true;
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(`${API}/projects`, { credentials: 'include', headers: getAuthHeaders() });
      
      // Check if still mounted
      if (!mountedRef.current) return;
      
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        
        // Validate and set selection
        let storedSelection = '';
        try {
          storedSelection = localStorage.getItem(storageKey) || '';
        } catch {}
        
        if (data.length > 0) {
          const isValid = data.some(p => p.project_id === storedSelection);
          const finalSelection = isValid ? storedSelection : data[0].project_id;
          setSelectedProjectIdState(finalSelection);
          if (!isValid) {
            try {
              localStorage.setItem(storageKey, finalSelection);
            } catch {}
          }
        } else {
          setSelectedProjectIdState('');
        }
      } else if (res.status === 401) {
        setProjects([]);
        setSelectedProjectIdState('');
      } else {
        setError('Failed to load projects');
      }
    } catch (err) {
      if (mountedRef.current) {
        console.error('Failed to fetch projects:', err);
        setError('Failed to load projects');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
      fetchingRef.current = false;
    }
  }, [storageKey]);

  // Refresh projects - resets the fetching guard
  const refreshProjects = useCallback(async () => {
    fetchingRef.current = false;
    await fetchProjects();
  }, [fetchProjects]);

  // Fetch on user change - with deduplication by userId
  useEffect(() => {
    const userId = user?.user_id;
    
    // Skip if same user and we already have projects
    if (userId === lastUserIdRef.current && projects.length > 0) {
      return;
    }
    
    lastUserIdRef.current = userId;
    
    if (userId) {
      // Load stored selection immediately (before fetch completes)
      if (storageKey) {
        try {
          const stored = localStorage.getItem(storageKey) || '';
          setSelectedProjectIdState(stored);
        } catch {}
      }
      fetchProjects();
    } else {
      setProjects([]);
      setSelectedProjectIdState('');
      setLoading(false);
    }
  }, [user?.user_id, storageKey, fetchProjects, projects.length]);

  // Compute selected project object - memoized
  const selectedProject = useMemo(() => 
    projects.find(p => p.project_id === selectedProjectId) || null,
    [projects, selectedProjectId]
  );

  // Memoize context value to prevent unnecessary re-renders of consumers
  const value = useMemo(() => ({
    projects,
    selectedProject,
    selectedProjectId,
    loading,
    error,
    setSelectedProjectId,
    refreshProjects,
  }), [projects, selectedProject, selectedProjectId, loading, error, setSelectedProjectId, refreshProjects]);

  return (
    <DataContext.Provider value={value}>
      {children}
    </DataContext.Provider>
  );
};

export default DataContext;
