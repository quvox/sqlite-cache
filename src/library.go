package main

import "C"
import (
	"sqlite-cache/src/api"
	"unsafe"
)

// Cライブラリインターフェース用のエクスポート関数

//export Init
func Init(baseDir *C.char, maxSize C.int, cap C.double) *C.char {
	result := api.InitParams(C.GoString(baseDir), int(maxSize), float64(cap))
	return C.CString(result)
}

//export Get
func Get(table *C.char, tenantId *C.char, freshness C.longlong, bind *C.char) *C.char {
	result := api.GetParams(C.GoString(table), C.GoString(tenantId), int64(freshness), C.GoString(bind))
	return C.CString(result)
}

//export Set
func Set(table *C.char, tenantId *C.char, freshness C.longlong, bind *C.char, content *C.char, contentLen C.int) *C.char {
	contentBytes := C.GoBytes(unsafe.Pointer(content), contentLen)
	result := api.SetParams(C.GoString(table), C.GoString(tenantId), int64(freshness), C.GoString(bind), contentBytes)
	return C.CString(result)
}

//export Delete
func Delete(table *C.char) *C.char {
	result := api.DeleteParams(C.GoString(table))
	return C.CString(result)
}

//export Close
func Close() *C.char {
	result := api.Close()
	return C.CString(result)
}
