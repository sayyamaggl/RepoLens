import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Layout, GitCommit, Files, AlertTriangle } from 'lucide-react';
import { api } from '../api/client';
import { RepoInfo, OverviewResponse } from '../types';
import AnalysisProgress from '../components/AnalysisProgress';
import ArchitectureOverview from '../components/ArchitectureOverview';
import DependencyGraph from '../components/DependencyGraph';
import FilesExplorer from '../components/FilesExplorer';
import ReactMarkdown from 'react-markdown';

export default function RepoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const repoId = parseInt(id || '0');

  const [status, setStatus] = useState<RepoInfo | null>(null);
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'graph' | 'files'>('overview');
  const [error, setError] = useState<string | null>(null);

  // Poll for status if not done
  useEffect(() => {
    if (!repoId) return;

    let intervalId: number;
    let isMounted = true;

    const checkStatus = async () => {
      if (!isMounted) return;
      try {
        const data = await api.getRepoStatus(repoId);
        if (!isMounted) return;
        setStatus(data);

        if (data.status === 'done') {
          fetchOverview();
        } else if (data.status === 'error') {
          setError(data.error_message || 'Analysis failed');
        } else {
          // Still processing, poll again
          intervalId = window.setTimeout(checkStatus, 3000);
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || 'Failed to fetch status');
      }
    };

    checkStatus();

    return () => {
      isMounted = false;
      clearTimeout(intervalId);
    };
  }, [repoId]);

  const handleReanalyze = async () => {
    if (!status?.url) return;
    try {
      await api.analyzeRepo(status.url);
      setOverview(null);
      window.location.reload();
    } catch (err: any) {
      setError(err.message || 'Failed to trigger re-analysis');
    }
  };

  const fetchOverview = async () => {
    try {
      const data = await api.getRepoOverview(repoId);
      setOverview(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch overview');
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="glass-card p-8 max-w-lg w-full border-red-500/30 text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-red-400 mb-2">Analysis Failed</h2>
          <p className="text-gray-400 mb-6">{error}</p>
          <div className="flex gap-4 justify-center">
            <button onClick={() => navigate('/')} className="btn-secondary">Back to Home</button>
            <button onClick={handleReanalyze} className="btn-primary">Retry Analysis</button>
          </div>
        </div>
      </div>
    );
  }

  if (!status || status.status !== 'done') {
    return <AnalysisProgress status={status?.status || 'pending'} repoName={status?.name || 'Repository'} />;
  }

  return (
    <div className="min-h-screen flex flex-col h-screen overflow-hidden bg-dark-900">
      {/* Header */}
      <header className="h-16 border-b border-white/10 bg-dark-800/80 backdrop-blur-md flex items-center px-6 flex-shrink-0 z-20">
        <button onClick={() => navigate('/')} className="p-2 hover:bg-white/5 rounded-full mr-4 transition-colors">
          <ArrowLeft className="w-5 h-5 text-gray-400 hover:text-white" />
        </button>
        
        <div className="flex-1">
          <h1 className="text-xl font-bold flex items-center">
            {status.name}
            {status.primary_language && (
              <span className="ml-4 px-2 py-0.5 text-xs rounded-full bg-cyan-900/30 text-cyan-400 border border-cyan-500/30">
                {status.primary_language}
              </span>
            )}
            {status.framework && (
              <span className="ml-2 px-2 py-0.5 text-xs rounded-full bg-violet-900/30 text-violet-400 border border-violet-500/30">
                {status.framework}
              </span>
            )}
          </h1>
        </div>

        {/* Tabs */}
        <div className="flex bg-dark-900 rounded-lg p-1 border border-white/5 mr-4">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === 'overview' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Layout className="w-4 h-4 mr-2" /> Overview
          </button>
          <button
            onClick={() => setActiveTab('graph')}
            className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === 'graph' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <GitCommit className="w-4 h-4 mr-2" /> Dependency Graph
          </button>
          <button
            onClick={() => setActiveTab('files')}
            className={`flex items-center px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
              activeTab === 'files' ? 'bg-white/10 text-white shadow-sm' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <Files className="w-4 h-4 mr-2" /> Files
          </button>
        </div>

        <button
          onClick={handleReanalyze}
          className="flex items-center px-4 py-1.5 rounded-md text-sm font-medium bg-dark-700 hover:bg-dark-600 text-gray-300 transition-colors border border-white/10"
          title="Re-analyze Repository"
        >
          <RefreshCw className="w-4 h-4 mr-2" /> Re-analyze
        </button>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 relative overflow-hidden">
        {activeTab === 'overview' && overview && (
          <div className="h-full overflow-y-auto p-6 md:p-10">
            <div className="max-w-5xl mx-auto">
              <ArchitectureOverview overview={overview} />
            </div>
          </div>
        )}

        {activeTab === 'graph' && (
          <div className="h-full w-full relative">
            <DependencyGraph repoId={repoId} />
          </div>
        )}
        
        {activeTab === 'files' && (
          <div className="h-full w-full p-6">
            <FilesExplorer repoId={repoId} />
          </div>
        )}
      </main>
    </div>
  );
}