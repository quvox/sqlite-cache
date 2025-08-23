.PHONY: build build-lib build-lib-mac build-lib-linux clean test deps fmt vet print-version

# Variables
VERSION?=0.1.0
BINARY_NAME=sqcache
LIB_NAME=sqcachelib
SRC_DIR=src
CACHE_DIR=$(SRC_DIR)/cache
API_DIR=$(SRC_DIR)/api
BUILD_DIR=build
GO_FILES=$(shell find $(SRC_DIR) -name "*.go")
LDFLAGS=-s -w -X main.Version=$(VERSION)

# Default target (cross-platform builds excluded due to CGO complexity)
all: build build-lib build-lib-mac build-lib-linux

# Build all including cross-platform (may fail without proper cross-compilation setup)  
all-cross: all build-lib-linux

# Download dependencies
deps:
	go mod download
	go mod tidy

# Format code
fmt:
	go fmt ./...

# Vet code
vet: deps
	go vet ./...

# Build the command-line binary
build: deps fmt
	@mkdir -p $(BUILD_DIR)
	CGO_ENABLED=1 go build -ldflags="$(LDFLAGS)" -o $(BUILD_DIR)/$(BINARY_NAME) $(SRC_DIR)/main.go $(SRC_DIR)/cmd.go

# Build shared library
build-lib: deps fmt vet
	@mkdir -p $(BUILD_DIR)
	cd $(SRC_DIR) && CGO_ENABLED=1 go build -buildmode=c-shared -ldflags="$(LDFLAGS)" -o ../$(BUILD_DIR)/$(LIB_NAME).$(VERSION).so .

# Build with static linking (no dynamic library dependencies)
build-static: deps fmt vet
	@mkdir -p $(BUILD_DIR)
	CGO_ENABLED=1 go build -ldflags="$(LDFLAGS) -extldflags '-static'" -tags sqlite_omit_load_extension -o $(BUILD_DIR)/$(BINARY_NAME)-static $(SRC_DIR)/main.go $(SRC_DIR)/cmd.go

# Cross-compile for Linux
build-linux: deps fmt vet
	@mkdir -p $(BUILD_DIR)
	GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build -ldflags="$(LDFLAGS)" -o $(BUILD_DIR)/$(BINARY_NAME)-linux $(SRC_DIR)/main.go $(SRC_DIR)/cmd.go

# Build Mac shared library (requires macOS)
build-lib-mac: deps fmt vet
	@mkdir -p $(BUILD_DIR)/mac
	@if [ "$$(uname)" != "Darwin" ]; then \
		echo "Error: Mac library build requires macOS environment"; \
		exit 1; \
	fi
	cd $(SRC_DIR) && GOOS=darwin GOARCH=arm64 CGO_ENABLED=1 go build -buildmode=c-shared -ldflags="$(LDFLAGS)" -o ../$(BUILD_DIR)/mac/$(LIB_NAME).$(VERSION).so .

# Build Linux shared library (requires Linux or cross-compilation environment)
build-lib-linux: deps fmt vet
	@mkdir -p $(BUILD_DIR)/linux
	@echo "Note: Linux cross-compilation from macOS requires proper CGO cross-compilation setup"
	@echo "Consider building on a Linux machine or using Docker for Linux builds"
	cd $(SRC_DIR) && GOOS=linux GOARCH=amd64 CGO_ENABLED=1 go build -buildmode=c-shared -ldflags="$(LDFLAGS)" -o ../$(BUILD_DIR)/linux/$(LIB_NAME).$(VERSION).so .

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR)
	rm -f coverage.out coverage.html

# Run the binary
run: build
	./$(BUILD_DIR)/$(BINARY_NAME)

# Print version
print-version:
	@echo $(VERSION)

# Install the binary to GOPATH/bin
install: build
	go install $(SRC_DIR)/main.go

# Development mode - watch for changes and rebuild
dev:
	@which air > /dev/null || go install github.com/cosmtrek/air@latest
	air

# Docker build
docker-build:
	docker build -t $(BINARY_NAME) .

# Show help
help:
	@echo "Available targets:"
	@echo "  all              - Build binary and shared libraries (default)"
	@echo "  all-cross        - Build all including cross-platform (requires setup)"
	@echo "  deps             - Download and tidy dependencies"
	@echo "  fmt              - Format Go code"
	@echo "  vet              - Run go vet"
	@echo "  build            - Build the command-line binary"
	@echo "  build-lib        - Build the shared library (.so)"
	@echo "  build-lib-mac    - Build shared library for Mac (macOS only)"
	@echo "  build-lib-linux  - Build shared library for Linux (requires setup)"
	@echo "  build-static     - Build binary with static linking"
	@echo "  build-linux      - Cross-compile binary for Linux"
	@echo "  test             - Run tests"
	@echo "  test-coverage    - Run tests with coverage"
	@echo "  clean            - Clean build artifacts"
	@echo "  run              - Build and run the binary"
	@echo "  install          - Install binary to GOPATH/bin"
	@echo "  dev              - Development mode with auto-reload"
	@echo "  docker-build     - Build Docker image"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "Environment variables:"
	@echo "  VERSION          - Set version string (default: 0.1.0)"