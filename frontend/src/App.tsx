import React, { useState, useEffect } from 'react';
import { Sidebar, SidebarItem } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './components/Dashboard';
import { BlogManager } from './components/BlogManager';
import { ChatInterface } from './components/ChatInterface';
import { BlogDataProvider } from './contexts/BlogDataContext';

type View = 'dashboard' | 'blogs' | 'chat';

function App() {
  const [activeView, setActiveView] = useState<View>('dashboard');
  const [sidebarItems] = useState<SidebarItem[]>([
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'blogs', label: 'Blog Manager', icon: '📚' },
    { id: 'chat', label: 'Research Chat', icon: '💬' },
  ]);

  // Handle hash routing
  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash === 'dashboard' || hash === 'blogs' || hash === 'chat') {
      setActiveView(hash);
    }
  }, []);

  useEffect(() => {
    window.location.hash = activeView;
  }, [activeView]);

  const handleSidebarClick = (itemId: string) => {
    if (itemId === 'dashboard' || itemId === 'blogs' || itemId === 'chat') {
      setActiveView(itemId);
    }
  };

  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <Dashboard />;
      case 'blogs':
        return <BlogManager />;
      case 'chat':
        return <ChatInterface />;
      default:
        return <Dashboard />;
    }
  };

  const getHeaderInfo = () => {
    switch (activeView) {
      case 'dashboard':
        return { title: 'Dashboard', subtitle: 'Overview of your blog ingestion system' };
      case 'blogs':
        return { title: 'Blog Manager', subtitle: 'Manage your blog sources and ingestion' };
      case 'chat':
        return { title: 'Research Chat', subtitle: 'Ask questions about marketing and ad tech' };
      default:
        return { title: 'Marketing Cortex', subtitle: '' };
    }
  };

  const headerInfo = getHeaderInfo();

  return (
    <BlogDataProvider>
      <div className="h-screen flex bg-gray-50 overflow-hidden">
        <Sidebar
          activeItem={activeView}
          onItemClick={handleSidebarClick}
          items={sidebarItems}
        />
        <div className="flex-1 flex flex-col ml-60 min-w-0">
          <Header title={headerInfo.title} subtitle={headerInfo.subtitle} />
          <div className="flex-1 overflow-hidden min-h-0">
            {renderContent()}
          </div>
        </div>
      </div>
    </BlogDataProvider>
  );
}

export default App;
