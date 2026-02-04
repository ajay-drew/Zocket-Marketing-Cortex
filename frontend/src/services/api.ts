/**
 * API client for Marketing Cortex backend
 */

// Use relative URL to leverage Vite proxy, or full URL if VITE_API_URL is set
// Trim whitespace to prevent malformed URLs
const API_BASE_URL = (import.meta.env.VITE_API_URL || '').trim();

// Blog ingestion types
export interface BlogSource {
  name: string;
  url: string;
  total_posts: number;
  last_updated: string | null;
}

export type { BlogSource };

export interface BlogSourcesResponse {
  sources: BlogSource[];
}

export interface BlogIngestResponse {
  status: string;
  blog_name: string;
  posts_ingested: number;
  chunks_created: number;
  errors: number;
  total_entries?: number;
  message?: string;
}

export interface AgentRequest {
  query: string;
  session_id?: string;
  metadata?: Record<string, any>;
}

export interface SSEEvent {
  type: 'start' | 'token' | 'done' | 'error' | 'tool_call_start' | 'tool_call_result' | 'query_refinement' | 'synthesis_start' | 'query_analysis';
  content?: string;
  session_id?: string;
  error?: string;
  tool?: string;
  query?: string;
  original?: string;
  refined?: string;
  sources?: string[];
  [key: string]: any; // Allow additional properties
}

/**
 * Create EventSource for SSE streaming
 */
export function createSSEConnection(): EventSource {
  // For POST requests with SSE, we need to use fetch with ReadableStream
  // But EventSource only supports GET, so we'll use fetch API instead
  // This will be handled in the useSSE hook
  
  // For now, return a placeholder (this won't be used)
  return new EventSource('');
}

/**
 * Fetch API wrapper for SSE streaming
 */
export async function streamAgentResponse(
  request: AgentRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
  signal?: AbortSignal
): Promise<void> {
  try {
    // Use proxy if API_BASE_URL is empty, otherwise use full URL
    // Ensure proper URL construction: remove trailing slash from base, add leading slash to path
    let url: string;
    if (API_BASE_URL) {
      const base = API_BASE_URL.replace(/\/$/, ''); // Remove trailing slash
      url = `${base}/api/agent/stream`;
    } else {
      url = '/api/agent/stream';
    }
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',  // Explicitly request SSE
      },
      body: JSON.stringify(request),
      signal,
    });
    
    if (!response.ok) {
      const errorText = await response.text().catch(() => 'No error details');
      console.error(`HTTP error! status: ${response.status}`, errorText);
      
      // Provide helpful error messages
      if (response.status === 404) {
        const helpfulMessage = `Endpoint not found (404). The backend route /api/agent/stream may not be registered. ` +
          `Please ensure the backend server is running and has been restarted after recent changes. ` +
          `Try visiting the API docs to verify the API is accessible.`;
        throw new Error(helpfulMessage);
      }
      
      throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        onComplete();
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            // Handle different event types
            if (data.type === 'token' && data.content) {
              onChunk(data.content);
            } else if (data.type === 'error') {
              onError(data.error || data.content || 'Unknown error');
              return;
            } else if (data.type === 'done') {
              onComplete();
              return;
            } else if (data.type === 'tool_call_start' || data.type === 'tool_call_result' || 
                       data.type === 'query_refinement' || data.type === 'synthesis_start' ||
                       data.type === 'query_analysis' || data.type === 'evaluation') {
              // Tool call events - pass through to onChunk with special marker
              // Format: [EVENT:type] JSON data
              onChunk(`[EVENT:${data.type}]${JSON.stringify(data)}`);
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        }
      }
    }
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Unknown error');
  }
}

/**
 * Get list of blog sources
 */
export async function getBlogSources(): Promise<BlogSourcesResponse> {
  let url: string;
  if (API_BASE_URL) {
    const base = API_BASE_URL.replace(/\/$/, '');
    url = `${base}/api/blogs/sources`;
  } else {
    url = '/api/blogs/sources';
  }

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to get blog sources: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Ingest blog content from RSS feed
 */
export async function ingestBlog(
  blogUrl: string,
  blogName: string,
  maxPosts: number = 50
): Promise<BlogIngestResponse> {
  let url: string;
  if (API_BASE_URL) {
    const base = API_BASE_URL.replace(/\/$/, '');
    url = `${base}/api/blogs/ingest`;
  } else {
    url = '/api/blogs/ingest';
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      blog_url: blogUrl,
      blog_name: blogName,
      max_posts: maxPosts,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`Failed to ingest blog: ${errorText}`);
  }

  return response.json();
}

/**
 * Stream blog ingestion progress via SSE
 */
export async function ingestBlogStream(
  blogUrl: string,
  blogName: string,
  maxPosts: number,
  onProgress: (data: any) => void,
  onComplete: (result: BlogIngestResponse) => void,
  onError: (error: string) => void,
  signal?: AbortSignal
): Promise<void> {
  let url: string;
  if (API_BASE_URL) {
    const base = API_BASE_URL.replace(/\/$/, '');
    url = `${base}/api/blogs/ingest/stream`;
  } else {
    url = '/api/blogs/ingest/stream';
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify({
        blog_url: blogUrl,
        blog_name: blogName,
        max_posts: maxPosts,
      }),
      signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'progress') {
              onProgress(data);
            } else if (data.type === 'complete') {
              onComplete(data.result);
              return;
            } else if (data.type === 'error') {
              onError(data.error || 'Unknown error');
              return;
            } else if (data.type === 'start') {
              onProgress({ stage: 'start', message: data.message, progress: 0 });
            }
          } catch (e) {
            console.error('Error parsing SSE data:', e);
          }
        }
      }
    }
  } catch (error) {
    onError(error instanceof Error ? error.message : 'Unknown error');
  }
}

/**
 * Refresh blog content
 */
export async function refreshBlog(blogName?: string): Promise<any> {
  let url: string;
  if (API_BASE_URL) {
    const base = API_BASE_URL.replace(/\/$/, '');
    url = `${base}/api/blogs/refresh`;
  } else {
    url = '/api/blogs/refresh';
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      blog_name: blogName || null,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`Failed to refresh blog: ${errorText}`);
  }

  return response.json();
}
