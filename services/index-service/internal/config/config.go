package config

import (
	"os"

	"github.com/joho/godotenv"
)

// Config 配置
type Config struct {
	ServerPort        string
	DatabaseURL       string
	BrowserServiceURL string
}

// Load 加载配置
func Load() *Config {
	_ = godotenv.Load()

	return &Config{
		ServerPort:        getEnv("SERVER_PORT", "8083"),
		DatabaseURL:       getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/newarch?sslmode=disable"),
		BrowserServiceURL: getEnv("BROWSER_SERVICE_URL", "http://localhost:8084"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
