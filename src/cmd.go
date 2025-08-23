package main

import (
	"bufio"
	"fmt"
	"os"
	"sqlite-cache/src/api"
	"strings"
)

// Version is set at build time via ldflags
var Version = "dev"

func runCommandLine() {
	if len(os.Args) > 1 {
		// コマンドライン引数がある場合の処理
		switch os.Args[1] {
		case "version":
			fmt.Printf("sqcache v%s\n", Version)
			return
		case "help":
			printHelp()
			return
		default:
			fmt.Fprintf(os.Stderr, "Unknown command: %s\n", os.Args[1])
			os.Exit(1)
		}
	}

	// インタラクティブモードまたはパイプモード
	scanner := bufio.NewScanner(os.Stdin)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		// JSONリクエストをパース
		parts := strings.SplitN(line, " ", 2)
		if len(parts) != 2 {
			fmt.Fprintln(os.Stderr, `{"success": false, "error": "invalid format: expected 'COMMAND JSON'"}`)
			continue
		}

		command := parts[0]
		jsonRequest := parts[1]

		var response string
		switch command {
		case "INIT":
			response = api.Init(jsonRequest)
		case "GET":
			response = api.Get(jsonRequest)
		case "SET":
			response = api.Set(jsonRequest)
		case "DELETE":
			response = api.Delete(jsonRequest)
		case "CLOSE":
			response = api.Close()
		default:
			response = fmt.Sprintf(`{"success": false, "error": "unknown command: %s"}`, command)
		}

		fmt.Println(response)

		if command == "CLOSE" {
			break
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "Error reading input: %v\n", err)
		os.Exit(1)
	}
}

func printHelp() {
	help := `sqcache - SQLite-based cache system

USAGE:
    sqcache [COMMAND]

COMMANDS:
    help     Show this help message
    version  Show version information

INTERACTIVE MODE:
    Run without arguments to enter interactive mode.
    Send commands in the format: COMMAND JSON_REQUEST

    Available commands:
    INIT    {"base_dir": "/path/to/cache", "max_size": 100, "cap": 0.8}
    GET     {"table": "users", "tenant_id": "tenant1", "freshness": 1234567890, "bind": "key1"}
    SET     {"table": "users", "tenant_id": "tenant1", "freshness": 1234567890, "bind": "key1", "content": "data"}
    DELETE  {"table": "users"}
    CLOSE   {}

EXAMPLES:
    echo 'INIT {"base_dir": "./cache", "max_size": 100, "cap": 0.8}' | sqcache
    echo 'GET {"table": "users", "tenant_id": "tenant1", "freshness": 1234567890, "bind": "user123"}' | sqcache
`
	fmt.Print(help)
}
