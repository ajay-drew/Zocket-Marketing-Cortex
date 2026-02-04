import React, { useState, useCallback } from 'react';
import { MessageList, Message } from './MessageList';
import { InputBox } from './InputBox';
import { useSSE } from '../hooks/useSSE';

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId] = useState<string>(() => {
    // Generate or retrieve session ID from localStorage
    const stored = localStorage.getItem('session_id');
    if (stored) return stored;
    const newId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('session_id', newId);
    return newId;
  });

  const { message: streamingMessage, isStreaming, error, toolCalls, sendMessage, clearMessage } = useSSE();

  const handleSend = useCallback(
    (query: string) => {
      // Add user message to list
      const userMessage: Message = {
        id: `msg_${Date.now()}_user`,
        role: 'user',
        content: query,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // Send to agent
      sendMessage(query, sessionId);
    },
    [sendMessage, sessionId]
  );

  // When streaming completes, add assistant message to list and save to history
  React.useEffect(() => {
    if (!isStreaming && streamingMessage) {
      const lastUserMessage = [...messages].reverse().find((msg) => msg.role === 'user');
      const assistantMessage: Message = {
        id: `msg_${Date.now()}_assistant`,
        role: 'assistant',
        content: streamingMessage,
        timestamp: new Date(),
        reasoning: toolCalls.length > 0 ? toolCalls : undefined, // Store reasoning steps
        query: lastUserMessage?.content, // Store query for feedback
        sessionId: sessionId, // Store session ID for feedback
      };
      setMessages((prev) => {
        const updated = [...prev, assistantMessage];
        
        // Save to research history (find the last user message)
        if (lastUserMessage) {
          try {
            const historyItem = {
              id: `history_${Date.now()}`,
              query: lastUserMessage.content,
              response: streamingMessage,
              timestamp: new Date(),
            };
            
            // Load existing history
            const stored = localStorage.getItem('research_history');
            const existing = stored ? JSON.parse(stored) : [];
            
            // Add new item and keep last 50
            const updatedHistory = [historyItem, ...existing].slice(0, 50);
            localStorage.setItem('research_history', JSON.stringify(updatedHistory));
          } catch (e) {
            console.error('Error saving to history:', e);
          }
        }
        
        return updated;
      });
      clearMessage();
    }
  }, [isStreaming, streamingMessage, clearMessage, messages, sessionId, toolCalls]);

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-6 py-4 mx-6 mt-4 rounded-lg flex-shrink-0">
          <p className="font-semibold">Error</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      {/* Messages - Scrollable area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <MessageList
          messages={messages}
          streamingMessage={streamingMessage}
          isStreaming={isStreaming}
          toolCalls={toolCalls}
          sessionId={sessionId}
        />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 bg-white flex-shrink-0">
        <InputBox onSend={handleSend} disabled={isStreaming} />
      </div>
    </div>
  );
};
