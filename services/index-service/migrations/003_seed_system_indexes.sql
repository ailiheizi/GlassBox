-- Index Service Migration 003: Seed System Indexes
-- Version: 003
-- Description: Insert initial system index data

INSERT INTO system_indexes (service_name, url, title, description, tags, element_type) VALUES
('feishu', 'https://www.feishu.cn', '飞书首页', '飞书官网首页', ARRAY['办公', '协作'], 'link'),
('feishu', 'https://www.feishu.cn/product/docs', '飞书文档', '飞书在线文档', ARRAY['文档', '协作'], 'link'),
('feishu', 'https://www.feishu.cn/product/messenger', '飞书即时消息', '飞书即时通讯功能', ARRAY['通讯', '协作'], 'link'),
('wechat', 'https://weixin.qq.com', '微信首页', '微信官网', ARRAY['社交', '通讯'], 'link'),
('wechat', 'https://mp.weixin.qq.com', '微信公众平台', '微信公众号管理平台', ARRAY['公众号', '运营'], 'link'),
('google', 'https://www.google.com', 'Google搜索', 'Google搜索引擎', ARRAY['搜索'], 'link'),
('google', 'https://drive.google.com', 'Google Drive', 'Google云存储', ARRAY['存储', '云服务'], 'link'),
('github', 'https://github.com', 'GitHub', '代码托管平台', ARRAY['开发', '代码'], 'link'),
('github', 'https://github.com/new', 'GitHub新建仓库', '创建新的GitHub仓库', ARRAY['开发', '代码'], 'link'),
('baidu', 'https://www.baidu.com', '百度搜索', '百度搜索引擎', ARRAY['搜索'], 'link'),
('taobao', 'https://www.taobao.com', '淘宝首页', '淘宝购物平台', ARRAY['购物', '电商'], 'link'),
('jd', 'https://www.jd.com', '京东首页', '京东购物平台', ARRAY['购物', '电商'], 'link')
ON CONFLICT DO NOTHING;
