import React, { useState, useEffect } from 'react';

export interface HistoryItem {
  id: string;
  query: string;
  response: string;
  timestamp: Date;
}

interface ResearchHistoryProps {
  onSelectHistory?: (item: HistoryItem) => void;
}

export const ResearchHistory: React.FC<ResearchHistoryProps> = ({
  onSelectHistory,
}) => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    // Load history from localStorage
    const stored = localStorage.getItem('research_history');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setHistory(
          parsed.map((item: any) => ({
            ...item,
            timestamp: new Date(item.timestamp),
          }))
        );
      } catch (e) {
        console.error('Error loading history:', e);
      }
    }
  }, []);

  const clearHistory = () => {
    localStorage.removeItem('research_history');
    setHistory([]);
  };

  return (
    <div className={`relative bg-white border-r border-gray-200 ${isOpen ? 'w-80' : 'w-0'} transition-all duration-300 overflow-hidden`}>
      {isOpen && (
        <div className="h-full flex flex-col">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Research History</h2>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-500 hover:text-gray-700"
              aria-label="Close history"
            >
              ✕
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {history.length === 0 ? (
              <p className="text-gray-500 text-sm">No research history yet.</p>
            ) : (
              <div className="space-y-2">
                {history.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => onSelectHistory?.(item)}
                    className="p-3 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {item.query}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {item.timestamp.toLocaleDateString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
          {history.length > 0 && (
            <div className="p-4 border-t border-gray-200">
              <button
                onClick={clearHistory}
                className="w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                Clear History
              </button>
            </div>
          )}
        </div>
      )}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="absolute left-0 top-1/2 transform -translate-y-1/2 bg-blue-600 text-white px-2 py-4 rounded-r-lg hover:bg-blue-700 transition-colors z-10"
          aria-label="Open history"
        >
          →
        </button>
      )}
    </div>
  );
};
