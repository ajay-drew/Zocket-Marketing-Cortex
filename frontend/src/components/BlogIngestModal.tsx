import React, { useState, useRef } from 'react';
import { ingestBlogStream } from '../services/api';

interface BlogIngestModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export const BlogIngestModal: React.FC<BlogIngestModalProps> = ({ onClose, onSuccess }) => {
  const [blogName, setBlogName] = useState('');
  const [blogUrl, setBlogUrl] = useState('');
  const [maxPosts, setMaxPosts] = useState(50);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>('');
  const [progressPercent, setProgressPercent] = useState(0);
  const [currentPost, setCurrentPost] = useState<{ current?: number; total?: number }>({});
  const abortControllerRef = useRef<AbortController | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!blogName.trim() || !blogUrl.trim()) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setProgress('Starting ingestion...');
      setProgressPercent(0);
      setCurrentPost({});

      // Cancel any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new abort controller
      abortControllerRef.current = new AbortController();

      await ingestBlogStream(
        blogUrl,
        blogName,
        maxPosts,
        (progressData) => {
          // Update progress
          if (progressData.progress !== undefined) {
            setProgressPercent(progressData.progress);
          }
          if (progressData.message) {
            setProgress(progressData.message);
          }
          if (progressData.current !== undefined && progressData.total !== undefined) {
            setCurrentPost({ current: progressData.current, total: progressData.total });
          }
        },
        (result) => {
          setProgress(`✓ Ingestion complete! ${result.posts_ingested} posts, ${result.chunks_created} chunks`);
          setProgressPercent(100);
          setTimeout(() => {
            onSuccess();
          }, 1500);
        },
        (errorMessage) => {
          setError(errorMessage);
          setProgress('');
        },
        abortControllerRef.current.signal
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to ingest blog');
      setProgress('');
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="p-6 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Add New Blog</h3>
          <p className="text-sm text-gray-500 mt-1">Ingest content from an RSS feed</p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Progress Section */}
          {loading && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-blue-900">{progress || 'Processing...'}</span>
                <span className="text-blue-700">{progressPercent}%</span>
              </div>
              
              {/* Progress Bar */}
              <div className="w-full h-2 bg-blue-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-600 transition-all duration-300 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              {/* Current Post Info */}
              {currentPost.current && currentPost.total && (
                <div className="text-xs text-blue-700">
                  Post {currentPost.current} of {currentPost.total}
                </div>
              )}
            </div>
          )}

          {!loading && progress && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-3">
              <p className="text-sm text-green-800">{progress}</p>
            </div>
          )}

          <div>
            <label htmlFor="blogName" className="block text-sm font-medium text-gray-700 mb-1">
              Blog Name *
            </label>
            <input
              id="blogName"
              type="text"
              value={blogName}
              onChange={(e) => setBlogName(e.target.value)}
              placeholder="e.g., HubSpot Marketing"
              required
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>

          <div>
            <label htmlFor="blogUrl" className="block text-sm font-medium text-gray-700 mb-1">
              RSS Feed URL *
            </label>
            <input
              id="blogUrl"
              type="url"
              value={blogUrl}
              onChange={(e) => setBlogUrl(e.target.value)}
              placeholder="https://blog.example.com/rss.xml"
              required
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
          </div>

          <div>
            <label htmlFor="maxPosts" className="block text-sm font-medium text-gray-700 mb-1">
              Max Posts
            </label>
            <input
              id="maxPosts"
              type="number"
              value={maxPosts}
              onChange={(e) => setMaxPosts(parseInt(e.target.value) || 50)}
              min={1}
              max={200}
              disabled={loading}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            <p className="text-xs text-gray-500 mt-1">Maximum number of posts to ingest (default: 50)</p>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {loading ? 'Ingesting...' : 'Ingest Blog'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
