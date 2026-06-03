package config

import (
	"os"
	"strconv"
)

type Config struct {
	// 服务器配置
	ServerPort  string
	Environment string

	// JWT配置
	JWTSecret string

	// 限流配置
	RateLimit RateLimitConfig

	// 后端服务地址
	AuthServiceURL    string
	BrowserServiceURL string
	MemoryServiceURL  string
	IndexServiceURL   string
	TaskServiceURL    string
	AIServiceURL      string
	WorkerServiceURL  string
}

type RateLimitConfig struct {
	RequestsPerSecond float64
	Burst             int
}

func Load() *Config {
	return &Config{
		ServerPort:  getEnv("SERVER_PORT", "8080"),
		Environment: getEnv("ENVIRONMENT", "development"),
		JWTSecret:   getEnv("JWT_SECRET", "your-super-secret-key-change-in-production"),

		RateLimit: RateLimitConfig{
			RequestsPerSecond: getEnvFloat("RATE_LIMIT_RPS", 100),
			Burst:             getEnvInt("RATE_LIMIT_BURST", 200),
		},

		AuthServiceURL:    getEnv("AUTH_SERVICE_URL", "http://localhost:8081"),
		BrowserServiceURL: getEnv("BROWSER_SERVICE_URL", "http://localhost:8082"),
		MemoryServiceURL:  getEnv("MEMORY_SERVICE_URL", "http://localhost:8083"),
		IndexServiceURL:   getEnv("INDEX_SERVICE_URL", "http://localhost:8084"),
		TaskServiceURL:    getEnv("TASK_SERVICE_URL", "http://localhost:8085"),
		AIServiceURL:      getEnv("AI_SERVICE_URL", "http://localhost:8086"),
		WorkerServiceURL:  getEnv("WORKER_SERVICE_URL", "http://localhost:9000"),
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

func getEnvFloat(key string, defaultValue float64) float64 {
	if value := os.Getenv(key); value != "" {
		if floatValue, err := strconv.ParseFloat(value, 64); err == nil {
			return floatValue
		}
	}
	return defaultValue
}
