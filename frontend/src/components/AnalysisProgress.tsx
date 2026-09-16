import { Loader2, DownloadCloud, FileCode2, Network, BrainCircuit, Sparkles } from 'lucide-react';

interface Props {
  status: string;
  repoName: string;
}

export default function AnalysisProgress({ status, repoName }: Props) {
  const steps = [
    { id: 'cloning', label: 'Cloning Repository', icon: DownloadCloud },
    { id: 'parsing', label: 'Parsing ASTs', icon: FileCode2 },
    { id: 'graphing', label: 'Building Dependency Graph', icon: Network },
    { id: 'analyzing', label: 'Structural Analysis', icon: BrainCircuit },
    { id: 'summarizing', label: 'LLM Grounded Summaries', icon: Sparkles },
  ];

  const currentIndex = steps.findIndex(s => s.id === status);
  
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-dark-900 relative">
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCI+PHBhdGggZD0iTTAgMGg0MHY0MEgwem0yMCAyMGMxMS4wNDYgMCAyMC04Ljk1NCAyMC0yMFMyOC45NTQgMCAyMCAwIDAgOC45NTQgMCAyMHM4Ljk1NCAyMCAyMCAyMHoiIGZpbGw9IiNmZmZmZmYiIGZpbGwtb3BhY2l0eT0iMC4wMiIgZmlsbC1ydWxlPSJldmVub2RkIi8+PC9zdmc+')] opacity-50"></div>
      
      <div className="z-10 w-full max-w-lg">
        <div className="text-center mb-10">
          <h2 className="text-3xl font-bold mb-2">Analyzing <span className="text-cyan-400">{repoName}</span></h2>
          <p className="text-gray-400">Please wait while RepoLens processes the codebase.</p>
        </div>

        <div className="glass-panel p-8 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-dark-800">
            <div 
              className="h-full bg-gradient-to-r from-cyan-400 to-violet-500 transition-all duration-1000 ease-out"
              style={{ width: `${Math.max(5, ((currentIndex + 1) / steps.length) * 100)}%` }}
            ></div>
          </div>

          <div className="space-y-6">
            {steps.map((step, idx) => {
              const Icon = step.icon;
              const isPast = currentIndex > idx;
              const isCurrent = currentIndex === idx;
              
              return (
                <div key={step.id} className={`flex items-center transition-all duration-500 ${isPast ? 'opacity-50' : isCurrent ? 'opacity-100 scale-105 transform translate-x-2' : 'opacity-30'}`}>
                  <div className={`
                    w-10 h-10 rounded-full flex items-center justify-center mr-4 border
                    ${isPast ? 'bg-dark-700 border-white/10 text-white' : 
                      isCurrent ? 'bg-cyan-900/40 border-cyan-400 text-cyan-400 shadow-[0_0_15px_rgba(0,245,255,0.3)]' : 
                      'bg-dark-800 border-white/5 text-gray-500'}
                  `}>
                    {isCurrent ? <Loader2 className="w-5 h-5 animate-spin" /> : <Icon className="w-5 h-5" />}
                  </div>
                  <span className={`font-medium ${isCurrent ? 'text-cyan-300' : 'text-gray-300'}`}>
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}