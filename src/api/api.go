package api

import (
	"fmt"
	"sqlite-cache/src/cache"
)

var globalCacheManager *cache.CacheManager

func Close() error {
	if globalCacheManager == nil {
		return fmt.Errorf("cache manager not initialized")
	}

	if err := globalCacheManager.Close(); err != nil {
		return fmt.Errorf("failed to close cache manager: %w", err)
	}

	globalCacheManager = nil
	return nil
}

// Init initializes the cache system
func Init(baseDir string, maxSize int, cap float64) error {
	globalCacheManager = cache.NewCacheManager(cache.CacheConfig{})

	if err := globalCacheManager.Init(baseDir, maxSize, cap); err != nil {
		return fmt.Errorf("failed to initialize cache manager: %w", err)
	}

	return nil
}

func Get(table, tenantId string, freshness string, bind string) ([]byte, error) {
	if globalCacheManager == nil {
		return nil, fmt.Errorf("cache manager not initialized")
	}

	content, err := globalCacheManager.Get(table, tenantId, freshness, bind)
	if err != nil {
		return nil, fmt.Errorf("failed to get from cache: %w", err)
	}

	return content, nil
}

func Set(table, tenantId string, freshness string, bind string, content []byte) error {
	if globalCacheManager == nil {
		return fmt.Errorf("cache manager not initialized")
	}

	if err := globalCacheManager.Set(table, tenantId, freshness, bind, content); err != nil {
		return fmt.Errorf("failed to set cache: %w", err)
	}

	return nil
}

func Delete(table string) error {
	if globalCacheManager == nil {
		return fmt.Errorf("cache manager not initialized")
	}

	if err := globalCacheManager.Delete(table); err != nil {
		return fmt.Errorf("failed to delete table: %w", err)
	}

	return nil
}
