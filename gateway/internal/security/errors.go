package security

import "errors"

var (
	// ErrRateLimitExceeded 请求频率超限
	ErrRateLimitExceeded = errors.New("rate limit exceeded")

	// ErrSuspiciousActivity 可疑活动
	ErrSuspiciousActivity = errors.New("suspicious activity detected")

	// ErrUserIDMismatch user_id不匹配
	ErrUserIDMismatch = errors.New("user_id mismatch")

	// ErrUnauthorized 未授权
	ErrUnauthorized = errors.New("unauthorized")

	// ErrForbidden 禁止访问
	ErrForbidden = errors.New("forbidden")
)
