package main

/*
#include <stdlib.h>
#include <string.h>
*/
import "C"
import (
	"sqlite-cache/src/api"
	"strings"
	"unsafe"
)

// Error codes for Python ctypes integration
const (
	SUCCESS           = 1
	ERROR_GENERAL     = 0
	ERROR_DISK_FULL   = -1
	ERROR_INVALID_ARG = -2
	ERROR_NOT_FOUND   = -3
	ERROR_NOT_INIT    = -4
)

// Cライブラリインターフェース用のエクスポート関数

//export Init
func Init(baseDir *C.char, maxSize C.int, cap C.double) C.int {
	if baseDir == nil {
		return ERROR_INVALID_ARG
	}

	err := api.Init(C.GoString(baseDir), int(maxSize), float64(cap))
	if err != nil {
		if isDiskFullError(err) {
			return ERROR_DISK_FULL
		}
		return ERROR_GENERAL
	}
	return SUCCESS
}

//export Get
func Get(table *C.char, tenantId *C.char, freshness *C.char, bind *C.char, resultLen *C.int) *C.char {
	if table == nil || tenantId == nil || freshness == nil || bind == nil || resultLen == nil {
		if resultLen != nil {
			*resultLen = ERROR_INVALID_ARG
		}
		return nil
	}

	result, err := api.Get(C.GoString(table), C.GoString(tenantId), C.GoString(freshness), C.GoString(bind))
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "not found") {
			*resultLen = ERROR_NOT_FOUND
		} else if isDiskFullError(err) {
			*resultLen = ERROR_DISK_FULL
		} else if strings.Contains(strings.ToLower(err.Error()), "not init") {
			*resultLen = ERROR_NOT_INIT
		} else {
			*resultLen = ERROR_GENERAL
		}
		return nil
	}

	if result == nil || len(result) == 0 {
		*resultLen = ERROR_NOT_FOUND
		return nil
	}

	*resultLen = C.int(len(result))
	return (*C.char)(C.CBytes(result))
}

//export Set
func Set(table *C.char, tenantId *C.char, freshness *C.char, bind *C.char, content *C.char, contentLen C.int) C.int {
	if table == nil || tenantId == nil || freshness == nil || bind == nil || content == nil {
		return ERROR_INVALID_ARG
	}

	contentBytes := C.GoBytes(unsafe.Pointer(content), contentLen)
	err := api.Set(C.GoString(table), C.GoString(tenantId), C.GoString(freshness), C.GoString(bind), contentBytes)
	if err != nil {
		if isDiskFullError(err) {
			return ERROR_DISK_FULL
		}
		if strings.Contains(strings.ToLower(err.Error()), "not init") {
			return ERROR_NOT_INIT
		}
		return ERROR_GENERAL
	}
	return SUCCESS
}

//export Delete
func Delete(table *C.char) C.int {
	if table == nil {
		return ERROR_INVALID_ARG
	}

	err := api.Delete(C.GoString(table))
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "not init") {
			return ERROR_NOT_INIT
		}
		return ERROR_GENERAL
	}
	return SUCCESS
}

//export Close
func Close() C.int {
	err := api.Close()
	if err != nil {
		return ERROR_GENERAL
	}
	return SUCCESS
}

//export FreeMem
func FreeMem(ptr *C.char) {
	if ptr != nil {
		C.free(unsafe.Pointer(ptr))
	}
}

// isDiskFullError checks if error is related to disk space issues
func isDiskFullError(err error) bool {
	if err == nil {
		return false
	}
	errStr := strings.ToLower(err.Error())
	return strings.Contains(errStr, "disk full") ||
		strings.Contains(errStr, "no space left on device") ||
		strings.Contains(errStr, "database or disk is full") ||
		strings.Contains(errStr, "insufficient disk space") ||
		strings.Contains(errStr, "sqlite_full")
}
