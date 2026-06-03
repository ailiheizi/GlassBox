package milvus

import (
	"context"
	"fmt"
	"log"
	"strings"

	"github.com/milvus-io/milvus-sdk-go/v2/client"
	"github.com/milvus-io/milvus-sdk-go/v2/entity"
)

const (
	CollectionName = "semantic_memories"
	VectorDim      = 1536
	IndexType      = "IVF_FLAT"
	MetricType     = entity.L2
	NList          = 128
)

// Client Milvus客户端
type Client struct {
	client client.Client
}

// NewClient 创建Milvus客户端
func NewClient(address string) (*Client, error) {
	ctx := context.Background()
	c, err := client.NewClient(ctx, client.Config{
		Address: address,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to milvus: %w", err)
	}

	mc := &Client{client: c}
	if err := mc.ensureCollection(ctx); err != nil {
		c.Close()
		return nil, err
	}

	return mc, nil
}

// ensureCollection 确保集合存在
func (c *Client) ensureCollection(ctx context.Context) error {
	exists, err := c.client.HasCollection(ctx, CollectionName)
	if err != nil {
		return fmt.Errorf("failed to check collection: %w", err)
	}

	if !exists {
		if err := c.createCollection(ctx); err != nil {
			return err
		}
	}

	// 加载集合到内存
	if err := c.client.LoadCollection(ctx, CollectionName, false); err != nil {
		log.Printf("Warning: failed to load collection: %v", err)
	}

	return nil
}

// createCollection 创建集合
func (c *Client) createCollection(ctx context.Context) error {
	schema := &entity.Schema{
		CollectionName: CollectionName,
		Description:    "Semantic memories with embeddings",
		Fields: []*entity.Field{
			{
				Name:       "id",
				DataType:   entity.FieldTypeVarChar,
				PrimaryKey: true,
				AutoID:     false,
				TypeParams: map[string]string{"max_length": "64"},
			},
			{
				Name:       "user_id",
				DataType:   entity.FieldTypeVarChar,
				TypeParams: map[string]string{"max_length": "64"},
			},
			{
				Name:     "embedding",
				DataType: entity.FieldTypeFloatVector,
				TypeParams: map[string]string{
					"dim": fmt.Sprintf("%d", VectorDim),
				},
			},
		},
	}

	if err := c.client.CreateCollection(ctx, schema, 2); err != nil {
		return fmt.Errorf("failed to create collection: %w", err)
	}

	// 创建索引
	idx, err := entity.NewIndexIvfFlat(MetricType, NList)
	if err != nil {
		return fmt.Errorf("failed to create index: %w", err)
	}

	if err := c.client.CreateIndex(ctx, CollectionName, "embedding", idx, false); err != nil {
		return fmt.Errorf("failed to create index: %w", err)
	}

	log.Printf("Created collection %s with index", CollectionName)
	return nil
}

// Insert 插入向量
func (c *Client) Insert(ctx context.Context, id, userID string, embedding []float32) error {
	ids := []string{id}
	userIDs := []string{userID}
	embeddings := [][]float32{embedding}

	idColumn := entity.NewColumnVarChar("id", ids)
	userIDColumn := entity.NewColumnVarChar("user_id", userIDs)
	embeddingColumn := entity.NewColumnFloatVector("embedding", VectorDim, embeddings)

	_, err := c.client.Insert(ctx, CollectionName, "", idColumn, userIDColumn, embeddingColumn)
	if err != nil {
		return fmt.Errorf("failed to insert: %w", err)
	}

	return nil
}

// Search 搜索相似向量
func (c *Client) Search(ctx context.Context, userID string, embedding []float32, topK int) ([]string, []float32, error) {
	vectors := []entity.Vector{entity.FloatVector(embedding)}

	sp, err := entity.NewIndexIvfFlatSearchParam(16)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to create search param: %w", err)
	}

	// 添加user_id过滤（转义双引号防止注入）
	escapedUserID := strings.ReplaceAll(userID, "\"", "\\\"")
	expr := fmt.Sprintf("user_id == \"%s\"", escapedUserID)

	results, err := c.client.Search(
		ctx,
		CollectionName,
		nil,
		expr,
		[]string{"id"},
		vectors,
		"embedding",
		MetricType,
		topK,
		sp,
	)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to search: %w", err)
	}

	if len(results) == 0 {
		return []string{}, []float32{}, nil
	}

	var ids []string
	var scores []float32

	for _, result := range results {
		idColumn, ok := result.Fields.GetColumn("id").(*entity.ColumnVarChar)
		if !ok {
			continue
		}
		for i := 0; i < result.ResultCount; i++ {
			id, err := idColumn.ValueByIdx(i)
			if err != nil {
				continue
			}
			ids = append(ids, id)
			scores = append(scores, result.Scores[i])
		}
	}

	return ids, scores, nil
}

// Delete 删除向量
func (c *Client) Delete(ctx context.Context, id string) error {
	// 转义双引号防止注入
	escapedID := strings.ReplaceAll(id, "\"", "\\\"")
	expr := fmt.Sprintf("id == \"%s\"", escapedID)
	if err := c.client.Delete(ctx, CollectionName, "", expr); err != nil {
		return fmt.Errorf("failed to delete: %w", err)
	}
	return nil
}

// Close 关闭连接
func (c *Client) Close() error {
	return c.client.Close()
}
