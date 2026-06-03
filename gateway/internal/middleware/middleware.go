package middleware

import (
	"log"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/newarch/gateway/internal/config"
	"golang.org/x/time/rate"
)

// Logger 日志中间件
func Logger() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		query := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()
		clientIP := c.ClientIP()
		method := c.Request.Method
		userID := c.GetHeader("X-User-ID")
		requestID := c.GetHeader("X-Request-ID")

		if query != "" {
			path = path + "?" + query
		}

		log.Printf("[%s] %s %s %d %v | user=%s request_id=%s ip=%s",
			method, path, c.Request.Proto, status, latency,
			userID, requestID, clientIP)
	}
}

// RequestID 请求ID中间件
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = uuid.New().String()
		}
		c.Request.Header.Set("X-Request-ID", requestID)
		c.Writer.Header().Set("X-Request-ID", requestID)
		c.Set("request_id", requestID)
		c.Next()
	}
}

// CORS 跨域中间件
func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
		c.Writer.Header().Set("Access-Control-Allow-Credentials", "true")
		c.Writer.Header().Set("Access-Control-Allow-Headers", "Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, accept, origin, Cache-Control, X-Requested-With, X-Request-ID")
		c.Writer.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS, GET, PUT, DELETE, PATCH")
		c.Writer.Header().Set("Access-Control-Expose-Headers", "X-Request-ID, X-Response-User-ID")

		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}

		c.Next()
	}
}

// RateLimit 限流中间件 (基于IP和用户)
func RateLimit(cfg config.RateLimitConfig) gin.HandlerFunc {
	// IP限流器
	ipLimiters := &sync.Map{}
	// 用户限流器
	userLimiters := &sync.Map{}

	getLimiter := func(limiters *sync.Map, key string) *rate.Limiter {
		if limiter, ok := limiters.Load(key); ok {
			return limiter.(*rate.Limiter)
		}
		limiter := rate.NewLimiter(rate.Limit(cfg.RequestsPerSecond), cfg.Burst)
		limiters.Store(key, limiter)
		return limiter
	}

	return func(c *gin.Context) {
		// IP限流
		clientIP := c.ClientIP()
		ipLimiter := getLimiter(ipLimiters, clientIP)
		if !ipLimiter.Allow() {
			c.AbortWithStatusJSON(429, gin.H{
				"error":   "Too many requests",
				"message": "Rate limit exceeded for IP",
			})
			return
		}

		// 用户限流 (如果已认证)
		userID := c.GetHeader("X-User-ID")
		if userID != "" {
			userLimiter := getLimiter(userLimiters, userID)
			if !userLimiter.Allow() {
				c.AbortWithStatusJSON(429, gin.H{
					"error":   "Too many requests",
					"message": "Rate limit exceeded for user",
				})
				return
			}
		}

		c.Next()
	}
}
