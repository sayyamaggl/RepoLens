import ReactMarkdown from 'react-markdown';
import { OverviewResponse, EntryPointInfo, CoreModuleInfo } from '../types';
import { FileCode, Zap, Layers, AlertOctagon, Activity, FileText, Database } from 'lucide-react';
import { useState } from 'react';

interface Props {
  overview: OverviewResponse;
}

export default function ArchitectureOverview({ overview }: Props) {
  const [showFullNarrative, setShowFullNarrative] = useState(true);

  return (
    <div className="space-y-6 pb-12 animate-fade-in">
      
      {/* Metrics Dashboard */}
      {overview.stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="glass-card p-4 text-center border-white/5">
            <FileText className="w-6 h-6 text-cyan-400 mx-auto mb-2" />
            <div className="text-2xl font-light text-white">{overview.stats.total_files || 0}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Files</div>
          </div>
          <div className="glass-card p-4 text-center border-white/5">
            <Activity className="w-6 h-6 text-violet-400 mx-auto mb-2" />
            <div className="text-2xl font-light text-white">{overview.stats.total_dependencies || 0}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Dependencies</div>
          </div>
          <div className="glass-card p-4 text-center border-white/5">
            <Zap className="w-6 h-6 text-amber-400 mx-auto mb-2" />
            <div className="text-2xl font-light text-white">{overview.entry_points.length}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Entry Points</div>
          </div>
          <div className="glass-card p-4 text-center border-white/5">
            <Database className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
            <div className="text-2xl font-light text-white">{overview.core_modules.length}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wider mt-1">Core Modules</div>
          </div>
        </div>
      )}

      {/* Narrative Card */}
      <div className="neon-border mb-8">
        <div className="bg-dark-800/90 backdrop-blur-xl p-8 rounded-xl relative">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold flex items-center neon-text-cyan">
              <Layers className="w-6 h-6 mr-3 text-cyan-400" />
              Executive Summary
            </h2>
            <button 
              onClick={() => setShowFullNarrative(!showFullNarrative)}
              className="text-xs text-cyan-400 hover:text-cyan-300 uppercase tracking-wider"
            >
              {showFullNarrative ? 'Collapse' : 'Expand'}
            </button>
          </div>
          
          <div className={`prose prose-invert prose-cyan max-w-none text-gray-300 leading-relaxed font-light whitespace-pre-wrap transition-all duration-500 ${showFullNarrative ? '' : 'max-h-40 overflow-hidden relative'}`}>
            <ReactMarkdown>{overview.narrative || '*No narrative generated.*'}</ReactMarkdown>
            {!showFullNarrative && (
              <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-dark-800 to-transparent pointer-events-none"></div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Entry Points */}
        <div className="glass-card p-6 border-cyan-500/20">
          <h3 className="text-lg font-bold mb-4 flex items-center text-cyan-300">
            <Zap className="w-5 h-5 mr-2" />
            Entry Points ({overview.entry_points.length})
          </h3>
          <p className="text-sm text-gray-400 mb-4">Files that act as the roots of execution.</p>
          
          <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
            {overview.entry_points.length === 0 && <p className="text-sm text-gray-500 italic">None detected</p>}
            {overview.entry_points.map((ep: EntryPointInfo, idx: number) => (
              <div key={idx} className="bg-dark-900/50 rounded-lg p-3 border border-white/5 hover:border-cyan-500/30 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-mono text-sm text-cyan-100 break-all">{ep.path}</span>
                  <span className="text-xs font-mono bg-cyan-900/30 text-cyan-400 px-2 py-0.5 rounded border border-cyan-500/20 whitespace-nowrap ml-2">
                    score: {ep.score.toFixed(1)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  {ep.reasons.map((r, i) => (
                    <span key={i} className="text-[10px] uppercase tracking-wider bg-white/5 text-gray-400 px-1.5 py-0.5 rounded">
                      {r.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Core Modules */}
        <div className="glass-card p-6 border-violet-500/20">
          <h3 className="text-lg font-bold mb-4 flex items-center text-violet-300">
            <FileCode className="w-5 h-5 mr-2" />
            Core Modules ({overview.core_modules.length})
          </h3>
          <p className="text-sm text-gray-400 mb-4">Central files that connect many parts of the codebase.</p>
          
          <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
            {overview.core_modules.length === 0 && <p className="text-sm text-gray-500 italic">None detected</p>}
            {overview.core_modules.map((cm: CoreModuleInfo, idx: number) => (
              <div key={idx} className="bg-dark-900/50 rounded-lg p-3 border border-white/5 hover:border-violet-500/30 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <span className="font-mono text-sm text-violet-100 break-all">{cm.path}</span>
                  <span className="text-xs font-mono bg-violet-900/30 text-violet-400 px-2 py-0.5 rounded border border-violet-500/20 whitespace-nowrap ml-2">
                    in: {cm.in_degree}
                  </span>
                </div>
                <div className="w-full bg-dark-800 rounded-full h-1 mt-2">
                  <div 
                    className="bg-gradient-to-r from-violet-500 to-fuchsia-500 h-1 rounded-full" 
                    style={{ width: `${Math.min(100, cm.score)}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Cycles */}
      {overview.cycles.length > 0 && (
        <div className="glass-card p-6 border-amber-500/20">
          <h3 className="text-lg font-bold mb-4 flex items-center text-amber-400">
            <AlertOctagon className="w-5 h-5 mr-2" />
            Cyclic Dependencies Detected ({overview.cycles.length})
          </h3>
          <div className="space-y-3">
            {overview.cycles.map((cycle: string[], idx: number) => (
              <div key={idx} className="bg-amber-900/10 rounded-lg p-3 border border-amber-500/20">
                <div className="flex flex-wrap items-center text-sm font-mono text-amber-200/70">
                  {cycle.map((node, i) => (
                    <span key={i} className="flex items-center">
                      <span className="text-amber-100">{node.split('/').pop()}</span>
                      <span className="mx-2 text-amber-500/50">{'->'}</span>
                    </span>
                  ))}
                  <span className="text-amber-100">{cycle[0].split('/').pop()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}