-- RepoLens Comprehension Engine — Database Schema
CREATE TABLE IF NOT EXISTS repos (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    name TEXT,
    primary_language TEXT,
    framework TEXT,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    last_analyzed TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    repo_id INT REFERENCES repos(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    language TEXT,
    role TEXT,
    centrality_score FLOAT DEFAULT 0.0,
    in_degree INT DEFAULT 0,
    out_degree INT DEFAULT 0,
    functions TEXT[],
    classes TEXT[],
    imports TEXT[],
    exports TEXT[],
    summary TEXT,
    UNIQUE(repo_id, path)
);

CREATE TABLE IF NOT EXISTS dependencies (
    id SERIAL PRIMARY KEY,
    repo_id INT REFERENCES repos(id) ON DELETE CASCADE,
    source_file_id INT REFERENCES files(id) ON DELETE CASCADE,
    target_file_id INT REFERENCES files(id) ON DELETE CASCADE,
    import_name TEXT,
    UNIQUE(repo_id, source_file_id, target_file_id)
);

CREATE TABLE IF NOT EXISTS architecture_overviews (
    id SERIAL PRIMARY KEY,
    repo_id INT REFERENCES repos(id) ON DELETE CASCADE,
    narrative TEXT,
    entry_points JSONB,
    core_modules JSONB,
    cycles JSONB,
    stats JSONB,
    generated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_files_repo_id ON files(repo_id);
CREATE INDEX IF NOT EXISTS idx_files_role ON files(role);
CREATE INDEX IF NOT EXISTS idx_deps_repo_id ON dependencies(repo_id);
CREATE INDEX IF NOT EXISTS idx_deps_source ON dependencies(source_file_id);
CREATE INDEX IF NOT EXISTS idx_deps_target ON dependencies(target_file_id);
CREATE INDEX IF NOT EXISTS idx_arch_repo_id ON architecture_overviews(repo_id);
