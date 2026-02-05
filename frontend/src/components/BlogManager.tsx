import React, { useState } from 'react';
import { ingestBlog, refreshBlog } from '../services/api';
import { BlogIngestModal } from './BlogIngestModal';
import { useBlogData } from '../contexts/BlogDataContext';

export const BlogManager: React.FC = () => {
  const { sources, loading, error, refresh, invalidateCache, lastFetched } = useBlogData();
  const [ingesting, setIngesting] = useState<Set<string>>(new Set());
  const [showModal, setShowModal] = useState(false);

  const handleIngest = async (blogName: string, blogUrl: string, maxPosts: number = 50) => {
    try {
      setIngesting(prev => new Set(prev).add(blogName));
      await ingestBlog(blogUrl, blogName, maxPosts);
      invalidateCache(); // Invalidate cache and refresh
    } catch (err) {
      alert(`Failed to ingest blog: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIngesting(prev => {
        const next = new Set(prev);
        next.delete(blogName);
        return next;
      });
    }
  };

  const handleRefresh = async (blogName: string) => {
    try {
      setIngesting(prev => new Set(prev).add(blogName));
      await refreshBlog(blogName);
      invalidateCache(); // Invalidate cache and refresh
    } catch (err) {
      alert(`Failed to refresh blog: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIngesting(prev => {
        const next = new Set(prev);
        next.delete(blogName);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Blog Manager</h2>
          <p className="text-gray-600 mt-1">
            Manage your blog sources and ingestion
            {lastFetched && (
              <span className="text-xs text-gray-400 ml-2">
                • Last updated: {new Date(lastFetched).toLocaleTimeString()}
              </span>
            )}
            <span className="text-xs text-gray-400 ml-2">
              • Auto-refreshes every 30s
            </span>
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => refresh()}
            disabled={loading}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            title="Manually refresh blog sources (e.g., after batch ingestion)"
          >
            {loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            + Add Blog
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Error: {error}</p>
          <button
            onClick={() => refresh()}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Retry
          </button>
        </div>
      )}

      <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Blog Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                RSS Feed
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Posts
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Last Updated
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sources.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                  No blog sources configured. Click "Add Blog" to get started.
                </td>
              </tr>
            ) : (
              sources.map((source) => (
                <tr key={source.name} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{source.name}</div>
                  </td>
                  <td className="px-6 py-4">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-800 truncate block max-w-md"
                    >
                      {source.url}
                    </a>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm text-gray-900">{source.total_posts}</span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm text-gray-500">
                      {source.last_updated
                        ? new Date(source.last_updated).toLocaleDateString()
                        : 'Never'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleIngest(source.name, source.url)}
                        disabled={ingesting.has(source.name)}
                        className="text-blue-600 hover:text-blue-900 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {ingesting.has(source.name) ? 'Ingesting...' : 'Ingest'}
                      </button>
                      <span className="text-gray-300">|</span>
                      <button
                        onClick={() => handleRefresh(source.name)}
                        disabled={ingesting.has(source.name)}
                        className="text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {ingesting.has(source.name) ? 'Refreshing...' : 'Refresh'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <BlogIngestModal
          onClose={() => setShowModal(false)}
          onSuccess={() => {
            setShowModal(false);
            invalidateCache(); // Invalidate cache and refresh
          }}
        />
      )}
    </div>
  );
};
