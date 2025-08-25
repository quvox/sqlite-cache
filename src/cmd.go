package main

import (
	"bufio"
	"fmt"
	"os"
	"sqlite-cache/src/api"
	"strconv"
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

		// シンプルなテキストコマンドをパース
		parts := strings.Fields(line)
		if len(parts) == 0 {
			fmt.Println("ERROR: empty command")
			continue
		}

		command := strings.ToUpper(parts[0])
		var success bool
		var result string

		switch command {
		case "INIT":
			if len(parts) != 4 {
				fmt.Println("ERROR: INIT requires 3 arguments: base_dir max_size cap")
				continue
			}
			baseDir := parts[1]
			maxSize, err1 := strconv.Atoi(parts[2])
			cap, err2 := strconv.ParseFloat(parts[3], 64)
			if err1 != nil || err2 != nil {
				fmt.Println("ERROR: invalid number format")
				continue
			}
			success = api.Init(baseDir, maxSize, cap)
			result = "initialized"

		case "SET":
			if len(parts) != 6 {
				fmt.Println("ERROR: SET requires 5 arguments: table tenant_id freshness bind content")
				continue
			}
			table, tenantId, freshness, bind, contentStr := parts[1], parts[2], parts[3], parts[4], parts[5]
			content := []byte(contentStr)
			success = api.Set(table, tenantId, freshness, bind, content)
			result = "set"

		case "GET":
			if len(parts) != 5 {
				fmt.Println("ERROR: GET requires 4 arguments: table tenant_id freshness bind")
				continue
			}
			table, tenantId, freshness, bind := parts[1], parts[2], parts[3], parts[4]
			content := api.Get(table, tenantId, freshness, bind)
			if content != nil {
				fmt.Printf("OK: %s\n", string(content))
			} else {
				fmt.Println("MISS: cache not found")
			}
			continue

		case "DELETE":
			if len(parts) != 2 {
				fmt.Println("ERROR: DELETE requires 1 argument: table")
				continue
			}
			table := parts[1]
			success = api.Delete(table)
			result = "deleted"

		case "CLOSE":
			success = api.Close()
			result = "closed"
			if success {
				fmt.Printf("OK: %s\n", result)
			} else {
				fmt.Printf("ERROR: failed to %s\n", result)
			}
			break

		default:
			fmt.Printf("ERROR: unknown command: %s\n", command)
			continue
		}

		if command != "GET" {
			if success {
				fmt.Printf("OK: %s\n", result)
			} else {
				fmt.Printf("ERROR: failed to %s\n", result)
			}
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
    Send simple text commands:

    Available commands:
    INIT base_dir max_size cap
    SET table tenant_id freshness bind content
    GET table tenant_id freshness bind
    DELETE table
    CLOSE

    Responses:
    OK: <result>     - Success
    ERROR: <reason>  - Failure
    MISS: <reason>   - Cache miss

EXAMPLES:
    echo 'INIT ./cache 100 0.8' | sqcache
    echo 'SET users tenant1 fresh1 user123 data' | sqcache
    echo 'GET users tenant1 fresh1 user123' | sqcache
    echo 'DELETE users' | sqcache
    echo 'CLOSE' | sqcache
`
	fmt.Print(help)
}
