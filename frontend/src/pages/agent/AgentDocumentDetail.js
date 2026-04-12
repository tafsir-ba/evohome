import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { AgentQuoteDetail } from './AgentQuoteDetail';
import { AgentInvoiceDetail } from './AgentInvoiceDetail';
import { AgentLayout } from '../../components/AgentLayout';
import { Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentDocumentDetail = () => {
  const { documentId } = useParams();
  const [docType, setDocType] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchType = async () => {
      try {
        const res = await fetch(`${API}/documents/${documentId}`, { credentials: 'include', headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          setDocType(data.type);
        }
      } catch {} finally {
        setLoading(false);
      }
    };
    fetchType();
  }, [documentId]);

  if (loading) {
    return <AgentLayout><div className="flex items-center justify-center min-h-[400px]"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div></AgentLayout>;
  }

  // Delegate to the appropriate detail component
  // They read from useParams() which still works with the documentId param
  if (docType === 'invoice') return <AgentInvoiceDetail />;
  return <AgentQuoteDetail />;
};
