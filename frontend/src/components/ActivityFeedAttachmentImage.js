import { useEffect, useRef, useState } from 'react';
import { cn } from '../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Revoke on the next macrotask so React Strict Mode / layout are not racing the
 * <img> decode step with synchronous revokeObjectURL in effect cleanup.
 */
const revokeObjectUrlDeferred = (url) => {
  if (!url) return;
  setTimeout(() => {
    try {
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  }, 0);
};

/**
 * Authenticated fetch of GET /api/activities/{id}/attachment → blob URL for <img>.
 * Owns the full blob lifecycle so feed cards do not duplicate hooks or revoke races.
 */
export function ActivityFeedAttachmentImage({
  activityId,
  enabled,
  fileName,
  containerClassName,
  skeletonClassName,
  imgClassName,
  linkClassName,
  dataTestId,
  onStateChange,
}) {
  const [phase, setPhase] = useState(() => (enabled ? 'loading' : 'idle'));
  const [objectUrl, setObjectUrl] = useState(null);
  const [decodeFailed, setDecodeFailed] = useState(false);
  const genRef = useRef(0);
  const onStateChangeRef = useRef(onStateChange);
  onStateChangeRef.current = onStateChange;

  const emit = (next) => {
    onStateChangeRef.current?.(next);
  };

  useEffect(() => {
    emit({
      phase,
      decodeFailed,
      showInline: phase === 'ready' && !decodeFailed,
    });
  }, [phase, decodeFailed]);

  useEffect(() => {
    if (!enabled || !activityId) {
      setPhase('idle');
      setObjectUrl(null);
      setDecodeFailed(false);
      emit({ phase: 'idle', decodeFailed: false, showInline: false });
      return;
    }

    const gen = ++genRef.current;
    setPhase('loading');
    setObjectUrl(null);
    setDecodeFailed(false);
    emit({ phase: 'loading', decodeFailed: false, showInline: false });

    const ac = new AbortController();
    const url = `${API}/activities/${activityId}/attachment`;
    let createdUrl = null;

    (async () => {
      try {
        const res = await fetch(url, {
          credentials: 'include',
          headers: getAuthHeaders(),
          signal: ac.signal,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (gen !== genRef.current) return;
        const ou = URL.createObjectURL(blob);
        if (gen !== genRef.current) {
          revokeObjectUrlDeferred(ou);
          return;
        }
        createdUrl = ou;
        setObjectUrl(ou);
        setPhase('ready');
      } catch (e) {
        if (e?.name === 'AbortError') return;
        if (gen !== genRef.current) return;
        setPhase('error');
      }
    })();

    return () => {
      ac.abort();
      revokeObjectUrlDeferred(createdUrl);
      setObjectUrl(null);
    };
  }, [activityId, enabled]);

  useEffect(() => {
    setDecodeFailed(false);
  }, [objectUrl, activityId]);

  if (!enabled || !activityId) {
    return null;
  }

  const showSkeleton = phase === 'loading';
  const showImg = phase === 'ready' && objectUrl && !decodeFailed;

  return (
    <>
      {showSkeleton && (
        <div className={cn(containerClassName)} aria-busy="true">
          <div
            className={cn(
              'w-full min-h-[180px] max-h-96 animate-pulse bg-muted/80',
              skeletonClassName
            )}
          />
        </div>
      )}
      {showImg && (
        <div className={containerClassName}>
          <a
            href={objectUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn('block', linkClassName)}
            data-testid={dataTestId}
          >
            <img
              key={objectUrl}
              src={objectUrl}
              alt={fileName || 'Image attachment'}
              className={imgClassName}
              onLoad={() => setDecodeFailed(false)}
              onError={() => setDecodeFailed(true)}
            />
          </a>
        </div>
      )}
    </>
  );
}
