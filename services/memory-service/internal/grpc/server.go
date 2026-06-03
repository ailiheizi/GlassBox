package grpc

import (
	"context"
	"encoding/json"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"memory-service/internal/service"
	pb "memory-service/proto/memory"
	pbcommon "memory-service/proto/common"
)

// MemoryGRPCServer 实现 gRPC MemoryService
type MemoryGRPCServer struct {
	pb.UnimplementedMemoryServiceServer
	memoryService *service.MemoryService
}

// NewMemoryGRPCServer 创建 gRPC 服务器
func NewMemoryGRPCServer(memoryService *service.MemoryService) *MemoryGRPCServer {
	return &MemoryGRPCServer{
		memoryService: memoryService,
	}
}

// Register 注册到 gRPC 服务器
func (s *MemoryGRPCServer) Register(server *grpc.Server) {
	pb.RegisterMemoryServiceServer(server, s)
}

// SaveMemory 保存语义记忆
func (s *MemoryGRPCServer) SaveMemory(ctx context.Context, req *pb.SaveMemoryRequest) (*pb.SaveMemoryResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.Content == "" {
		return nil, status.Error(codes.InvalidArgument, "content is required")
	}

	// 解析 metadata
	var metadata map[string]interface{}
	if req.Metadata != "" {
		if err := json.Unmarshal([]byte(req.Metadata), &metadata); err != nil {
			return nil, status.Error(codes.InvalidArgument, "invalid metadata JSON")
		}
	}

	id, err := s.memoryService.SaveSemanticMemory(ctx, service.SaveMemoryInput{
		UserID:      req.UserId,
		SessionID:   req.SessionId,
		Content:     req.Content,
		ContentType: req.ContentType,
		SourceURL:   req.SourceUrl,
		PageTitle:   req.PageTitle,
		Metadata:    metadata,
	})

	if err != nil {
		return &pb.SaveMemoryResponse{
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	return &pb.SaveMemoryResponse{
		Id:      id,
		Success: true,
	}, nil
}

// SearchMemories 搜索语义记忆
func (s *MemoryGRPCServer) SearchMemories(ctx context.Context, req *pb.SearchMemoriesRequest) (*pb.SearchMemoriesResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.Query == "" {
		return nil, status.Error(codes.InvalidArgument, "query is required")
	}

	limit := int(req.Limit)
	if limit <= 0 {
		limit = 10
	}

	memories, err := s.memoryService.SearchMemories(ctx, req.UserId, req.Query, limit)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	pbMemories := make([]*pb.SemanticMemory, len(memories))
	for i, m := range memories {
		metadataJSON, _ := json.Marshal(m.Metadata)
		pbMemories[i] = &pb.SemanticMemory{
			Id:              m.ID,
			UserId:          m.UserID,
			SessionId:       m.SessionID,
			Content:         m.Content,
			ContentType:     m.ContentType,
			SourceUrl:       m.SourceURL,
			PageTitle:       m.PageTitle,
			Metadata:        string(metadataJSON),
			IsActive:        m.IsActive,
			CreatedAt:       m.CreatedAt.Unix(),
			SimilarityScore: m.SimilarityScore,
		}
	}

	return &pb.SearchMemoriesResponse{
		Memories: pbMemories,
	}, nil
}

// GetRecentMemories 获取最近记忆
func (s *MemoryGRPCServer) GetRecentMemories(ctx context.Context, req *pb.GetRecentMemoriesRequest) (*pb.GetRecentMemoriesResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	limit := int(req.Limit)
	if limit <= 0 {
		limit = 20
	}

	memories, err := s.memoryService.GetRecentMemories(ctx, req.UserId, req.SessionId, limit)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	pbMemories := make([]*pb.SemanticMemory, len(memories))
	for i, m := range memories {
		metadataJSON, _ := json.Marshal(m.Metadata)
		pbMemories[i] = &pb.SemanticMemory{
			Id:          m.ID,
			UserId:      m.UserID,
			SessionId:   m.SessionID,
			Content:     m.Content,
			ContentType: m.ContentType,
			SourceUrl:   m.SourceURL,
			PageTitle:   m.PageTitle,
			Metadata:    string(metadataJSON),
			IsActive:    m.IsActive,
			CreatedAt:   m.CreatedAt.Unix(),
		}
	}

	return &pb.GetRecentMemoriesResponse{
		Memories: pbMemories,
	}, nil
}

// DeleteMemory 删除记忆
func (s *MemoryGRPCServer) DeleteMemory(ctx context.Context, req *pb.DeleteMemoryRequest) (*pbcommon.Status, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	err := s.memoryService.DeleteMemory(ctx, req.Id, req.UserId)
	if err != nil {
		return &pbcommon.Status{
			Success: false,
			Message: err.Error(),
		}, nil
	}

	return &pbcommon.Status{
		Success: true,
		Message: "deleted",
	}, nil
}

// CreateZone 创建记忆区域
func (s *MemoryGRPCServer) CreateZone(ctx context.Context, req *pb.CreateZoneRequest) (*pb.MemoryZone, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.ZoneId == "" {
		return nil, status.Error(codes.InvalidArgument, "zone_id is required")
	}

	zone, err := s.memoryService.CreateZone(ctx, service.CreateZoneInput{
		UserID:      req.UserId,
		SessionID:   req.SessionId,
		ZoneID:      req.ZoneId,
		Description: req.Description,
		ZoneType:    req.ZoneType,
	})

	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	return &pb.MemoryZone{
		Id:          zone.ID,
		ZoneId:      zone.ZoneID,
		UserId:      zone.UserID,
		SessionId:   zone.SessionID,
		Description: zone.Description,
		ZoneType:    zone.ZoneType,
		IsActive:    zone.IsActive,
		CreatedAt:   zone.CreatedAt.Unix(),
	}, nil
}

// ListZones 获取区域列表
func (s *MemoryGRPCServer) ListZones(ctx context.Context, req *pb.ListZonesRequest) (*pb.ListZonesResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}

	zones, err := s.memoryService.ListZones(ctx, req.UserId, req.SessionId)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	pbZones := make([]*pb.MemoryZone, len(zones))
	for i, z := range zones {
		pbZones[i] = &pb.MemoryZone{
			Id:          z.ID,
			ZoneId:      z.ZoneID,
			UserId:      z.UserID,
			SessionId:   z.SessionID,
			Description: z.Description,
			ZoneType:    z.ZoneType,
			IsActive:    z.IsActive,
			CreatedAt:   z.CreatedAt.Unix(),
		}
	}

	return &pb.ListZonesResponse{
		Zones: pbZones,
	}, nil
}

// AddZoneMemory 添加区域记忆
func (s *MemoryGRPCServer) AddZoneMemory(ctx context.Context, req *pb.AddZoneMemoryRequest) (*pb.ZoneMemory, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.ZoneId == "" {
		return nil, status.Error(codes.InvalidArgument, "zone_id is required")
	}

	var metadata map[string]interface{}
	if req.Metadata != "" {
		json.Unmarshal([]byte(req.Metadata), &metadata)
	}

	memory, err := s.memoryService.AddZoneMemory(ctx, service.AddZoneMemoryInput{
		UserID:      req.UserId,
		ZoneID:      req.ZoneId,
		Content:     req.Content,
		ContentType: req.ContentType,
		SourceURL:   req.SourceUrl,
		PageTitle:   req.PageTitle,
		Metadata:    metadata,
	})

	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	metadataJSON, _ := json.Marshal(memory.Metadata)
	return &pb.ZoneMemory{
		Id:             memory.ID,
		ZoneId:         memory.ZoneID,
		UserId:         memory.UserID,
		Content:        memory.Content,
		ContentType:    memory.ContentType,
		SequenceNumber: int32(memory.SequenceNumber),
		SourceUrl:      memory.SourceURL,
		PageTitle:      memory.PageTitle,
		Metadata:       string(metadataJSON),
		CreatedAt:      memory.CreatedAt.Unix(),
	}, nil
}

// GetZoneMemories 获取区域记忆
func (s *MemoryGRPCServer) GetZoneMemories(ctx context.Context, req *pb.GetZoneMemoriesRequest) (*pb.GetZoneMemoriesResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.ZoneId == "" {
		return nil, status.Error(codes.InvalidArgument, "zone_id is required")
	}

	memories, err := s.memoryService.GetZoneMemories(ctx, req.UserId, req.ZoneId)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	pbMemories := make([]*pb.ZoneMemory, len(memories))
	for i, m := range memories {
		metadataJSON, _ := json.Marshal(m.Metadata)
		pbMemories[i] = &pb.ZoneMemory{
			Id:             m.ID,
			ZoneId:         m.ZoneID,
			UserId:         m.UserID,
			Content:        m.Content,
			ContentType:    m.ContentType,
			SequenceNumber: int32(m.SequenceNumber),
			SourceUrl:      m.SourceURL,
			PageTitle:      m.PageTitle,
			Metadata:       string(metadataJSON),
			CreatedAt:      m.CreatedAt.Unix(),
		}
	}

	return &pb.GetZoneMemoriesResponse{
		Memories: pbMemories,
	}, nil
}

// SaveChatMessage 保存聊天消息
func (s *MemoryGRPCServer) SaveChatMessage(ctx context.Context, req *pb.SaveChatMessageRequest) (*pb.ChatMessage, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.SessionId == "" {
		return nil, status.Error(codes.InvalidArgument, "session_id is required")
	}

	var toolCalls []interface{}
	if req.ToolCalls != "" {
		json.Unmarshal([]byte(req.ToolCalls), &toolCalls)
	}

	var metadata map[string]interface{}
	if req.Metadata != "" {
		json.Unmarshal([]byte(req.Metadata), &metadata)
	}

	msg, err := s.memoryService.SaveChatMessage(ctx, service.SaveChatMessageInput{
		UserID:    req.UserId,
		SessionID: req.SessionId,
		Role:      req.Role,
		Content:   req.Content,
		ToolCalls: toolCalls,
		Metadata:  metadata,
	})

	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	toolCallsJSON, _ := json.Marshal(msg.ToolCalls)
	metadataJSON, _ := json.Marshal(msg.Metadata)

	return &pb.ChatMessage{
		Id:        msg.ID,
		SessionId: msg.SessionID,
		UserId:    msg.UserID,
		Role:      msg.Role,
		Content:   msg.Content,
		ToolCalls: string(toolCallsJSON),
		Metadata:  string(metadataJSON),
		CreatedAt: msg.CreatedAt.Unix(),
	}, nil
}

// GetChatHistory 获取聊天历史
func (s *MemoryGRPCServer) GetChatHistory(ctx context.Context, req *pb.GetChatHistoryRequest) (*pb.GetChatHistoryResponse, error) {
	if req.UserId == "" {
		return nil, status.Error(codes.InvalidArgument, "user_id is required")
	}
	if req.SessionId == "" {
		return nil, status.Error(codes.InvalidArgument, "session_id is required")
	}

	limit := int(req.Limit)
	if limit <= 0 {
		limit = 50
	}

	messages, err := s.memoryService.GetChatHistory(ctx, req.UserId, req.SessionId, limit)
	if err != nil {
		return nil, status.Error(codes.Internal, err.Error())
	}

	pbMessages := make([]*pb.ChatMessage, len(messages))
	for i, m := range messages {
		toolCallsJSON, _ := json.Marshal(m.ToolCalls)
		metadataJSON, _ := json.Marshal(m.Metadata)

		pbMessages[i] = &pb.ChatMessage{
			Id:        m.ID,
			SessionId: m.SessionID,
			UserId:    m.UserID,
			Role:      m.Role,
			Content:   m.Content,
			ToolCalls: string(toolCallsJSON),
			Metadata:  string(metadataJSON),
			CreatedAt: m.CreatedAt.Unix(),
		}
	}

	return &pb.GetChatHistoryResponse{
		Messages: pbMessages,
	}, nil
}
