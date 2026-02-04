import React from 'react';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: string[];
}

interface MessageListProps {
  messages: Message[];
  streamingMessage?: string;
  isStreaming?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  streamingMessage,
  isStreaming = false,
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
    <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6">
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
