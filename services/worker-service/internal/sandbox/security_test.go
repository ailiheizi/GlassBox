package sandbox

import (
	"testing"
	"time"
)

func TestGenerateRequestSignature(t *testing.T) {
	sm := NewSecurityManager("test-secret-key")

	userID := "user123"
	sandboxID := "sandbox456"
	timestamp := time.Now().Unix()

	signature := sm.GenerateRequestSignature(userID, sandboxID, timestamp)

	if signature == "" {
		t.Error("Expected non-empty signature")
	}

	if len(signature) != 64 { // SHA256 hex = 64 chars
		t.Errorf("Expected signature length 64, got %d", len(signature))
	}
}

func TestVerifyResponse(t *testing.T) {
	sm := NewSecurityManager("test-secret-key")

	userID := "user123"
	sandboxID := "sandbox456"
	timestamp := time.Now().Unix()

	// Generate valid signature
	validSignature := sm.GenerateRequestSignature(userID, sandboxID, timestamp)

	// Test valid signature
	if !sm.VerifyResponse(userID, sandboxID, timestamp, validSignature) {
		t.Error("Expected valid signature to pass verification")
	}

	// Test invalid signature
	invalidSignature := "invalid-signature-12345"
	if sm.VerifyResponse(userID, sandboxID, timestamp, invalidSignature) {
		t.Error("Expected invalid signature to fail verification")
	}
}

func TestVerifyResponseTimestamp(t *testing.T) {
	sm := NewSecurityManager("test-secret-key")

	userID := "user123"
	sandboxID := "sandbox456"

	// Test expired timestamp (10 minutes ago)
	oldTimestamp := time.Now().Add(-10 * time.Minute).Unix()
	oldSignature := sm.GenerateRequestSignature(userID, sandboxID, oldTimestamp)

	if sm.VerifyResponse(userID, sandboxID, oldTimestamp, oldSignature) {
		t.Error("Expected expired timestamp to fail verification")
	}

	// Test future timestamp (10 minutes ahead)
	futureTimestamp := time.Now().Add(10 * time.Minute).Unix()
	futureSignature := sm.GenerateRequestSignature(userID, sandboxID, futureTimestamp)

	if sm.VerifyResponse(userID, sandboxID, futureTimestamp, futureSignature) {
		t.Error("Expected future timestamp to fail verification")
	}
}

func TestVerifyResponseDifferentUser(t *testing.T) {
	sm := NewSecurityManager("test-secret-key")

	userID := "user123"
	sandboxID := "sandbox456"
	timestamp := time.Now().Unix()

	signature := sm.GenerateRequestSignature(userID, sandboxID, timestamp)

	// Try to verify with different user ID
	if sm.VerifyResponse("user999", sandboxID, timestamp, signature) {
		t.Error("Expected different user ID to fail verification")
	}
}
