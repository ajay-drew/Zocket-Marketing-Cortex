import { useState, useCallback, useRef, useEffect } from 'react';
import { streamAgentResponse, AgentRequest } from '../services/api';

export interface ToolCallEvent {
  type: 'tool_call_start' | 'tool_call_result' | 'query_refinement' | 'synthesis_start' | 'query_analysis' | 'evaluation';
  tool?: string;
  query?: string;
  original?: string;
  refined?: string;
  sources?: string[];
  reasoning?: string;
  analysis?: any;
  strategy?: string;
  quality_score?: number;
  results_count?: number;
  overall_quality?: number;
  result_count?: number;
  next_action?: string;
  [key: string]: any;
}

export interface UseSSEReturn {
  message: string;
  isStreaming: boolean;
  error: string | null;
  toolCalls: ToolCallEvent[];
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
  const [toolCalls, setToolCalls] = useState<ToolCallEvent[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback((query: string, sessionId?: string) => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Reset state
    setMessage('');
    setError(null);
    setToolCalls([]);
    setIsStreaming(true);

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    const request: AgentRequest = {
      query,
      session_id: sessionId,
    };

    // Stream response
    streamAgentResponse(
      request,
      (chunk: string) => {
        // Check if this is a tool call event
        if (chunk.startsWith('[EVENT:')) {
          const eventMatch = chunk.match(/^\[EVENT:([^\]]+)\](.+)$/);
          if (eventMatch) {
            const eventType = eventMatch[1];
            try {
              const eventData = JSON.parse(eventMatch[2]);
              setToolCalls((prev) => [...prev, { type: eventType as any, ...eventData }]);
            } catch (e) {
              console.error('Error parsing tool call event:', e);
            }
          }
        } else {
          setMessage((prev) => prev + chunk);
        }
      },
      () => {
        setIsStreaming(false);
        abortControllerRef.current = null;
      },
      (errorMessage: string) => {
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
    setToolCalls([]);
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
    toolCalls,
    sendMessage,
    clearMessage,
  };
}
