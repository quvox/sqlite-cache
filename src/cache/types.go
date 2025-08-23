package cache

import (
	"database/sql"
	"sync"
)

type CacheConfig struct {
	BaseDir string
	MaxSize int     // MB単位
	Cap     float64 // 削除する割合 (0~0.95)
}

type CacheManager struct {
	config CacheConfig
	mutex  sync.RWMutex
	dbs    map[string]*sql.DB
}

type CacheEntry struct {
	Key          string
	Content      []byte
	LastAccessed int64
	CreatedAt    int64
}
