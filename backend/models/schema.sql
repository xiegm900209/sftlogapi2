-- sftlogapi SQLite 索引库 Schema
-- 支持 7 天日志滚动，按小时分表

-- ============================================
-- 元数据表：跟踪已同步的日志文件
-- ============================================
CREATE TABLE IF NOT EXISTS sync_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_file TEXT UNIQUE NOT NULL,        -- 日志文件完整路径
    index_file TEXT NOT NULL,              -- 索引文件完整路径
    log_hour TEXT NOT NULL,                -- 日志小时 (YYYYMMDDHH)
    service TEXT NOT NULL,                 -- 服务名称
    synced_at TEXT NOT NULL,               -- 同步时间
    log_size INTEGER,                      -- 日志文件大小 (字节)
    index_size INTEGER,                    -- 索引文件大小 (字节)
    record_count INTEGER,                  -- 索引记录数
    status TEXT DEFAULT 'synced'           -- synced, failed, pending
);

CREATE INDEX IF NOT EXISTS idx_sync_hour ON sync_meta(log_hour);
CREATE INDEX IF NOT EXISTS idx_sync_service ON sync_meta(service);
CREATE INDEX IF NOT EXISTS idx_sync_status ON sync_meta(status);

-- ============================================
-- 主索引表模板 (按小时分表)
-- 实际表名：logs_YYYYMMDDHH
-- ============================================
-- 示例：CREATE TABLE logs_2026040809 (...)

-- ============================================
-- 全局查询视图 (联合所有小时表)
-- 注意：需要动态创建，这里只是示例
-- ============================================
-- CREATE VIEW IF NOT EXISTS all_logs AS
-- SELECT * FROM logs_2026040809
-- UNION ALL SELECT * FROM logs_2026040810
-- UNION ALL SELECT * FROM logs_2026040811
-- ...

-- ============================================
-- 统计表：快速查询统计信息
-- ============================================
CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,               -- 日期 (YYYYMMDD)
    stat_hour TEXT NOT NULL,               -- 小时 (YYYYMMDDHH)
    service TEXT NOT NULL,
    total_records INTEGER DEFAULT 0,
    total_trace_ids INTEGER DEFAULT 0,
    total_req_sn INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(stat_hour, service)
);

CREATE INDEX IF NOT EXISTS idx_stats_hour ON stats(stat_hour);
CREATE INDEX IF NOT EXISTS idx_stats_date ON stats(stat_date);

-- ============================================
-- 缓存元数据：记录热点 TraceID
-- ============================================
CREATE TABLE IF NOT EXISTS cache_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id TEXT NOT NULL,
    access_count INTEGER DEFAULT 1,
    last_accessed TEXT DEFAULT (datetime('now')),
    cached_at TEXT DEFAULT (datetime('now')),
    UNIQUE(trace_id)
);

CREATE INDEX IF NOT EXISTS idx_cache_trace ON cache_meta(trace_id);
CREATE INDEX IF NOT EXISTS idx_cache_access ON cache_meta(access_count DESC);
