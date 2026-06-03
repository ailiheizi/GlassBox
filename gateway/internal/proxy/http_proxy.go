package proxy

import (
	"bufio"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
)

// 全局 HTTP 客户端，用于 SSE 代理
var sseHTTPClient = &http.Client{
	Timeout: 0, // SSE 不设置超时
	Transport: &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 10,
		IdleConnTimeout:     90 * time.Second,
	},
}

// HTTPProxy HTTP代理
type HTTPProxy struct {
	targetURL *url.URL
	proxy     *httputil.ReverseProxy
}

// NewHTTPProxy 创建HTTP代理
func NewHTTPProxy(target string) *HTTPProxy {
	targetURL, err := url.Parse(target)
	if err != nil {
		log.Fatalf("Invalid proxy target URL: %s", target)
	}

	proxy := httputil.NewSingleHostReverseProxy(targetURL)

	// 自定义Director，保留认证Header
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		// httputil.ReverseProxy默认删除Authorization头
		// 需要手动保留以支持后端服务的JWT认证
		// 注意：Authorization头已经在Gateway的JWTAuth中间件中验证过
	}

	// 错误处理
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		log.Printf("Proxy error: %v", err)
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{"error": "Service unavailable"}`))
	}

	return &HTTPProxy{
		targetURL: targetURL,
		proxy:     proxy,
	}
}

// Handler 返回Gin处理函数
func (p *HTTPProxy) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 更新请求URL
		c.Request.URL.Host = p.targetURL.Host
		c.Request.URL.Scheme = p.targetURL.Scheme
		c.Request.Host = p.targetURL.Host

		// 重写路径：移除 /api/v1/{service} 前缀
		// 例如 /api/v1/auth/register -> /register
		path := c.Request.URL.Path
		parts := strings.Split(path, "/")
		if len(parts) >= 4 && parts[1] == "api" && parts[2] == "v1" {
			// 移除 /api/v1/{service} 前缀，保留后面的路径
			newPath := "/" + strings.Join(parts[4:], "/")
			if newPath == "/" && len(parts) > 4 {
				newPath = "/" + strings.Join(parts[4:], "/")
			}
			c.Request.URL.Path = newPath
		}

		p.proxy.ServeHTTP(c.Writer, c.Request)
	}
}

// SSEProxy SSE流式代理
type SSEProxy struct {
	targetURL string
}

// NewSSEProxy 创建SSE代理
func NewSSEProxy(target string) *SSEProxy {
	return &SSEProxy{targetURL: target}
}

// Handler 返回SSE处理函数
func (p *SSEProxy) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 重写路径：移除 /api/v1/{service} 前缀
		path := c.Request.URL.Path
		parts := strings.Split(path, "/")
		if len(parts) >= 4 && parts[1] == "api" && parts[2] == "v1" {
			// 移除 /api/v1/{service} 前缀，保留后面的路径
			path = "/" + strings.Join(parts[4:], "/")
		}

		// 构建目标URL
		targetURL := p.targetURL + path
		if c.Request.URL.RawQuery != "" {
			targetURL += "?" + c.Request.URL.RawQuery
		}

		// 创建请求
		req, err := http.NewRequestWithContext(c.Request.Context(), c.Request.Method, targetURL, c.Request.Body)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
			return
		}

		// 复制Header
		for key, values := range c.Request.Header {
			for _, value := range values {
				req.Header.Add(key, value)
			}
		}

		// 发送请求（使用全局 HTTP 客户端）
		resp, err := sseHTTPClient.Do(req)
		if err != nil {
			log.Printf("SSE proxy error: %v", err)
			c.JSON(http.StatusBadGateway, gin.H{"error": "Service unavailable"})
			return
		}
		defer resp.Body.Close()

		// 检查是否是SSE响应
		contentType := resp.Header.Get("Content-Type")
		if !strings.Contains(contentType, "text/event-stream") {
			// 非SSE响应，直接转发
			for key, values := range resp.Header {
				for _, value := range values {
					c.Writer.Header().Add(key, value)
				}
			}
			c.Writer.WriteHeader(resp.StatusCode)
			io.Copy(c.Writer, resp.Body)
			return
		}

		// SSE响应
		c.Writer.Header().Set("Content-Type", "text/event-stream")
		c.Writer.Header().Set("Cache-Control", "no-cache")
		c.Writer.Header().Set("Connection", "keep-alive")
		c.Writer.Header().Set("X-Accel-Buffering", "no")

		// 复制响应中的安全Header
		if userID := resp.Header.Get("X-Response-User-ID"); userID != "" {
			c.Writer.Header().Set("X-Response-User-ID", userID)
		}

		c.Writer.WriteHeader(resp.StatusCode)
		c.Writer.Flush()

		// 流式转发
		reader := bufio.NewReader(resp.Body)
		for {
			line, err := reader.ReadBytes('\n')
			if err != nil {
				if err != io.EOF {
					log.Printf("SSE read error: %v", err)
				}
				break
			}

			_, writeErr := c.Writer.Write(line)
			if writeErr != nil {
				log.Printf("SSE write error: %v", writeErr)
				break
			}

			if flusher, ok := c.Writer.(http.Flusher); ok {
				flusher.Flush()
			}
		}
	}
}

// WSProxy WebSocket代理
type WSProxy struct {
	targetURL string
	jwtSecret string
	upgrader  websocket.Upgrader
}

// NewWSProxy 创建WebSocket代理
func NewWSProxy(target string) *WSProxy {
	return &WSProxy{
		targetURL: target,
		jwtSecret: "",
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // 允许所有来源（生产环境应该限制）
			},
		},
	}
}

// NewWSProxyWithAuth 创建带认证的WebSocket代理
func NewWSProxyWithAuth(target string, jwtSecret string) *WSProxy {
	return &WSProxy{
		targetURL: target,
		jwtSecret: jwtSecret,
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // 允许所有来源（生产环境应该限制）
			},
		},
	}
}

// Handler 返回WebSocket处理函数
func (p *WSProxy) Handler() gin.HandlerFunc {
	return func(c *gin.Context) {
		// 如果配置了 JWT secret，则验证 token
		if p.jwtSecret != "" {
			// 1. 从查询参数获取 token
			tokenString := c.Query("token")
			if tokenString == "" {
				c.JSON(401, gin.H{"error": "Token required"})
				return
			}

			// 2. 解析并验证 JWT
			token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
				if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
					return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
				}
				return []byte(p.jwtSecret), nil
			})

			if err != nil {
				log.Printf("JWT validation error: %v", err)
				c.JSON(401, gin.H{"error": "Invalid token"})
				return
			}

			// 3. 提取 claims
			claims, ok := token.Claims.(jwt.MapClaims)
			if !ok || !token.Valid {
				c.JSON(401, gin.H{"error": "Invalid token claims"})
				return
			}

			// 4. 提取 user_id
			userID, ok := claims["user_id"].(string)
			if !ok || userID == "" {
				c.JSON(401, gin.H{"error": "Invalid user_id in token"})
				return
			}

			// 5. 验证 user_id 与 URL 参数匹配
			urlUserID := c.Param("user_id")
			if urlUserID != "" && userID != urlUserID {
				c.JSON(403, gin.H{"error": "User ID mismatch"})
				return
			}

			// 6. 设置内部 Header（用于日志和下游服务）
			c.Request.Header.Set("X-User-ID", userID)
		}

		// 重写路径：移除 /api/v1/{service} 前缀
		path := c.Request.URL.Path
		parts := strings.Split(path, "/")
		if len(parts) >= 4 && parts[1] == "api" && parts[2] == "v1" {
			// 移除 /api/v1/{service} 前缀，保留后面的路径
			path = "/" + strings.Join(parts[4:], "/")
		}

		// 构建目标 WebSocket URL
		targetURL := strings.Replace(p.targetURL, "http://", "ws://", 1)
		targetURL = strings.Replace(targetURL, "https://", "wss://", 1)
		targetURL += path
		if c.Request.URL.RawQuery != "" {
			targetURL += "?" + c.Request.URL.RawQuery
		}

		// 升级客户端连接为 WebSocket
		clientConn, err := p.upgrader.Upgrade(c.Writer, c.Request, nil)
		if err != nil {
			log.Printf("Failed to upgrade client connection: %v", err)
			return
		}
		defer clientConn.Close()

		// 连接到上游 WebSocket
		upstreamConn, _, err := websocket.DefaultDialer.Dial(targetURL, nil)
		if err != nil {
			log.Printf("Failed to connect to upstream WebSocket: %v", err)
			clientConn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseInternalServerErr, "Failed to connect to upstream"))
			return
		}
		defer upstreamConn.Close()

		// 双向中继消息
		errChan := make(chan error, 2)

		// 客户端 -> 上游
		go func() {
			for {
				messageType, message, err := clientConn.ReadMessage()
				if err != nil {
					errChan <- err
					return
				}
				if err := upstreamConn.WriteMessage(messageType, message); err != nil {
					errChan <- err
					return
				}
			}
		}()

		// 上游 -> 客户端
		go func() {
			for {
				messageType, message, err := upstreamConn.ReadMessage()
				if err != nil {
					errChan <- err
					return
				}
				if err := clientConn.WriteMessage(messageType, message); err != nil {
					errChan <- err
					return
				}
			}
		}()

		// 等待任一方向出错
		<-errChan
	}
}

