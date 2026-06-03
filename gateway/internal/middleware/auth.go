package middleware

import (
	"bytes"
	"fmt"
	"log"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

// JWTAuth JWT认证中间件 - Gateway唯一的认证点
func JWTAuth(secret string) gin.HandlerFunc {
	return func(c *gin.Context) {
		var tokenString string

		// 优先从 Header 获取 Token
		authHeader := c.GetHeader("Authorization")
		if authHeader != "" {
			// 解析Bearer Token
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) == 2 && parts[0] == "Bearer" {
				tokenString = parts[1]
			}
		}

		// 如果 Header 中没有 token，尝试从查询参数获取（用于 WebSocket）
		if tokenString == "" {
			tokenString = c.Query("token")
		}

		// 如果仍然没有 token，返回错误
		if tokenString == "" {
			c.AbortWithStatusJSON(401, gin.H{"error": "Authorization required"})
			return
		}

		// 解析并验证JWT
		token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
			// 验证签名算法
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
			}
			return []byte(secret), nil
		})

		if err != nil {
			log.Printf("JWT validation error: %v", err)
			c.AbortWithStatusJSON(401, gin.H{"error": "Invalid token"})
			return
		}

		// 提取claims
		claims, ok := token.Claims.(jwt.MapClaims)
		if !ok || !token.Valid {
			c.AbortWithStatusJSON(401, gin.H{"error": "Invalid token claims"})
			return
		}

		// 提取user_id - 这是唯一可信的来源
		userID, ok := claims["user_id"].(string)
		if !ok || userID == "" {
			c.AbortWithStatusJSON(401, gin.H{"error": "Invalid user_id in token"})
			return
		}

		// 设置内部Header - 内部服务只信任这个Header
		// 这是user_id的唯一可信来源
		c.Request.Header.Set("X-User-ID", userID)

		// 可选：提取用户名
		if username, ok := claims["username"].(string); ok {
			c.Request.Header.Set("X-Username", username)
		}

		// 将user_id存入Context，方便后续使用
		c.Set("user_id", userID)

		c.Next()
	}
}

// ResponseSecurity 响应安全校验中间件
func ResponseSecurity() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 获取请求的user_id
		requestUserID := c.GetHeader("X-User-ID")
		requestID := c.GetHeader("X-Request-ID")

		// 创建响应拦截器
		writer := &securityResponseWriter{
			ResponseWriter: c.Writer,
			requestUserID:  requestUserID,
			requestID:      requestID,
			body:           &bytes.Buffer{},
		}
		c.Writer = writer

		c.Next()

		// 校验响应
		responseUserID := c.Writer.Header().Get("X-Response-User-ID")
		if responseUserID != "" && responseUserID != requestUserID {
			// 响应的user_id与请求不匹配，记录安全告警
			log.Printf("SECURITY WARNING: User ID mismatch! Request: %s, Response: %s, RequestID: %s",
				requestUserID, responseUserID, requestID)
			// 注意：此时响应可能已经发送，只能记录告警
		}
	}
}

type securityResponseWriter struct {
	gin.ResponseWriter
	requestUserID string
	requestID     string
	body          *bytes.Buffer
}

func (w *securityResponseWriter) Write(data []byte) (int, error) {
	w.body.Write(data)
	return w.ResponseWriter.Write(data)
}
