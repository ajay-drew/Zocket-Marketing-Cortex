import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getBlogSources, BlogSource } from '../services/api';

interface BlogDataContextType {
  sources: BlogSource[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  invalidateCache: () => void;
  lastFetched: number | null;
}

const BlogDataContext = createContext<BlogDataContextType | undefined>(undefined);

const CACHE_KEY = 'blog_sources_cache';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface CacheEntry {
  data: BlogSource[];
  timestamp: number;
}

export const BlogDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sources, setSources] = useState<BlogSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastFetched, setLastFetched] = useState<number | null>(null);

  const loadFromCache = useCallback((): BlogSource[] | null => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const entry: CacheEntry = JSON.parse(cached);
        const now = Date.now();
        
        // Check if cache is still valid
        if (now - entry.timestamp < CACHE_TTL) {
          return entry.data;
        }
      }
    } catch (e) {
      console.warn('Failed to load from cache:', e);
    }
    return null;
  }, []);

  const saveToCache = useCallback((data: BlogSource[]) => {
    try {
      const entry: CacheEntry = {
        data,
        timestamp: Date.now(),
      };
      localStorage.setItem(CACHE_KEY, JSON.stringify(entry));
    } catch (e) {
      console.warn('Failed to save to cache:', e);
    }
  }, []);

  const fetchBlogSources = useCallback(async (forceRefresh = false) => {
    // Check cache first if not forcing refresh
    if (!forceRefresh) {
      const cached = loadFromCache();
      if (cached) {
        setSources(cached);
        setLoading(false);
        setError(null);
        // Try to refresh in background
        fetchBlogSources(true).catch(() => {
          // Silent fail for background refresh
        });
        return;
      }
    }

    try {
      setLoading(true);
      setError(null);
      const response = await getBlogSources();
      const sourcesData = response.sources || [];
      
      setSources(sourcesData);
      setLastFetched(Date.now());
      saveToCache(sourcesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load blog sources');
      // Try to use cached data if available
      const cached = loadFromCache();
      if (cached) {
        setSources(cached);
      }
    } finally {
      setLoading(false);
    }
  }, [loadFromCache, saveToCache]);

  const invalidateCache = useCallback(() => {
    try {
      localStorage.removeItem(CACHE_KEY);
    } catch (e) {
      console.warn('Failed to invalidate cache:', e);
    }
    // Force refresh
    fetchBlogSources(true);
  }, [fetchBlogSources]);

  // Initial load
  useEffect(() => {
    fetchBlogSources(false);
  }, [fetchBlogSources]);

  const value: BlogDataContextType = {
    sources,
    loading,
    error,
    refresh: () => fetchBlogSources(true),
    invalidateCache,
    lastFetched,
  };

  return (
    <BlogDataContext.Provider value={value}>
      {children}
    </BlogDataContext.Provider>
  );
};

export const useBlogData = (): BlogDataContextType => {
  const context = useContext(BlogDataContext);
  if (context === undefined) {
    throw new Error('useBlogData must be used within a BlogDataProvider');
  }
  return context;
};
