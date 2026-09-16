export interface RepoInfo {
  id: number;
  url: string;
  name?: string;
  primary_language?: string;
  framework?: string;
  status: string;
  error_message?: string;
  last_analyzed?: string;
}

export interface FileInfo {
  id: number;
  path: string;
  language?: string;
  role?: string;
  centrality_score: number;
  in_degree: number;
  out_degree: number;
  functions: string[];
  classes: string[];
  summary?: string;
}

export interface EntryPointInfo {
  path: string;
  score: number;
  reasons: string[];
  in_degree: number;
  out_degree: number;
}

export interface CoreModuleInfo {
  path: string;
  score: number;
  in_degree: number;
  out_degree: number;
  betweenness: number;
}

export interface OverviewResponse {
  repo: RepoInfo;
  narrative?: string;
  entry_points: EntryPointInfo[];
  core_modules: CoreModuleInfo[];
  cycles: string[][];
  stats?: Record<string, any>;
  generated_at?: string;
}

export interface DependencyEdge {
  source: string;
  target: string;
  import_name?: string;
}

export interface GraphNode {
  id: string;
  language: string;
  functions: string[];
  classes: string[];
  role: string;
  centrality_score: number;
  in_degree: number;
  out_degree: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: DependencyEdge[];
}

export interface FileSummaryResponse {
  file: FileInfo;
  dependents: string[];
  dependencies: string[];
}