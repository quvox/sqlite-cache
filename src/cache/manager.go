package cache

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	_ "github.com/mattn/go-sqlite3"
)

func NewCacheManager(config CacheConfig) *CacheManager {
	return &CacheManager{
		config: config,
		dbs:    make(map[string]*sql.DB),
	}
}

func (cm *CacheManager) Init(baseDir string, maxSize int, cap float64) error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	if cap < 0 || cap > 0.95 {
		return fmt.Errorf("cap must be between 0 and 0.95, got %f", cap)
	}

	cm.config = CacheConfig{
		BaseDir: baseDir,
		MaxSize: maxSize,
		Cap:     cap,
	}

	// ベースディレクトリを作成
	if err := os.MkdirAll(baseDir, 0755); err != nil {
		return fmt.Errorf("failed to create base directory: %w", err)
	}

	return nil
}

func (cm *CacheManager) getDBPath(table, tenantID string, freshness int64) string {
	return filepath.Join(cm.config.BaseDir, table, tenantID, fmt.Sprintf("%d.db", freshness))
}

func (cm *CacheManager) getDBKey(table, tenantID string, freshness int64) string {
	return fmt.Sprintf("%s:%s:%d", table, tenantID, freshness)
}

func (cm *CacheManager) openDB(table, tenantID string, freshness int64) (*sql.DB, error) {
	dbKey := cm.getDBKey(table, tenantID, freshness)

	if db, exists := cm.dbs[dbKey]; exists {
		return db, nil
	}

	dbPath := cm.getDBPath(table, tenantID, freshness)

	// ディレクトリを作成
	if err := os.MkdirAll(filepath.Dir(dbPath), 0755); err != nil {
		return nil, fmt.Errorf("failed to create directory: %w", err)
	}

	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// PRAGMA設定を適用
	if err := cm.configurePragmas(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to configure pragmas: %w", err)
	}

	// テーブルを作成
	if err := cm.createTables(db); err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to create tables: %w", err)
	}

	cm.dbs[dbKey] = db
	return db, nil
}

func (cm *CacheManager) configurePragmas(db *sql.DB) error {
	// ページサイズは4KB
	const pageSize = 4096

	// 最大ファイルサイズからページ数を計算（安全マージンを追加）
	maxSizeBytes := int64(cm.config.MaxSize) * 1024 * 1024 // MB to bytes
	maxPageCount := (maxSizeBytes * 2) / pageSize          // 2倍のマージンを設定

	pragmas := []string{
		"PRAGMA journal_mode = OFF",
		"PRAGMA synchronous = NORMAL",
		fmt.Sprintf("PRAGMA page_size = %d", pageSize),
		fmt.Sprintf("PRAGMA max_page_count = %d", maxPageCount),
	}

	for _, pragma := range pragmas {
		if _, err := db.Exec(pragma); err != nil {
			return fmt.Errorf("failed to execute pragma '%s': %w", pragma, err)
		}
	}

	return nil
}

func (cm *CacheManager) createTables(db *sql.DB) error {
	query := `
	CREATE TABLE IF NOT EXISTS cache_entries (
		key TEXT PRIMARY KEY,
		content BLOB,
		last_accessed INTEGER,
		created_at INTEGER
	);
	CREATE INDEX IF NOT EXISTS idx_last_accessed ON cache_entries(last_accessed);
	`
	_, err := db.Exec(query)
	return err
}

func (cm *CacheManager) cleanupOldCacheFiles(table, tenantID string, currentFreshness int64) error {
	tenantDir := filepath.Join(cm.config.BaseDir, table, tenantID)

	entries, err := os.ReadDir(tenantDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}

		fileName := entry.Name()
		if !strings.HasSuffix(fileName, ".db") {
			continue
		}

		// ファイル名からフレッシュネス値を取得
		freshnessStr := strings.TrimSuffix(fileName, ".db")
		freshness, err := strconv.ParseInt(freshnessStr, 10, 64)
		if err != nil {
			continue
		}

		// 現在のフレッシュネス値と異なる場合は削除
		if freshness != currentFreshness {
			filePath := filepath.Join(tenantDir, fileName)

			// DBキャッシュからも削除
			dbKey := cm.getDBKey(table, tenantID, freshness)
			if db, exists := cm.dbs[dbKey]; exists {
				db.Close()
				delete(cm.dbs, dbKey)
			}

			os.Remove(filePath)
		}
	}

	return nil
}

func (cm *CacheManager) Close() error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	for _, db := range cm.dbs {
		if err := db.Close(); err != nil {
			return err
		}
	}
	cm.dbs = make(map[string]*sql.DB)
	return nil
}
