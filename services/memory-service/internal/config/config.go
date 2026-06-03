package config

import (
	"os"
)

type Config struct {
	ServerPort    string
	Environment   string
	DatabaseURL   string
	MilvusAddress string
	AIServiceURL  string
}

func Load() *Config {
	return &Config{
		ServerPort:    getEnv("SERVER_PORT", "8082"),
		Environment:   getEnv("ENVIRONMENT", "development"),
		DatabaseURL:   getEnv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/newarch?sslmode=disable"),
		MilvusAddress: getEnv("MILVUS_ADDRESS", "localhost:19530"),
		AIServiceURL:  getEnv("AI_SERVICE_URL", "http://localhost:8085"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
