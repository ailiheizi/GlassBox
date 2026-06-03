package grpc

import (
	"context"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"auth-service/internal/service"
	pb "auth-service/proto/auth"
)

// AuthGRPCServer 实现 gRPC AuthService
type AuthGRPCServer struct {
	pb.UnimplementedAuthServiceServer
	authService *service.AuthService
}

// NewAuthGRPCServer 创建 gRPC 服务器
func NewAuthGRPCServer(authService *service.AuthService) *AuthGRPCServer {
	return &AuthGRPCServer{
		authService: authService,
	}
}

// Register 注册到 gRPC 服务器
func (s *AuthGRPCServer) Register(server *grpc.Server) {
	pb.RegisterAuthServiceServer(server, s)
}

// ValidateToken 验证 Token (供 Gateway 调用)
func (s *AuthGRPCServer) ValidateToken(ctx context.Context, req *pb.ValidateTokenRequest) (*pb.ValidateTokenResponse, error) {
	if req.Token == "" {
		return &pb.ValidateTokenResponse{
			Valid: false,
			Error: "token is required",
		}, nil
	}

	// 验证 token
	claims, err := s.authService.ValidateToken(req.Token)
	if err != nil {
		return &pb.ValidateTokenResponse{
			Valid: false,
			Error: err.Error(),
		}, nil
	}

	return &pb.ValidateTokenResponse{
		Valid:     true,
		UserId:    claims.UserID,
		Username:  claims.Username,
		ExpiresAt: claims.ExpiresAt.Unix(),
	}, nil
}

// GetUser 获取用户信息 (供其他服务调用)
func (s *AuthGRPCServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.User, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	user, err := s.authService.GetUserByID(ctx, req.UserId)
	if err != nil {
		return nil, status.Error(codes.NotFound, "user not found")
	}

	return &pb.User{
		Id:        user.ID,
		Username:  user.Username,
		Email:     user.Email,
		CreatedAt: user.CreatedAt.Unix(),
		UpdatedAt: user.UpdatedAt.Unix(),
	}, nil
}

// GetUserByID 通过 ID 获取用户
func (s *AuthGRPCServer) GetUserByID(ctx context.Context, req *pb.GetUserByIDRequest) (*pb.User, error) {
	if req.Id == "" {
		return nil, status.Error(codes.InvalidArgument, "id is required")
	}

	user, err := s.authService.GetUserByID(ctx, req.Id)
	if err != nil {
		return nil, status.Error(codes.NotFound, "user not found")
	}

	return &pb.User{
		Id:        user.ID,
		Username:  user.Username,
		Email:     user.Email,
		CreatedAt: user.CreatedAt.Unix(),
		UpdatedAt: user.UpdatedAt.Unix(),
	}, nil
}

// StartGRPCServer 启动 gRPC 服务器
func StartGRPCServer(addr string, authService *service.AuthService) (*grpc.Server, error) {
	server := grpc.NewServer(
		grpc.UnaryInterceptor(loggingInterceptor),
	)

	authGRPC := NewAuthGRPCServer(authService)
	authGRPC.Register(server)

	return server, nil
}

// loggingInterceptor 日志拦截器
func loggingInterceptor(
	ctx context.Context,
	req interface{},
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (interface{}, error) {
	start := time.Now()

	resp, err := handler(ctx, req)

	// 记录请求日志
	duration := time.Since(start)
	if err != nil {
		// log error
		_ = duration
	}

	return resp, err
}
