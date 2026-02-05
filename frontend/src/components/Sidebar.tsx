import React from 'react';

export type SidebarItem = {
  id: string;
  label: string;
  icon?: string;
};

interface SidebarProps {
  activeItem: string;
  onItemClick: (itemId: string) => void;
  items: SidebarItem[];
}

export const Sidebar: React.FC<SidebarProps> = ({ activeItem, onItemClick, items }) => {
  return (
    <div data-testid="sidebar" className="w-60 bg-gray-800 text-white flex flex-col h-screen fixed left-0 top-0">
      {/* Logo/Brand */}
      <div className="p-6 border-b border-gray-700">
        <h1 className="text-xl font-bold">Marketing Cortex</h1>
        <p className="text-xs text-gray-400 mt-1">AI Research Platform</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => onItemClick(item.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                  activeItem === item.id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`}
              >
                {item.icon && <span className="text-lg">{item.icon}</span>}
                <span className="font-medium">{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700">
        <p className="text-xs text-gray-400 text-center">
          Created by Ajay A, +91-7530054065
        </p>
      </div>
    </div>
  );
};
