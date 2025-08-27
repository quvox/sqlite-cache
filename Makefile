.PHONY: build build-lib build-lib-mac build-lib-linux-musl build-linux-musl clean test deps fmt vet print-version help

# Variables
VERSION?=0.4.0
BINARY_NAME=sqcache
LIB_NAME=sqcachelib
SRC_DIR=src
CACHE_DIR=$(SRC_DIR)/cache
API_DIR=$(SRC_DIR)/api
BUILD_DIR=build
GO_FILES=$(shell find $(SRC_DIR) -name "*.go")
LDFLAGS=-s -w -X main.Version=$(VERSION)

# Default target
all: build build-lib build-lib-mac build-lib-linux-all

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


# Build Mac shared library (requires macOS)
build-lib-mac: deps fmt vet
	@mkdir -p $(BUILD_DIR)/mac
	@if [ "$$(uname)" != "Darwin" ]; then \
		echo "Error: Mac library build requires macOS environment"; \
		exit 1; \
	fi
	cd $(SRC_DIR) && GOOS=darwin GOARCH=arm64 CGO_ENABLED=1 go build -buildmode=c-shared -ldflags="$(LDFLAGS)" -o ../$(BUILD_DIR)/mac/$(LIB_NAME).$(VERSION).so .

# Build Linux binary with Zig CC and musl (no GLIBC dependency)
build-linux-musl: deps fmt vet
	@mkdir -p $(BUILD_DIR)/linux
	@echo "Building Linux binary with Zig CC and musl"
	@which zig > /dev/null || (echo "Error: zig not found. Please install Zig."; exit 1)
	GOOS=linux GOARCH=amd64 CGO_ENABLED=1 \
	CC="zig cc -target x86_64-linux-musl -D_LARGEFILE64_SOURCE=0 -DSQLITE_DISABLE_LFS" \
	CXX="zig c++ -target x86_64-linux-musl -D_LARGEFILE64_SOURCE=0 -DSQLITE_DISABLE_LFS" \
	go build \
		-ldflags="$(LDFLAGS) -linkmode external -extldflags '-static'" \
		-tags 'sqlite_omit_load_extension netgo osusergo sqlite_disable_fts4_unicode' \
		-o $(BUILD_DIR)/linux/$(BINARY_NAME) \
		$(SRC_DIR)/main.go $(SRC_DIR)/cmd.go

# Build Linux shared library with Zig CC and musl
build-lib-linux-musl: deps fmt vet
	@mkdir -p $(BUILD_DIR)/linux
	@echo "Building Linux shared library with Zig CC and musl"
	@which zig > /dev/null || (echo "Error: zig not found. Please install Zig."; exit 1)
	cd $(SRC_DIR) && GOOS=linux GOARCH=amd64 CGO_ENABLED=1 \
	CC="zig cc -target x86_64-linux-gnu" \
	CXX="zig c++ -target x86_64-linux-gnu" \
	go build \
		-buildmode=c-shared \
		-ldflags="$(LDFLAGS)" \
		-tags 'sqlite_omit_load_extension' \
		-o ../$(BUILD_DIR)/linux/$(LIB_NAME).$(VERSION).so .

# Build Linux ARM64 shared library with Zig CC and musl
build-lib-linux-arm64-musl: deps fmt vet
	@mkdir -p $(BUILD_DIR)/linux
	@echo "Building Linux ARM64 shared library with Zig CC and musl"
	@which zig > /dev/null || (echo "Error: zig not found. Please install Zig."; exit 1)
	cd $(SRC_DIR) && GOOS=linux GOARCH=arm64 CGO_ENABLED=1 \
	CC="zig cc -target aarch64-linux-gnu" \
	CXX="zig c++ -target aarch64-linux-gnu" \
	go build \
		-buildmode=c-shared \
		-ldflags="$(LDFLAGS)" \
		-tags 'sqlite_omit_load_extension' \
		-o ../$(BUILD_DIR)/linux/$(LIB_NAME).$(VERSION).arm64.so .

# Build both Linux architectures
build-lib-linux-all: build-lib-linux-musl build-lib-linux-arm64-musl

# Build in Amazon Linux 2 Docker container for Lambda compatibility
build-lib-lambda: deps fmt vet
	@echo "Building shared library in Amazon Linux 2 Docker container for Lambda"
	@mkdir -p $(BUILD_DIR)/lambda
	docker run --rm --platform=linux/amd64 \
		-v $(PWD):/workspace \
		-w /workspace \
		amazonlinux:2 \
		bash -c '\
			yum update -y && \
			yum install -y gcc git wget tar && \
			if [ ! -f go1.23.4.linux-amd64.tar.gz ]; then \
				wget -q https://go.dev/dl/go1.23.4.linux-amd64.tar.gz; \
			fi && \
			tar -C /usr/local -xzf go1.23.4.linux-amd64.tar.gz && \
			export PATH=/usr/local/go/bin:$$PATH && \
			export CGO_ENABLED=1 && \
			export GOOS=linux && \
			export GOARCH=amd64 && \
			cd src && \
			go mod download && \
			go build \
				-buildmode=c-shared \
				-ldflags="$(LDFLAGS)" \
				-buildvcs=false \
				-tags "sqlite_omit_load_extension" \
				-o ../$(BUILD_DIR)/lambda/$(LIB_NAME).$(VERSION).so . \
		'

# Build Lambda ARM64 version
build-lib-lambda-arm64: deps fmt vet
	@echo "Building ARM64 shared library in Amazon Linux 2 Docker container for Lambda"
	@mkdir -p $(BUILD_DIR)/lambda
	docker run --rm --platform=linux/arm64 \
		-v $(PWD):/workspace \
		-w /workspace \
		amazonlinux:2 \
		bash -c '\
			yum update -y && \
			yum install -y gcc git wget tar && \
			if [ ! -f go1.23.4.linux-arm64.tar.gz ]; then \
				wget -q https://go.dev/dl/go1.23.4.linux-arm64.tar.gz; \
			fi && \
			tar -C /usr/local -xzf go1.23.4.linux-arm64.tar.gz && \
			export PATH=/usr/local/go/bin:$$PATH && \
			export CGO_ENABLED=1 && \
			export GOOS=linux && \
			export GOARCH=arm64 && \
			cd src && \
			go mod download && \
			go build \
				-buildmode=c-shared \
				-ldflags="$(LDFLAGS)" \
				-buildvcs=false \
				-tags "sqlite_omit_load_extension" \
				-o ../$(BUILD_DIR)/lambda/$(LIB_NAME).$(VERSION).arm64.so . \
		'

# Build both Lambda architectures
build-lib-lambda-all: build-lib-lambda build-lib-lambda-arm64

# Run Python tests
test: build-lib
	@echo "Running Python integration tests..."
	@echo "Testing all Python scripts in examples/ with VERSION=$(VERSION)"
	@for script in examples/*.py; do \
		if [ -f "$$script" ]; then \
			echo "Running $$script..."; \
			VERSION=$(VERSION) python3 "$$script" || exit 1; \
			echo "✓ $$script passed"; \
		fi; \
	done
	@echo "All Python tests passed!"

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


# Show help
help:
	@echo "Available targets:"
	@echo "  all              - Build binary and shared libraries (default)"
	@echo "  deps                    - Download and tidy dependencies"
	@echo "  fmt                     - Format Go code"
	@echo "  vet                     - Run go vet"
	@echo "  build                   - Build the command-line binary"
	@echo "  build-lib               - Build the shared library (.so)"
	@echo "  build-lib-mac           - Build shared library for Mac (macOS only)"
	@echo "  build-lib-linux-musl    - Build Linux shared library with Zig CC and musl"
	@echo "  build-linux-musl        - Build Linux binary with Zig CC and musl"
	@echo "  test                    - Run tests"
	@echo "  clean                   - Clean build artifacts"
	@echo "  run                     - Build and run the binary"
	@echo "  install                 - Install binary to GOPATH/bin"
	@echo "  dev                     - Development mode with auto-reload"
	@echo "  help                - Show this help message"
	@echo ""
	@echo "Environment variables:"
	@echo "  VERSION          - Set version string (default: 0.1.0)"