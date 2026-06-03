package middleware

import (
	"bufio"
	"bytes"
	"net"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func init() {
	gin.SetMode(gin.TestMode)
}

// generateTestToken 生成测试用的JWT token
func generateTestToken(secret string, userID string, username string, expiry time.Duration) string {
	claims := jwt.MapClaims{
		"user_id":  userID,
		"username": username,
		"exp":      time.Now().Add(expiry).Unix(),
		"iat":      time.Now().Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, _ := token.SignedString([]byte(secret))
	return tokenString
}

func TestJWTAuthMissingHeader(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/test", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401, got %d", w.Code)
	}
}

func TestJWTAuthInvalidFormat(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Test without "Bearer" prefix
	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "invalid-token")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401, got %d", w.Code)
	}
}

func TestJWTAuthInvalidToken(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer invalid-token")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401, got %d", w.Code)
	}
}

func TestJWTAuthExpiredToken(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Generate expired token
	token := generateTestToken(secret, "user123", "testuser", -1*time.Hour)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401 for expired token, got %d", w.Code)
	}
}

func TestJWTAuthWrongSecret(t *testing.T) {
	router := gin.New()
	router.Use(JWTAuth("correct-secret"))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Generate token with different secret
	token := generateTestToken("wrong-secret", "user123", "testuser", 1*time.Hour)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401 for wrong secret, got %d", w.Code)
	}
}

func TestJWTAuthValidToken(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))

	var capturedUserID string
	var capturedUsername string
	router.GET("/test", func(c *gin.Context) {
		capturedUserID = c.GetHeader("X-User-ID")
		capturedUsername = c.GetHeader("X-Username")
		c.JSON(200, gin.H{"status": "ok"})
	})

	token := generateTestToken(secret, "user123", "testuser", 1*time.Hour)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	if capturedUserID != "user123" {
		t.Errorf("Expected X-User-ID 'user123', got '%s'", capturedUserID)
	}

	if capturedUsername != "testuser" {
		t.Errorf("Expected X-Username 'testuser', got '%s'", capturedUsername)
	}
}

func TestJWTAuthMissingUserID(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Generate token without user_id
	claims := jwt.MapClaims{
		"username": "testuser",
		"exp":      time.Now().Add(1 * time.Hour).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, _ := token.SignedString([]byte(secret))

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+tokenString)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401 for missing user_id, got %d", w.Code)
	}
}

func TestJWTAuthEmptyUserID(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))
	router.GET("/test", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "ok"})
	})

	// Generate token with empty user_id
	token := generateTestToken(secret, "", "testuser", 1*time.Hour)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("Expected status 401 for empty user_id, got %d", w.Code)
	}
}

func TestJWTAuthContextUserID(t *testing.T) {
	secret := "test-secret"
	router := gin.New()
	router.Use(JWTAuth(secret))

	var contextUserID string
	router.GET("/test", func(c *gin.Context) {
		if val, exists := c.Get("user_id"); exists {
			contextUserID = val.(string)
		}
		c.JSON(200, gin.H{"status": "ok"})
	})

	token := generateTestToken(secret, "user123", "testuser", 1*time.Hour)

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if contextUserID != "user123" {
		t.Errorf("Expected context user_id 'user123', got '%s'", contextUserID)
	}
}

func TestResponseSecurityMiddleware(t *testing.T) {
	router := gin.New()
	router.Use(ResponseSecurity())
	router.GET("/test", func(c *gin.Context) {
		c.Writer.Header().Set("X-Response-User-ID", c.GetHeader("X-User-ID"))
		c.JSON(200, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("X-User-ID", "user123")
	req.Header.Set("X-Request-ID", "req-001")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}
}

func TestResponseSecurityMismatch(t *testing.T) {
	router := gin.New()
	router.Use(ResponseSecurity())
	router.GET("/test", func(c *gin.Context) {
		// Simulate a mismatch (different user_id in response)
		c.Writer.Header().Set("X-Response-User-ID", "different-user")
		c.JSON(200, gin.H{"status": "ok"})
	})

	req := httptest.NewRequest("GET", "/test", nil)
	req.Header.Set("X-User-ID", "user123")
	req.Header.Set("X-Request-ID", "req-001")
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)

	// Response should still be 200, but a warning should be logged
	// (We can't easily test the log output, but the middleware should not block)
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}
}

func TestSecurityResponseWriter(t *testing.T) {
	gin.SetMode(gin.TestMode)

	w := httptest.NewRecorder()
	srw := &securityResponseWriter{
		ResponseWriter: &responseWriterWrapper{ResponseWriter: w, status: 200},
		requestUserID:  "user123",
		requestID:      "req-001",
		body:           &bytes.Buffer{},
	}

	data := []byte("test data")
	n, err := srw.Write(data)

	if err != nil {
		t.Errorf("Write returned error: %v", err)
	}

	if n != len(data) {
		t.Errorf("Expected to write %d bytes, wrote %d", len(data), n)
	}

	if srw.body.String() != "test data" {
		t.Errorf("Expected body 'test data', got '%s'", srw.body.String())
	}
}

// responseWriterWrapper wraps http.ResponseWriter to implement gin.ResponseWriter
type responseWriterWrapper struct {
	http.ResponseWriter
	status int
	size   int
}

func (w *responseWriterWrapper) Status() int {
	return w.status
}

func (w *responseWriterWrapper) Size() int {
	return w.size
}

func (w *responseWriterWrapper) Written() bool {
	return w.status != 0
}

func (w *responseWriterWrapper) WriteHeader(code int) {
	w.status = code
	w.ResponseWriter.WriteHeader(code)
}

func (w *responseWriterWrapper) WriteHeaderNow() {
	if !w.Written() {
		w.WriteHeader(http.StatusOK)
	}
}

func (w *responseWriterWrapper) Write(data []byte) (int, error) {
	n, err := w.ResponseWriter.Write(data)
	w.size += n
	return n, err
}

func (w *responseWriterWrapper) WriteString(s string) (int, error) {
	return w.Write([]byte(s))
}

func (w *responseWriterWrapper) Pusher() http.Pusher {
	return nil
}

func (w *responseWriterWrapper) Flush() {
	if f, ok := w.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

func (w *responseWriterWrapper) CloseNotify() <-chan bool {
	return make(chan bool)
}

func (w *responseWriterWrapper) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	return nil, nil, nil
}
