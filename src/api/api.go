package api

import (
	"encoding/json"
	"sqlite-cache/src/cache"
)

var globalCacheManager *cache.CacheManager

type InitRequest struct {
	BaseDir string  `json:"base_dir"`
	MaxSize int     `json:"max_size"`
	Cap     float64 `json:"cap"`
}

type GetRequest struct {
	Table     string `json:"table"`
	TenantID  string `json:"tenant_id"`
	Freshness int64  `json:"freshness"`
	Bind      string `json:"bind"`
}

type SetRequest struct {
	Table     string `json:"table"`
	TenantID  string `json:"tenant_id"`
	Freshness int64  `json:"freshness"`
	Bind      string `json:"bind"`
	Content   []byte `json:"content"`
}

type DeleteRequest struct {
	Table string `json:"table"`
}

type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}

func Init(jsonRequest string) string {
	var req InitRequest
	if err := json.Unmarshal([]byte(jsonRequest), &req); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	globalCacheManager = cache.NewCacheManager(cache.CacheConfig{})

	if err := globalCacheManager.Init(req.BaseDir, req.MaxSize, req.Cap); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func Get(jsonRequest string) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	var req GetRequest
	if err := json.Unmarshal([]byte(jsonRequest), &req); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	content, err := globalCacheManager.Get(req.Table, req.TenantID, req.Freshness, req.Bind)
	if err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true, Data: content})
}

func Set(jsonRequest string) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	var req SetRequest
	if err := json.Unmarshal([]byte(jsonRequest), &req); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	if err := globalCacheManager.Set(req.Table, req.TenantID, req.Freshness, req.Bind, req.Content); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func Delete(jsonRequest string) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	var req DeleteRequest
	if err := json.Unmarshal([]byte(jsonRequest), &req); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	if err := globalCacheManager.Delete(req.Table); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func Close() string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	if err := globalCacheManager.Close(); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	globalCacheManager = nil
	return toJSON(Response{Success: true})
}

// 個別引数版の関数
func InitParams(baseDir string, maxSize int, cap float64) string {
	globalCacheManager = cache.NewCacheManager(cache.CacheConfig{})

	if err := globalCacheManager.Init(baseDir, maxSize, cap); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func GetParams(table, tenantId string, freshness int64, bind string) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	content, err := globalCacheManager.Get(table, tenantId, freshness, bind)
	if err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true, Data: content})
}

func SetParams(table, tenantId string, freshness int64, bind string, content []byte) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	if err := globalCacheManager.Set(table, tenantId, freshness, bind, content); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func DeleteParams(table string) string {
	if globalCacheManager == nil {
		return toJSON(Response{Success: false, Error: "cache not initialized"})
	}

	if err := globalCacheManager.Delete(table); err != nil {
		return toJSON(Response{Success: false, Error: err.Error()})
	}

	return toJSON(Response{Success: true})
}

func toJSON(response Response) string {
	data, _ := json.Marshal(response)
	return string(data)
}
