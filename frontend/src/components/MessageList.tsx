import React from 'react';
import { ReasoningDisplay } from './ReasoningDisplay';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: string[];
  reasoning?: ToolCallEvent[];
}

interface ToolCallEvent {
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

interface MessageListProps {
  messages: Message[];
  streamingMessage?: string;
  isStreaming?: boolean;
  toolCalls?: ToolCallEvent[];
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  streamingMessage,
  isStreaming = false,
  toolCalls = [],
}) => {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage, isStreaming]);

  // Extract URLs from content for citations
  const extractCitations = (content: string): string[] => {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const matches = content.match(urlRegex);
    return matches || [];
  };

  return (
    <div className="h-full overflow-y-auto px-6 py-8 space-y-6">
      {messages.length === 0 && !streamingMessage && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">💬</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Welcome to Marketing Cortex</h3>
            <p className="text-gray-600">Ask me anything about marketing, advertising, or ad tech trends.</p>
            <p className="text-sm text-gray-500 mt-2">I can search marketing blogs, web content, and past research.</p>
          </div>
        </div>
      )}

      {messages.map((message) => {
        const citations = extractCitations(message.content);
        
        return (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-2xl px-5 py-4 shadow-sm ${
                message.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-900 border border-gray-200'
              }`}
            >
              {/* Reasoning Display - Only for assistant messages */}
              {message.role === 'assistant' && message.reasoning && message.reasoning.length > 0 && (
                <ReasoningDisplay reasoningSteps={message.reasoning} />
              )}
              
              <div className="whitespace-pre-wrap break-words leading-relaxed">{message.content}</div>
              
              {citations.length > 0 && message.role === 'assistant' && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-xs font-medium text-gray-500 mb-2">Sources:</p>
                  <div className="flex flex-wrap gap-2">
                    {citations.map((url, idx) => (
                      <a
                        key={idx}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
                      >
                        {new URL(url).hostname}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              
              <div
                className={`text-xs mt-3 ${
                  message.role === 'user' ? 'text-blue-100' : 'text-gray-400'
                }`}
              >
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        );
      })}

      {/* Tool Calls Display */}
      {toolCalls.length > 0 && isStreaming && (
        <div className="flex justify-start mb-4">
          <div className="max-w-3xl rounded-lg px-4 py-3 bg-blue-50 border border-blue-200">
            <div className="text-sm font-medium text-blue-900 mb-2">Agent Thinking:</div>
            <div className="space-y-2">
              {toolCalls.map((event, idx) => {
                if (event.type === 'tool_call_start') {
                  return (
                    <div key={idx} className="flex items-center gap-2 text-sm text-blue-700">
                      <span className="animate-spin">⏳</span>
                      <span>Searching {event.tool?.replace('_', ' ')}...</span>
                    </div>
                  );
                } else if (event.type === 'tool_call_result') {
                  return (
                    <div key={idx} className="flex items-center gap-2 text-sm text-green-700">
                      <span>✓</span>
                      <span>Found {event.results_count || 0} results from {event.tool?.replace('_', ' ')}</span>
                    </div>
                  );
                } else if (event.type === 'query_refinement') {
                  return (
                    <div key={idx} className="text-sm text-purple-700">
                      <span className="font-medium">Refining query:</span> "{event.original}" → "{event.refined}"
                    </div>
                  );
                } else if (event.type === 'synthesis_start') {
                  return (
                    <div key={idx} className="flex items-center gap-2 text-sm text-indigo-700">
                      <span className="animate-pulse">🧠</span>
                      <span>Synthesizing results from {event.sources?.length || 0} sources...</span>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          </div>
        </div>
      )}

      {streamingMessage && (
        <div className="flex justify-start">
          <div className="max-w-3xl rounded-2xl px-5 py-4 bg-white text-gray-900 border border-gray-200 shadow-sm">
            <div className="whitespace-pre-wrap break-words leading-relaxed">
              {streamingMessage}
              {isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 bg-blue-600 animate-pulse rounded" />
              )}
            </div>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
};
