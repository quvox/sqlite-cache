package cache

import (
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func (cm *CacheManager) Get(table, tenantID string, freshness string, bind string) ([]byte, error) {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()

	dbPath := cm.getDBPath(table, tenantID, freshness)

	// キャッシュファイルが存在しない場合
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		// 古いキャッシュファイルを削除
		if cleanErr := cm.cleanupOldCacheFiles(table, tenantID, freshness); cleanErr != nil {
			return nil, fmt.Errorf("failed to cleanup old cache files: %w", cleanErr)
		}
		return nil, fmt.Errorf("cache not found")
	}

	db, err := cm.openDB(table, tenantID, freshness)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// UPDATE...RETURNINGを使って、最新アクセス時刻を更新しつつコンテンツを取得
	now := time.Now().Unix()
	var content []byte

	query := "UPDATE cache SET last_accessed = ? WHERE bind = ? RETURNING content"
	err = db.QueryRow(query, now, bind).Scan(&content)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("cache entry not found")
		}
		return nil, fmt.Errorf("failed to update and query cache: %w", err)
	}

	return content, nil
}

func (cm *CacheManager) Set(table, tenantID string, freshness string, bind string, content []byte) error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	dbPath := cm.getDBPath(table, tenantID, freshness)

	// キャッシュファイルが存在しない場合、古いファイルを削除
	if _, err := os.Stat(dbPath); os.IsNotExist(err) {
		if cleanErr := cm.cleanupOldCacheFiles(table, tenantID, freshness); cleanErr != nil {
			return fmt.Errorf("failed to cleanup old cache files: %w", cleanErr)
		}
	}

	db, err := cm.openDB(table, tenantID, freshness)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}

	now := time.Now().Unix()

	// 事前にサイズチェックとLRU削除を実行
	if err := cm.enforceSize(db); err != nil {
		return fmt.Errorf("failed to enforce size limits before insert: %w", err)
	}

	// エントリを挿入または更新
	query := `
	INSERT OR REPLACE INTO cache (bind, content, last_accessed)
	VALUES (?, ?, ?)
	`
	_, err = db.Exec(query, bind, content, now)
	if err != nil {
		return fmt.Errorf("failed to insert cache entry: %w", err)
	}

	return nil
}

func (cm *CacheManager) Delete(table string) error {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()

	tableDir := filepath.Join(cm.config.BaseDir, table)

	// 該当テーブルのDBキャッシュをクローズ
	for key, db := range cm.dbs {
		if len(key) > len(table) && key[:len(table)] == table && key[len(table)] == ':' {
			db.Close()
			delete(cm.dbs, key)
		}
	}

	// テーブルディレクトリを削除
	return os.RemoveAll(tableDir)
}

func (cm *CacheManager) enforceSize(db *sql.DB) error {
	// データベースファイルサイズをチェック
	dbPath := ""
	row := db.QueryRow("PRAGMA database_list")
	var seq int
	var name string
	if err := row.Scan(&seq, &name, &dbPath); err != nil {
		return err
	}

	if stat, err := os.Stat(dbPath); err == nil {
		sizeMB := float64(stat.Size()) / (1024 * 1024)

		if sizeMB > float64(cm.config.MaxSize) {
			// LRUアルゴリズムで古いレコードを削除
			return cm.lruCleanup(db)
		}
	}

	return nil
}

func (cm *CacheManager) lruCleanup(db *sql.DB) error {
	// 現在のレコード数を取得
	var totalCount int
	err := db.QueryRow("SELECT COUNT(*) FROM cache").Scan(&totalCount)
	if err != nil {
		return err
	}

	// 残すべき数を計算し、削除する数を決定
	keepCount := int(float64(totalCount) * cm.config.Cap)
	deleteCount := totalCount - keepCount
	if deleteCount <= 0 {
		return nil
	}

	// 古いレコードを削除
	query := `
	DELETE FROM cache 
	WHERE id IN (
		SELECT id FROM cache 
		ORDER BY last_accessed ASC 
		LIMIT ?
	)
	`
	_, err = db.Exec(query, deleteCount)
	if err != nil {
		return fmt.Errorf("failed to delete old entries: %w", err)
	}

	// VACUUMでデータベースを最適化
	_, err = db.Exec("VACUUM")
	return err
}
