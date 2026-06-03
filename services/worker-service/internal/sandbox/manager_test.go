package sandbox

import (
	"testing"
	"time"
)

func TestDefaultConfig(t *testing.T) {
	config := DefaultConfig()

	if config.SandboxImage != "newarch-sandbox:latest" {
		t.Errorf("Expected SandboxImage 'newarch-sandbox:latest', got '%s'", config.SandboxImage)
	}

	if config.MaxSandboxes != 50 {
		t.Errorf("Expected MaxSandboxes 50, got %d", config.MaxSandboxes)
	}

	if config.DefaultCPU != 1.0 {
		t.Errorf("Expected DefaultCPU 1.0, got %f", config.DefaultCPU)
	}

	if config.DefaultMemory != 2*1024*1024*1024 {
		t.Errorf("Expected DefaultMemory 2GB, got %d", config.DefaultMemory)
	}

	if config.IdleTimeout != 30*time.Minute {
		t.Errorf("Expected IdleTimeout 30m, got %v", config.IdleTimeout)
	}

	if config.HostAddress != "localhost" {
		t.Errorf("Expected HostAddress 'localhost', got '%s'", config.HostAddress)
	}
}

func TestTruncateUserID(t *testing.T) {
	tests := []struct {
		userID   string
		maxLen   int
		expected string
	}{
		{"short", 10, "short"},
		{"exactly10c", 10, "exactly10c"},
		{"this-is-a-very-long-user-id", 8, "this-is-"},
		{"", 5, ""},
		{"abc", 3, "abc"},
		{"abcd", 3, "abc"},
	}

	for _, tt := range tests {
		result := truncateUserID(tt.userID, tt.maxLen)
		if result != tt.expected {
			t.Errorf("truncateUserID(%q, %d) = %q, expected %q", tt.userID, tt.maxLen, result, tt.expected)
		}
	}
}

func TestSandboxStatus(t *testing.T) {
	if StatusCreating != "creating" {
		t.Errorf("Expected StatusCreating 'creating', got '%s'", StatusCreating)
	}

	if StatusRunning != "running" {
		t.Errorf("Expected StatusRunning 'running', got '%s'", StatusRunning)
	}

	if StatusStopped != "stopped" {
		t.Errorf("Expected StatusStopped 'stopped', got '%s'", StatusStopped)
	}

	if StatusError != "error" {
		t.Errorf("Expected StatusError 'error', got '%s'", StatusError)
	}
}
