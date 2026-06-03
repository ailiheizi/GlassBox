package security

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

// ResponseSecurityMiddleware 响应安全校验中间件
func ResponseSecurityMiddleware(auditLogger *AuditLogger) gin.HandlerFunc {
	return func(c *gin.Context) {
		requestUserID := c.GetHeader("X-User-ID")
		requestID := c.GetHeader("X-Request-ID")

		// 创建响应拦截器
		responseWriter := &SecurityResponseWriter{
			ResponseWriter: c.Writer,
			requestUserID:  requestUserID,
			requestID:      requestID,
			auditLogger:    auditLogger,
			body:           &bytes.Buffer{},
		}
		c.Writer = responseWriter

		c.Next()

		// 校验响应
		if err := responseWriter.Validate(c.Request.Context()); err != nil {
			log.Printf("[SECURITY] Response validation failed: request_id=%s, user_id=%s, error=%v",
				requestID, requestUserID, err)
		}
	}
}

// SecurityResponseWriter 安全响应写入器
type SecurityResponseWriter struct {
	gin.ResponseWriter
	requestUserID string
	requestID     string
	auditLogger   *AuditLogger
	body          *bytes.Buffer
	statusCode    int
}

func (w *SecurityResponseWriter) Write(data []byte) (int, error) {
	w.body.Write(data)
	return w.ResponseWriter.Write(data)
}

func (w *SecurityResponseWriter) WriteHeader(code int) {
	w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}

// Validate 校验响应
func (w *SecurityResponseWriter) Validate(ctx interface{}) error {
	// 1. 检查响应Header中的user_id是否匹配
	responseUserID := w.Header().Get("X-Response-User-ID")
	if responseUserID != "" && responseUserID != w.requestUserID {
		if w.auditLogger != nil {
			// 使用 context.Background() 因为原始 context 可能已经取消
			w.auditLogger.LogResponseMismatch(nil, w.requestUserID, responseUserID, w.requestID)
		}
		log.Printf("[SECURITY] User ID mismatch in response: request=%s, response=%s",
			w.requestUserID, responseUserID)
	}

	// 2. 检查响应体中是否包含敏感信息 (仅对JSON响应)
	contentType := w.Header().Get("Content-Type")
	if strings.Contains(contentType, "application/json") {
		w.checkJSONResponse()
	}

	return nil
}

// checkJSONResponse 检查JSON响应中的敏感信息
func (w *SecurityResponseWriter) checkJSONResponse() {
	var data map[string]interface{}
	if err := json.Unmarshal(w.body.Bytes(), &data); err != nil {
		return // 不是有效的JSON，跳过检查
	}

	// 检查是否包含其他用户的数据
	w.checkUserIDInData(data, "")
}

// checkUserIDInData 递归检查数据中的user_id
func (w *SecurityResponseWriter) checkUserIDInData(data interface{}, path string) {
	switch v := data.(type) {
	case map[string]interface{}:
		for key, value := range v {
			currentPath := path + "." + key
			if key == "user_id" || key == "userId" || key == "UserID" {
				if strVal, ok := value.(string); ok {
					if strVal != "" && strVal != w.requestUserID {
						log.Printf("[SECURITY] Found different user_id in response: path=%s, request_user=%s, found_user=%s",
							currentPath, w.requestUserID, strVal)
					}
				}
			}
			w.checkUserIDInData(value, currentPath)
		}
	case []interface{}:
		for i, item := range v {
			w.checkUserIDInData(item, path+"["+string(rune(i))+"]")
		}
	}
}

// SanitizeResponseMiddleware 响应数据清理中间件
func SanitizeResponseMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next()
	}
}

// ProxyResponseValidator 代理响应校验器
type ProxyResponseValidator struct {
	requestUserID string
	requestID     string
	auditLogger   *AuditLogger
}

// NewProxyResponseValidator 创建代理响应校验器
func NewProxyResponseValidator(requestUserID, requestID string, auditLogger *AuditLogger) *ProxyResponseValidator {
	return &ProxyResponseValidator{
		requestUserID: requestUserID,
		requestID:     requestID,
		auditLogger:   auditLogger,
	}
}

// ValidateResponse 校验代理响应
func (v *ProxyResponseValidator) ValidateResponse(resp *http.Response) error {
	// 检查响应Header
	responseUserID := resp.Header.Get("X-Response-User-ID")
	if responseUserID != "" && responseUserID != v.requestUserID {
		if v.auditLogger != nil {
			v.auditLogger.LogResponseMismatch(nil, v.requestUserID, responseUserID, v.requestID)
		}
		log.Printf("[SECURITY] Proxy response user_id mismatch: request=%s, response=%s",
			v.requestUserID, responseUserID)
	}

	return nil
}

// ValidateSSEEvent 校验SSE事件
func (v *ProxyResponseValidator) ValidateSSEEvent(event []byte) error {
	// 解析SSE事件数据
	if !bytes.HasPrefix(event, []byte("data: ")) {
		return nil
	}

	data := bytes.TrimPrefix(event, []byte("data: "))
	data = bytes.TrimSpace(data)

	if len(data) == 0 || bytes.Equal(data, []byte("[DONE]")) {
		return nil
	}

	var eventData map[string]interface{}
	if err := json.Unmarshal(data, &eventData); err != nil {
		return nil // 不是JSON，跳过
	}

	// 检查事件中的user_id
	if security, ok := eventData["_security"].(map[string]interface{}); ok {
		if userID, ok := security["user_id"].(string); ok {
			if userID != v.requestUserID {
				log.Printf("[SECURITY] SSE event user_id mismatch: request=%s, event=%s",
					v.requestUserID, userID)
			}
		}
	}

	return nil
}

// SecureProxyTransport 安全代理传输
type SecureProxyTransport struct {
	Transport   http.RoundTripper
	AuditLogger *AuditLogger
}

// RoundTrip 执行请求并校验响应
func (t *SecureProxyTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	resp, err := t.Transport.RoundTrip(req)
	if err != nil {
		return nil, err
	}

	// 校验响应
	requestUserID := req.Header.Get("X-User-ID")
	requestID := req.Header.Get("X-Request-ID")

	validator := NewProxyResponseValidator(requestUserID, requestID, t.AuditLogger)
	validator.ValidateResponse(resp)

	return resp, nil
}

// FilterSensitiveData 过滤敏感数据
func FilterSensitiveData(data []byte, requestUserID string) []byte {
	var jsonData map[string]interface{}
	if err := json.Unmarshal(data, &jsonData); err != nil {
		return data
	}

	filtered := filterSensitiveFields(jsonData, requestUserID)
	result, err := json.Marshal(filtered)
	if err != nil {
		return data
	}
	return result
}

// filterSensitiveFields 递归过滤敏感字段
func filterSensitiveFields(data interface{}, requestUserID string) interface{} {
	switch v := data.(type) {
	case map[string]interface{}:
		result := make(map[string]interface{})
		for key, value := range v {
			// 过滤敏感字段
			if isSensitiveField(key) {
				continue
			}
			// 过滤其他用户的user_id
			if (key == "user_id" || key == "userId") && value != requestUserID {
				continue
			}
			result[key] = filterSensitiveFields(value, requestUserID)
		}
		return result
	case []interface{}:
		result := make([]interface{}, len(v))
		for i, item := range v {
			result[i] = filterSensitiveFields(item, requestUserID)
		}
		return result
	default:
		return v
	}
}

// isSensitiveField 判断是否为敏感字段
func isSensitiveField(field string) bool {
	sensitiveFields := []string{
		"password", "password_hash", "secret", "token",
		"api_key", "apiKey", "private_key", "privateKey",
		"access_token", "accessToken", "refresh_token", "refreshToken",
	}
	fieldLower := strings.ToLower(field)
	for _, sensitive := range sensitiveFields {
		if strings.Contains(fieldLower, strings.ToLower(sensitive)) {
			return true
		}
	}
	return false
}

// CopyResponseBody 复制响应体用于检查
func CopyResponseBody(resp *http.Response) ([]byte, error) {
	if resp.Body == nil {
		return nil, nil
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	// 重新设置响应体
	resp.Body = io.NopCloser(bytes.NewBuffer(body))
	return body, nil
}
