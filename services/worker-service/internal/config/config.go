package config

import (
	"os"
	"strconv"

	"github.com/newarch/worker-service/pkg/types"
)

// Config 配置
type Config struct {
	WorkerID           string
	CoreServiceURL     string
	ListenAddr         string
	JWTSecret          string
	MaxContainers      int
	MaxConcurrentTasks int
	SecurityPolicy     types.SecurityPolicy
}

// Load 加载配置
func Load() *Config {
	return &Config{
		WorkerID:           getEnv("WORKER_ID", "worker-01"),
		CoreServiceURL:     getEnv("CORE_SERVICE_URL", "http://localhost:8080"),
		ListenAddr:         getEnv("LISTEN_ADDR", ":9000"),
		JWTSecret:          getEnv("JWT_SECRET", "your-secret-key"),
		MaxContainers:      getEnvInt("MAX_CONTAINERS", 50),
		MaxConcurrentTasks: getEnvInt("MAX_CONCURRENT_TASKS", 10),
		SecurityPolicy: types.SecurityPolicy{
			AllowedImages: []string{
				"python:3.11-slim",
				"node:18-alpine",
				"golang:1.21-alpine",
				"ubuntu:22.04",
			},
			BlockedPorts:   []int{22, 23, 3389},
			NetworkMode:    getEnv("NETWORK_MODE", "none"),
			ReadOnlyRootFS: getEnvBool("READ_ONLY_ROOT_FS", false),
			CapDrop: []string{
				"NET_RAW",
				"NET_ADMIN",
				"SYS_ADMIN",
				"SYS_MODULE",
			},
		},
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}
