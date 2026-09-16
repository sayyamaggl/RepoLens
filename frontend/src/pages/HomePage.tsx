import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Loader2, GitBranch, ShieldAlert, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import { RepoInfo } from '../types';

export default function HomePage() {
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentRepos, setRecentRepos] = useState<RepoInfo[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    api.getRepos().then((data) => setRecentRepos(data.repos)).catch(console.error);
  }, []);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const result = await api.analyzeRepo(url);
      navigate(`/repo/${result.repo_id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'An error occurred during analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteRepo = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation(); // prevent navigation
    try {
      await api.deleteRepo(id);
      setRecentRepos(recentRepos.filter((repo) => repo.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete repository');
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 relative overflow-hidden">
      
      {/* Hero Section */}
      <div className="z-10 w-full max-w-3xl text-center mb-12">
        <h1 className="text-5xl md:text-7xl font-black mb-6 tracking-tight">
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-violet-500">
            RepoLens
          </span>
        </h1>
        <p className="text-xl md:text-2xl text-gray-400 font-light max-w-2xl mx-auto mb-10">
          Instantly comprehend any codebase. AI-powered structural analysis and grounded architecture summaries.
        </p>

        {/* Search Bar */}
        <form onSubmit={handleAnalyze} className="relative group max-w-xl mx-auto">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-cyan-500 to-violet-500 rounded-xl blur opacity-30 group-hover:opacity-60 transition duration-500"></div>
          <div className="relative flex items-center bg-dark-800 rounded-xl p-2 border border-white/10">
            <Search className="w-6 h-6 text-gray-500 ml-3" />
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste public GitHub URL..."
              className="w-full bg-transparent border-none px-4 py-3 text-white placeholder-gray-500 focus:outline-none"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !url}
              className="btn-primary flex items-center whitespace-nowrap"
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <GitBranch className="w-5 h-5 mr-2" />}
              {isLoading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
          {error && (
            <div className="absolute top-full mt-4 w-full flex items-center p-3 rounded-lg bg-red-900/30 text-red-400 border border-red-500/30">
              <ShieldAlert className="w-5 h-5 mr-2 flex-shrink-0" />
              <p className="text-sm text-left">{error}</p>
            </div>
          )}
        </form>
      </div>

      {/* Recent Repos */}
      {recentRepos.length > 0 && (
        <div className="z-10 w-full max-w-5xl mt-12">
          <h3 className="text-lg font-medium text-gray-400 mb-6 flex items-center">
            <span className="h-px bg-gray-800 flex-1 mr-4"></span>
            Recently Analyzed
            <span className="h-px bg-gray-800 flex-1 ml-4"></span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recentRepos.map((repo) => (
              <div 
                key={repo.id}
                onClick={() => navigate(`/repo/${repo.id}`)}
                className="glass-card p-6 cursor-pointer group"
              >
                <div className="flex justify-between items-start mb-2">
                  <h4 className="text-xl font-bold group-hover:text-cyan-400 transition-colors truncate pr-4">
                    {repo.name || repo.url.split('/').pop()}
                  </h4>
                  <button 
                    onClick={(e) => handleDeleteRepo(e, repo.id)}
                    className="text-gray-500 hover:text-red-400 p-1 rounded-md hover:bg-red-500/10 transition-colors"
                    title="Delete Repository"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex items-center space-x-3 text-sm text-gray-400 mb-4">
                  {repo.primary_language && (
                    <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10">
                      {repo.primary_language}
                    </span>
                  )}
                  {repo.framework && (
                    <span className="px-2 py-1 rounded-md bg-white/5 border border-white/10">
                      {repo.framework}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>Status: <span className={`capitalize ${repo.status === 'done' ? 'text-emerald-400' : 'text-amber-400'}`}>{repo.status}</span></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}