package api

import (
	"sqlite-cache/src/cache"
)

var globalCacheManager *cache.CacheManager

func Close() bool {
	if globalCacheManager == nil {
		return false
	}

	if err := globalCacheManager.Close(); err != nil {
		return false
	}

	globalCacheManager = nil
	return true
}

// Init initializes the cache system
func Init(baseDir string, maxSize int, cap float64) bool {
	globalCacheManager = cache.NewCacheManager(cache.CacheConfig{})

	if err := globalCacheManager.Init(baseDir, maxSize, cap); err != nil {
		return false
	}

	return true
}

func Get(table, tenantId string, freshness string, bind string) []byte {
	if globalCacheManager == nil {
		return nil
	}

	content, err := globalCacheManager.Get(table, tenantId, freshness, bind)
	if err != nil {
		return nil
	}

	return content
}

func Set(table, tenantId string, freshness string, bind string, content []byte) bool {
	if globalCacheManager == nil {
		return false
	}

	if err := globalCacheManager.Set(table, tenantId, freshness, bind, content); err != nil {
		return false
	}

	return true
}

func Delete(table string) bool {
	if globalCacheManager == nil {
		return false
	}

	if err := globalCacheManager.Delete(table); err != nil {
		return false
	}

	return true
}
