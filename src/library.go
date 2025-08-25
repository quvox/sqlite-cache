package main

/*
#include <stdlib.h>
#include <string.h>
*/
import "C"
import (
	"sqlite-cache/src/api"
	"unsafe"
)

// Cライブラリインターフェース用のエクスポート関数

//export Init
func Init(baseDir *C.char, maxSize C.int, cap C.double) C.int {
	result := api.Init(C.GoString(baseDir), int(maxSize), float64(cap))
	if result {
		return 1
	}
	return 0
}

//export Get
func Get(table *C.char, tenantId *C.char, freshness *C.char, bind *C.char, resultLen *C.int) *C.char {
	result := api.Get(C.GoString(table), C.GoString(tenantId), C.GoString(freshness), C.GoString(bind))
	if result == nil || len(result) == 0 {
		*resultLen = 0
		return nil
	}

	*resultLen = C.int(len(result))

	// C.CBytesを使用してGoが管理するメモリを使用
	return (*C.char)(C.CBytes(result))
}

//export Set
func Set(table *C.char, tenantId *C.char, freshness *C.char, bind *C.char, content *C.char, contentLen C.int) C.int {
	contentBytes := C.GoBytes(unsafe.Pointer(content), contentLen)
	result := api.Set(C.GoString(table), C.GoString(tenantId), C.GoString(freshness), C.GoString(bind), contentBytes)
	if result {
		return 1
	}
	return 0
}

//export Delete
func Delete(table *C.char) C.int {
	result := api.Delete(C.GoString(table))
	if result {
		return 1
	}
	return 0
}

//export Close
func Close() C.int {
	result := api.Close()
	if result {
		return 1
	}
	return 0
}

//export FreeMem
func FreeMem(ptr *C.char) {
	if ptr != nil {
		C.free(unsafe.Pointer(ptr))
	}
}
