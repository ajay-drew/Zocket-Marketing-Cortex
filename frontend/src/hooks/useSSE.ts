import { useState, useCallback, useRef, useEffect } from 'react';
import { streamAgentResponse, AgentRequest } from '../services/api';

export interface UseSSEReturn {
  message: string;
  isStreaming: boolean;
  error: string | null;
  sendMessage: (query: string, sessionId?: string) => void;
  clearMessage: () => void;
}

/**
 * Custom hook for Server-Sent Events (SSE) streaming
 */
export function useSSE(): UseSSEReturn {
  const [message, setMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback((query: string, sessionId?: string) => {
    // #region agent log
    fetch('http://127.0.0.1:7253/ingest/3ac3d9b9-6b30-42fe-81b9-6705712ab86a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useSSE.ts:21',message:'sendMessage called',data:{query:query.substring(0,50),sessionId:sessionId||'none'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Reset state
    setMessage('');
    setError(null);
    setIsStreaming(true);

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    const request: AgentRequest = {
      query,
      session_id: sessionId,
    };

    // #region agent log
    fetch('http://127.0.0.1:7253/ingest/3ac3d9b9-6b30-42fe-81b9-6705712ab86a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useSSE.ts:41',message:'calling streamAgentResponse',data:{requestQuery:request.query.substring(0,50),hasSessionId:!!request.session_id},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion

    // Stream response
    streamAgentResponse(
      request,
      (chunk: string) => {
        setMessage((prev) => prev + chunk);
      },
      () => {
        setIsStreaming(false);
        abortControllerRef.current = null;
      },
      (errorMessage: string) => {
        // #region agent log
        fetch('http://127.0.0.1:7253/ingest/3ac3d9b9-6b30-42fe-81b9-6705712ab86a',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'useSSE.ts:50',message:'onError callback triggered',data:{errorMessage:errorMessage.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
        // #endregion
        setError(errorMessage);
        setIsStreaming(false);
        abortControllerRef.current = null;
      },
      abortControllerRef.current.signal
    );
  }, []);

  const clearMessage = useCallback(() => {
    setMessage('');
    setError(null);
    setIsStreaming(false);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    message,
    isStreaming,
    error,
    sendMessage,
    clearMessage,
  };
}
