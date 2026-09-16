import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { FileInfo, FileSummaryResponse } from '../types';
import { Loader2, FileCode, Search, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Props {
  repoId: number;
}

export default function FilesExplorer({ repoId }: Props) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [search, setSearch] = useState('');
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [fileSummary, setFileSummary] = useState<FileSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const data = await api.getRepoFiles(repoId);
        setFiles(data.files);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch files');
      } finally {
        setLoading(false);
      }
    };
    fetchFiles();
  }, [repoId]);

  const handleFileClick = async (fileId: number) => {
    setSelectedFileId(fileId);
    setLoadingSummary(true);
    setFileSummary(null);
    try {
      const summary = await api.getFileSummary(repoId, fileId);
      setFileSummary(summary);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSummary(false);
    }
  };

  const filteredFiles = files.filter(f => f.path.toLowerCase().includes(search.toLowerCase()));

  if (loading) return <div className="h-full flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>;
  if (error) return <div className="h-full flex items-center justify-center text-red-400">{error}</div>;

  return (
    <div className="flex h-full relative overflow-hidden bg-dark-900 rounded-xl border border-white/10">
      
      {/* File List */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        <div className="p-4 border-b border-white/10 bg-dark-800">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input 
              type="text" 
              placeholder="Search files..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-dark-900 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
            />
          </div>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {filteredFiles.map(file => (
            <div 
              key={file.id} 
              onClick={() => handleFileClick(file.id)}
              className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${selectedFileId === file.id ? 'bg-white/10 border-cyan-500/50' : 'bg-dark-800 border-white/5 hover:border-white/20'}`}
            >
              <div className="flex items-center truncate mr-4">
                <FileCode className="w-4 h-4 text-gray-500 mr-3 flex-shrink-0" />
                <span className="font-mono text-sm text-gray-300 truncate">{file.path}</span>
              </div>
              <div className="flex items-center space-x-3 flex-shrink-0">
                <span className={`text-[10px] uppercase tracking-wider px-2 py-1 rounded border ${file.role === 'entry_point' ? 'bg-cyan-900/30 text-cyan-400 border-cyan-500/30' : file.role === 'core_module' ? 'bg-violet-900/30 text-violet-400 border-violet-500/30' : 'bg-dark-700 text-gray-400 border-white/10'}`}>
                  {file.role}
                </span>
                <span className="text-xs text-gray-500 font-mono w-12 text-right">
                  ★ {file.centrality_score.toFixed(1)}
                </span>
              </div>
            </div>
          ))}
          {filteredFiles.length === 0 && (
            <div className="text-center text-gray-500 mt-10">No files match your search.</div>
          )}
        </div>
      </div>

      {/* Slide-out File Summary Panel */}
      <div className={`w-96 h-full glass-panel rounded-none border-y-0 border-r-0 flex flex-col transform transition-transform duration-300 ${selectedFileId ? 'translate-x-0 border-l border-white/10' : 'hidden'}`}>
        {selectedFileId && (
          <>
            <div className="p-4 border-b border-white/10 flex justify-between items-center bg-dark-800/80">
              <h3 className="font-mono text-sm truncate pr-4 text-cyan-100" title={files.find(f => f.id === selectedFileId)?.path}>
                {files.find(f => f.id === selectedFileId)?.path.split('/').pop()}
              </h3>
              <button onClick={() => setSelectedFileId(null)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingSummary ? (
                <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
              ) : fileSummary ? (
                <>
                  <div>
                    <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2">AI Summary</h4>
                    <div className="prose prose-sm prose-invert prose-cyan text-gray-300 whitespace-pre-wrap">
                      <ReactMarkdown>{fileSummary.file.summary || '*No summary available.*'}</ReactMarkdown>
                    </div>
                  </div>

                  {fileSummary.file.functions?.length > 0 && (
                    <div>
                      <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2">Functions Defined</h4>
                      <div className="flex flex-wrap gap-2">
                        {fileSummary.file.functions.map((fn, i) => (
                          <span key={i} className="text-xs font-mono bg-dark-800 text-gray-300 px-2 py-1 rounded border border-white/5">{fn}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-white/5">
                    <div>
                      <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2">Imports ({fileSummary.dependencies.length})</h4>
                      <p className="text-2xl font-light text-white">{fileSummary.file.out_degree}</p>
                    </div>
                    <div>
                      <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2">Imported By ({fileSummary.dependents.length})</h4>
                      <p className="text-2xl font-light text-white">{fileSummary.file.in_degree}</p>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center text-gray-500 py-10">No summary data available</div>
              )}
            </div>
          </>
        )}
      </div>

    </div>
  );
}