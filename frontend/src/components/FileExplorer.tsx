/**
 * FileExplorer - Manus 风格文件树 + 代码查看器
 * 左侧文件树，右侧代码查看器（带语法高亮）
 */

import React, { useState, useEffect, useCallback } from 'react';

interface FileItem {
  name: string;
  path: string;
  type: 'file' | 'directory' | 'unknown';
  size: number;
  modified: number;
  permissions: string;
}

interface FileExplorerProps {
  userId: string;
  apiBaseUrl?: string;
}

// 文件类型图标映射
const getFileIcon = (name: string, type: string): string => {
  if (type === 'directory') return '\u{1F4C1}';
  const ext = name.split('.').pop()?.toLowerCase() || '';
  const iconMap: Record<string, string> = {
    py: '\u{1F40D}', js: '\u{1F7E8}', ts: '\u{1F535}', tsx: '\u{1F535}',
    jsx: '\u{1F7E8}', json: '\u{1F4CB}', md: '\u{1F4DD}', txt: '\u{1F4C4}',
    html: '\u{1F310}', css: '\u{1F3A8}', sh: '\u{1F4DF}', yml: '\u{2699}',
    yaml: '\u{2699}', toml: '\u{2699}', cfg: '\u{2699}', ini: '\u{2699}',
    go: '\u{1F4A0}', rs: '\u{1F980}', java: '\u{2615}', c: '\u{1F1E8}',
    cpp: '\u{1F1E8}', h: '\u{1F1ED}', png: '\u{1F5BC}', jpg: '\u{1F5BC}',
    gif: '\u{1F5BC}', svg: '\u{1F5BC}', lock: '\u{1F512}',
  };
  return iconMap[ext] || '\u{1F4C4}';
};

// 格式化文件大小
const formatSize = (bytes: number): string => {
  if (bytes === 0) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

// 简单语法高亮（基于文件扩展名的关键字着色）
const getLanguageClass = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const langMap: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript', tsx: 'typescript',
    jsx: 'javascript', json: 'json', html: 'html', css: 'css',
    sh: 'bash', go: 'go', rs: 'rust', java: 'java', md: 'markdown',
    yml: 'yaml', yaml: 'yaml', toml: 'toml',
  };
  return langMap[ext] || 'text';
};

export const FileExplorer: React.FC<FileExplorerProps> = ({
  userId,
  apiBaseUrl = '',
}) => {
  const [currentPath, setCurrentPath] = useState('/home/sandbox');
  const [files, setFiles] = useState<FileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [fileEncoding, setFileEncoding] = useState<string>('utf-8');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['/home/sandbox']));

  const baseUrl = apiBaseUrl || '';

  const fetchFiles = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${baseUrl}/api/v1/ai/sandbox/files/${userId}/list?path=${encodeURIComponent(path)}`,
        { credentials: 'include' }
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setFiles(data.items || []);
      setCurrentPath(data.path || path);
    } catch (e: any) {
      setError(e.message || 'Failed to load files');
    } finally {
      setLoading(false);
    }
  }, [userId, baseUrl]);

  const fetchFileContent = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(
        `${baseUrl}/api/v1/ai/sandbox/files/${userId}/read?path=${encodeURIComponent(path)}`,
        { credentials: 'include' }
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setFileContent(data.content || '');
      setFileEncoding(data.encoding || 'utf-8');
      setSelectedFile(path);
    } catch (e: any) {
      setError(e.message || 'Failed to read file');
    } finally {
      setLoading(false);
    }
  }, [userId, baseUrl]);

  // 初始加载
  useEffect(() => {
    fetchFiles(currentPath);
  }, [fetchFiles, currentPath]);

  const handleItemClick = (item: FileItem) => {
    if (item.type === 'directory') {
      const newExpanded = new Set(expandedDirs);
      if (newExpanded.has(item.path)) {
        newExpanded.delete(item.path);
      } else {
        newExpanded.add(item.path);
      }
      setExpandedDirs(newExpanded);
      setCurrentPath(item.path);
      fetchFiles(item.path);
    } else {
      fetchFileContent(item.path);
    }
  };

  const navigateUp = () => {
    const parent = currentPath.split('/').slice(0, -1).join('/') || '/';
    if (parent === '/home' || parent === '/') return; // 安全边界
    setCurrentPath(parent);
    fetchFiles(parent);
  };

  const breadcrumbs = currentPath.split('/').filter(Boolean);

  return (
    <div className="flex h-full bg-gray-900 text-gray-300">
      {/* 左侧：文件树 */}
      <div className="w-64 flex-shrink-0 border-r border-gray-700 flex flex-col">
        {/* 路径导航 */}
        <div className="px-3 py-2 border-b border-gray-700 bg-gray-800">
          <div className="flex items-center text-xs text-gray-400 overflow-x-auto whitespace-nowrap">
            <button
              onClick={() => { setCurrentPath('/home/sandbox'); fetchFiles('/home/sandbox'); }}
              className="hover:text-white"
            >
              ~
            </button>
            {breadcrumbs.slice(2).map((part, i) => (
              <span key={i}>
                <span className="mx-1">/</span>
                <button
                  onClick={() => {
                    const path = '/' + breadcrumbs.slice(0, i + 3).join('/');
                    setCurrentPath(path);
                    fetchFiles(path);
                  }}
                  className="hover:text-white"
                >
                  {part}
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* 文件列表 */}
        <div className="flex-1 overflow-y-auto">
          {currentPath !== '/home/sandbox' && (
            <button
              onClick={navigateUp}
              className="w-full px-3 py-1.5 text-left text-xs hover:bg-gray-800 flex items-center space-x-2"
            >
              <span>..</span>
            </button>
          )}
          {loading && files.length === 0 ? (
            <div className="px-3 py-4 text-center text-gray-500 text-xs">Loading...</div>
          ) : (
            files.map((item) => (
              <button
                key={item.path}
                onClick={() => handleItemClick(item)}
                className={`w-full px-3 py-1.5 text-left text-xs hover:bg-gray-800 flex items-center space-x-2 ${
                  selectedFile === item.path ? 'bg-gray-700 text-white' : ''
                }`}
              >
                <span className="flex-shrink-0">{getFileIcon(item.name, item.type)}</span>
                <span className="truncate flex-1">{item.name}</span>
                {item.type === 'file' && (
                  <span className="text-gray-600 flex-shrink-0">{formatSize(item.size)}</span>
                )}
              </button>
            ))
          )}
          {!loading && files.length === 0 && (
            <div className="px-3 py-4 text-center text-gray-500 text-xs">Empty directory</div>
          )}
        </div>
      </div>

      {/* 右侧：代码查看器 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedFile ? (
          <>
            {/* 文件标题栏 */}
            <div className="px-3 py-1.5 border-b border-gray-700 bg-gray-800 flex items-center justify-between">
              <div className="flex items-center space-x-2 text-xs">
                <span className="text-gray-400">{selectedFile.split('/').pop()}</span>
                <span className="text-gray-600">({getLanguageClass(selectedFile)})</span>
              </div>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <span>{fileEncoding}</span>
                <button
                  onClick={() => fetchFileContent(selectedFile)}
                  className="hover:text-white"
                  title="Refresh"
                >
                  &#x21bb;
                </button>
              </div>
            </div>

            {/* 代码内容 */}
            <div className="flex-1 overflow-auto">
              {fileEncoding === 'base64' ? (
                <div className="p-4 text-center text-gray-500">
                  <p>Binary file ({formatSize(fileContent.length)})</p>
                  <p className="text-xs mt-1">Cannot display binary content</p>
                </div>
              ) : (
                <pre className="p-0 m-0 text-xs leading-5">
                  <code>
                    {fileContent.split('\n').map((line, i) => (
                      <div key={i} className="flex hover:bg-gray-800/50">
                        <span className="w-12 flex-shrink-0 text-right pr-3 text-gray-600 select-none border-r border-gray-800">
                          {i + 1}
                        </span>
                        <span className="pl-3 whitespace-pre overflow-x-auto">{line}</span>
                      </div>
                    ))}
                  </code>
                </pre>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-600 text-sm">
            Select a file to view its content
          </div>
        )}
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="absolute bottom-4 right-4 bg-red-900/80 text-red-200 px-3 py-2 rounded text-xs">
          {error}
        </div>
      )}
    </div>
  );
};

export default FileExplorer;
