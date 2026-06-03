package service

import (
	"context"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/newarch/auth-service/internal/domain"
)

// MockUserRepository 模拟用户仓库
type MockUserRepository struct {
	users    map[string]*domain.User
	byEmail  map[string]*domain.User
	byID     map[uuid.UUID]*domain.User
	createFn func(ctx context.Context, user *domain.User) error
}

func NewMockUserRepository() *MockUserRepository {
	return &MockUserRepository{
		users:   make(map[string]*domain.User),
		byEmail: make(map[string]*domain.User),
		byID:    make(map[uuid.UUID]*domain.User),
	}
}

func (m *MockUserRepository) Create(ctx context.Context, user *domain.User) error {
	if m.createFn != nil {
		return m.createFn(ctx, user)
	}
	user.ID = uuid.New()
	user.CreatedAt = time.Now()
	user.UpdatedAt = time.Now()
	m.users[user.Username] = user
	m.byEmail[user.Email] = user
	m.byID[user.ID] = user
	return nil
}

func (m *MockUserRepository) GetByUsername(ctx context.Context, username string) (*domain.User, error) {
	if user, ok := m.users[username]; ok {
		return user, nil
	}
	return nil, ErrUserNotFound
}

func (m *MockUserRepository) GetByEmail(ctx context.Context, email string) (*domain.User, error) {
	if user, ok := m.byEmail[email]; ok {
		return user, nil
	}
	return nil, ErrUserNotFound
}

func (m *MockUserRepository) GetByID(ctx context.Context, id uuid.UUID) (*domain.User, error) {
	if user, ok := m.byID[id]; ok {
		return user, nil
	}
	return nil, ErrUserNotFound
}

func (m *MockUserRepository) Update(ctx context.Context, user *domain.User) error {
	if _, ok := m.byID[user.ID]; !ok {
		return ErrUserNotFound
	}
	user.UpdatedAt = time.Now()
	m.users[user.Username] = user
	m.byEmail[user.Email] = user
	m.byID[user.ID] = user
	return nil
}

func (m *MockUserRepository) Delete(ctx context.Context, id uuid.UUID) error {
	if user, ok := m.byID[id]; ok {
		delete(m.users, user.Username)
		delete(m.byEmail, user.Email)
		delete(m.byID, id)
		return nil
	}
	return ErrUserNotFound
}

func TestNewAuthService(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)

	if svc == nil {
		t.Fatal("Expected non-nil AuthService")
	}
}

func TestRegister(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Test successful registration
	user, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Register failed: %v", err)
	}

	if user.Username != "testuser" {
		t.Errorf("Expected username 'testuser', got '%s'", user.Username)
	}

	if user.Email != "test@example.com" {
		t.Errorf("Expected email 'test@example.com', got '%s'", user.Email)
	}

	if user.PasswordHash == "" {
		t.Error("Expected non-empty password hash")
	}

	if user.PasswordHash == "password123" {
		t.Error("Password should be hashed, not stored in plain text")
	}
}

func TestRegisterDuplicateUsername(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register first user
	_, err := svc.Register(ctx, "testuser", "test1@example.com", "password123")
	if err != nil {
		t.Fatalf("First registration failed: %v", err)
	}

	// Try to register with same username
	_, err = svc.Register(ctx, "testuser", "test2@example.com", "password456")
	if err != ErrUserAlreadyExists {
		t.Errorf("Expected ErrUserAlreadyExists, got %v", err)
	}
}

func TestRegisterDuplicateEmail(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register first user
	_, err := svc.Register(ctx, "testuser1", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("First registration failed: %v", err)
	}

	// Try to register with same email
	_, err = svc.Register(ctx, "testuser2", "test@example.com", "password456")
	if err != ErrUserAlreadyExists {
		t.Errorf("Expected ErrUserAlreadyExists, got %v", err)
	}
}

func TestLogin(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register user first
	_, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	// Test successful login
	token, user, err := svc.Login(ctx, "testuser", "password123")
	if err != nil {
		t.Fatalf("Login failed: %v", err)
	}

	if token == "" {
		t.Error("Expected non-empty token")
	}

	if user.Username != "testuser" {
		t.Errorf("Expected username 'testuser', got '%s'", user.Username)
	}
}

func TestLoginInvalidUsername(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Try to login with non-existent user
	_, _, err := svc.Login(ctx, "nonexistent", "password123")
	if err != ErrInvalidCredentials {
		t.Errorf("Expected ErrInvalidCredentials, got %v", err)
	}
}

func TestLoginInvalidPassword(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register user first
	_, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	// Try to login with wrong password
	_, _, err = svc.Login(ctx, "testuser", "wrongpassword")
	if err != ErrInvalidCredentials {
		t.Errorf("Expected ErrInvalidCredentials, got %v", err)
	}
}

func TestValidateToken(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register and login to get a token
	_, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	token, _, err := svc.Login(ctx, "testuser", "password123")
	if err != nil {
		t.Fatalf("Login failed: %v", err)
	}

	// Validate the token
	claims, err := svc.ValidateToken(token)
	if err != nil {
		t.Fatalf("ValidateToken failed: %v", err)
	}

	if claims.Username != "testuser" {
		t.Errorf("Expected username 'testuser', got '%s'", claims.Username)
	}
}

func TestValidateInvalidToken(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)

	// Try to validate an invalid token
	_, err := svc.ValidateToken("invalid-token")
	if err != ErrInvalidToken {
		t.Errorf("Expected ErrInvalidToken, got %v", err)
	}
}

func TestValidateTokenWithWrongSecret(t *testing.T) {
	repo := NewMockUserRepository()
	svc1 := NewAuthService(repo, "secret1", 24*time.Hour)
	svc2 := NewAuthService(repo, "secret2", 24*time.Hour)
	ctx := context.Background()

	// Register and login with svc1
	_, err := svc1.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	token, _, err := svc1.Login(ctx, "testuser", "password123")
	if err != nil {
		t.Fatalf("Login failed: %v", err)
	}

	// Try to validate with svc2 (different secret)
	_, err = svc2.ValidateToken(token)
	if err != ErrInvalidToken {
		t.Errorf("Expected ErrInvalidToken, got %v", err)
	}
}

func TestRefreshToken(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register and login to get a token
	_, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	token, _, err := svc.Login(ctx, "testuser", "password123")
	if err != nil {
		t.Fatalf("Login failed: %v", err)
	}

	// Refresh the token
	newToken, err := svc.RefreshToken(ctx, token)
	if err != nil {
		t.Fatalf("RefreshToken failed: %v", err)
	}

	if newToken == "" {
		t.Error("Expected non-empty new token")
	}

	// Validate the new token
	claims, err := svc.ValidateToken(newToken)
	if err != nil {
		t.Fatalf("ValidateToken failed: %v", err)
	}

	if claims.Username != "testuser" {
		t.Errorf("Expected username 'testuser', got '%s'", claims.Username)
	}
}

func TestRefreshInvalidToken(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Try to refresh an invalid token
	_, err := svc.RefreshToken(ctx, "invalid-token")
	if err != ErrInvalidToken {
		t.Errorf("Expected ErrInvalidToken, got %v", err)
	}
}

func TestGetUserByID(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register user
	user, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	// Get user by ID
	foundUser, err := svc.GetUserByID(ctx, user.ID)
	if err != nil {
		t.Fatalf("GetUserByID failed: %v", err)
	}

	if foundUser.Username != "testuser" {
		t.Errorf("Expected username 'testuser', got '%s'", foundUser.Username)
	}
}

func TestGetUserByIDNotFound(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Try to get non-existent user
	_, err := svc.GetUserByID(ctx, uuid.New())
	if err != ErrUserNotFound {
		t.Errorf("Expected ErrUserNotFound, got %v", err)
	}
}

func TestUpdateUser(t *testing.T) {
	repo := NewMockUserRepository()
	svc := NewAuthService(repo, "test-secret", 24*time.Hour)
	ctx := context.Background()

	// Register user
	user, err := svc.Register(ctx, "testuser", "test@example.com", "password123")
	if err != nil {
		t.Fatalf("Registration failed: %v", err)
	}

	// Update user email
	user.Email = "newemail@example.com"
	err = svc.UpdateUser(ctx, user)
	if err != nil {
		t.Fatalf("UpdateUser failed: %v", err)
	}

	// Verify update
	updatedUser, err := svc.GetUserByID(ctx, user.ID)
	if err != nil {
		t.Fatalf("GetUserByID failed: %v", err)
	}

	if updatedUser.Email != "newemail@example.com" {
		t.Errorf("Expected email 'newemail@example.com', got '%s'", updatedUser.Email)
	}
}
