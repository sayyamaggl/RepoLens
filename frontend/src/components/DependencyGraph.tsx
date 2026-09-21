import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { api } from '../api/client';
import { GraphResponse, GraphNode, FileSummaryResponse } from '../types';
import { Loader2, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Props {
  repoId: number;
}

export default function DependencyGraph({ repoId }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [fileSummary, setFileSummary] = useState<FileSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    api.getRepoGraph(repoId)
      .then(data => {
        setGraphData(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [repoId]);

  useEffect(() => {
    if (!graphData || !svgRef.current || !containerRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);
      
    svg.selectAll('*').remove(); // Clear previous render

    const g = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Filter out disconnected nodes for better visualization
    const connectedNodeIds = new Set<string>();
    graphData.edges.forEach(e => {
      connectedNodeIds.add(e.source);
      connectedNodeIds.add(e.target);
    });
    
    // Keep nodes with high centrality even if disconnected
    const nodes = graphData.nodes
      .filter(n => connectedNodeIds.has(n.id) || n.centrality_score > 0)
      .map(d => ({ ...d })); // Clone objects for D3
      
    const edges = graphData.edges
      .filter(e => nodes.some(n => n.id === e.source) && nodes.some(n => n.id === e.target))
      .map(d => ({ ...d }));

    // Simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-80))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.05))
      .force('collision', d3.forceCollide().radius((d: any) => Math.max(20, (d.centrality_score * 50) + 10)));

    // Arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '-0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('orient', 'auto')
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('xoverflow', 'visible')
      .append('svg:path')
      .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
      .attr('fill', 'rgba(255,255,255,0.2)');

    // Draw edges
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .enter().append('line')
      .attr('stroke', 'rgba(255,255,255,0.1)')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrowhead)');

    // Draw nodes
    const nodeGroup = g.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .enter().append('g')
      .call(d3.drag<any, any>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended)
      )
      .on('click', (event, d: any) => {
        handleNodeClick(d.id);
      });

    // Node circles
    nodeGroup.append('circle')
      .attr('r', (d: any) => Math.max(8, (d.centrality_score * 30) + 5))
      .attr('fill', (d: any) => {
        switch(d.role) {
          case 'entry_point': return '#00f5ff'; // cyan
          case 'core_module': return '#8b5cf6'; // violet
          case 'test': return '#10b981'; // emerald
          case 'config': return '#f59e0b'; // amber
          default: return '#3a3a5c'; // gray
        }
      })
      .attr('stroke', (d: any) => d.id === selectedNode ? '#fff' : 'transparent')
      .attr('stroke-width', 3)
      .attr('class', 'cursor-pointer transition-all duration-300')
      .style('filter', (d: any) => {
        if (d.role === 'entry_point') return 'drop-shadow(0 0 10px rgba(0,245,255,0.5))';
        if (d.role === 'core_module') return 'drop-shadow(0 0 10px rgba(139,92,246,0.5))';
        return 'none';
      });

    // Node labels
    nodeGroup.append('text')
      .text((d: any) => d.id.split('/').pop())
      .attr('x', 15)
      .attr('y', 4)
      .attr('fill', '#a1a1aa')
      .attr('font-size', '12px')
      .attr('font-family', 'JetBrains Mono, monospace')
      .style('pointer-events', 'none')
      .style('opacity', (d: any) => (d.role === 'entry_point' || d.role === 'core_module') ? 1 : 0)
      .attr('class', 'node-label transition-opacity duration-300');

    // Show labels on hover
    nodeGroup.on('mouseover', function() {
      d3.select(this).select('.node-label').style('opacity', 1);
    }).on('mouseout', function(event, d: any) {
      if (d.role !== 'entry_point' && d.role !== 'core_module') {
        d3.select(this).select('.node-label').style('opacity', 0);
      }
    });

    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      nodeGroup
        .attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    function dragstarted(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event: any, d: any) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event: any, d: any) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    return () => {
      simulation.stop();
    };
  }, [graphData, selectedNode]);

  const handleNodeClick = async (nodeId: string) => {
    setSelectedNode(nodeId);
    setLoadingSummary(true);
    try {
      // GraphNode only exposes the file's path, not its numeric id, so we
      // resolve it via the files list (already exposed through api.getRepoFiles).
      const filesRes = await api.getRepoFiles(repoId);
      const file = filesRes.files.find((f: any) => f.path === nodeId);

      if (file) {
        const summary = await api.getFileSummary(repoId, file.id);
        setFileSummary(summary);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSummary(false);
    }
  };

  if (loading) return <div className="h-full flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-cyan-400" /></div>;
  if (error) return <div className="h-full flex items-center justify-center text-red-400">{error}</div>;

  return (
    <div className="w-full h-full relative" ref={containerRef}>
      <svg ref={svgRef} className="w-full h-full bg-dark-900"></svg>
      
      {/* Graph Legend */}
      <div className="absolute top-4 left-4 glass-panel p-4 text-sm">
        <h4 className="font-bold mb-3 text-gray-300">Legend</h4>
        <div className="space-y-2">
          <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-cyan-400 mr-2 shadow-[0_0_8px_rgba(0,245,255,0.5)]"></span> Entry Point</div>
          <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-violet-500 mr-2 shadow-[0_0_8px_rgba(139,92,246,0.5)]"></span> Core Module</div>
          <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-emerald-500 mr-2"></span> Test</div>
          <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-amber-500 mr-2"></span> Config</div>
          <div className="flex items-center"><span className="w-3 h-3 rounded-full bg-dark-400 mr-2"></span> Utility / Leaf</div>
        </div>
      </div>

      {/* Slide-out File Summary Panel */}
      <div className={`absolute top-0 right-0 w-96 h-full glass-panel rounded-none border-r-0 border-y-0 transform transition-transform duration-300 ease-in-out ${selectedNode ? 'translate-x-0' : 'translate-x-full'}`}>
        {selectedNode && (
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-white/10 flex justify-between items-center bg-dark-800/80">
              <h3 className="font-mono text-sm truncate pr-4 text-cyan-100" title={selectedNode}>{selectedNode}</h3>
              <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingSummary ? (
                <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
              ) : fileSummary ? (
                <>
                  <div>
                    <span className={`inline-block px-2 py-1 rounded text-xs font-mono mb-4 border ${
                      fileSummary.file.role === 'entry_point' ? 'bg-cyan-900/30 text-cyan-400 border-cyan-500/30' :
                      fileSummary.file.role === 'core_module' ? 'bg-violet-900/30 text-violet-400 border-violet-500/30' :
                      'bg-dark-700 text-gray-300 border-white/10'
                    }`}>
                      Role: {fileSummary.file.role}
                    </span>
                    
                    <h4 className="text-gray-400 text-xs uppercase tracking-wider mb-2">AI Summary</h4>
                    <div className="prose prose-sm prose-invert prose-cyan text-gray-300">
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
          </div>
        )}
      </div>
    </div>
  );
}