/**
 * TraceTimeline - Manus 风格执行链路可视化组件
 * 按时间顺序展示 AI Agent 的完整决策链路
 */

import React, { useEffect, useRef } from 'react';

export interface TraceEvent {
  id: string;
  timestamp: Date;
  type:
    | 'skill_retrieval'
    | 'model_routing'
    | 'llm_call_start'
    | 'llm_call_end'
    | 'thinking'
    | 'tool_call'
    | 'tool_result'
    | 'tool_error'
    | 'node_transition'
    | 'plan_created'
    | 'action_executed'
    | 'review_result'
    | 'screenshot'
    | 'step_start'
    | 'step_end'
    | 'execution_complete'
    | 'model_switch'
    | 'warning'
    | 'error';
  data: Record<string, any>;
}

interface TraceTimelineProps {
  events: TraceEvent[];
  isStreaming: boolean;
  onClose: () => void;
}

const EVENT_CONFIG: Record<
  string,
  { icon: string; label: string; color: string; bgColor: string }
> = {
  skill_retrieval: {
    icon: '\u{1F50D}',
    label: '技能检索',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30 border-blue-700',
  },
  model_routing: {
    icon: '\u{1F9E0}',
    label: '模型路由',
    color: 'text-purple-400',
    bgColor: 'bg-purple-900/30 border-purple-700',
  },
  llm_call_start: {
    icon: '\u26A1',
    label: 'LLM 调用',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30 border-orange-700',
  },
  llm_call_end: {
    icon: '\u26A1',
    label: 'LLM 返回',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30 border-orange-700',
  },
  thinking: {
    icon: '\u{1F4AD}',
    label: '思考',
    color: 'text-gray-400',
    bgColor: 'bg-gray-800/50 border-gray-600',
  },
  tool_call: {
    icon: '\u{1F527}',
    label: '工具调用',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30 border-yellow-700',
  },
  tool_result: {
    icon: '\u2713',
    label: '工具结果',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30 border-green-700',
  },
  tool_error: {
    icon: '\u2717',
    label: '工具错误',
    color: 'text-red-400',
    bgColor: 'bg-red-900/30 border-red-700',
  },
  node_transition: {
    icon: '\u2192',
    label: '节点转移',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30 border-blue-700',
  },
  plan_created: {
    icon: '\u{1F4CB}',
    label: '计划创建',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30 border-blue-700',
  },
  action_executed: {
    icon: '\u26A1',
    label: '动作执行',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30 border-yellow-700',
  },
  review_result: {
    icon: '\u{1F50D}',
    label: '审查结果',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30 border-green-700',
  },
  screenshot: {
    icon: '\u{1F4F8}',
    label: '截图',
    color: 'text-gray-400',
    bgColor: 'bg-gray-800/50 border-gray-600',
  },
  step_start: {
    icon: '\u25B6',
    label: '步骤开始',
    color: 'text-blue-300',
    bgColor: 'bg-blue-900/20 border-blue-800',
  },
  step_end: {
    icon: '\u25A0',
    label: '步骤结束',
    color: 'text-gray-500',
    bgColor: 'bg-gray-800/30 border-gray-700',
  },
  execution_complete: {
    icon: '\u2705',
    label: '执行完成',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30 border-green-700',
  },
  model_switch: {
    icon: '\u21C4',
    label: '模型切换',
    color: 'text-amber-400',
    bgColor: 'bg-amber-900/30 border-amber-700',
  },
  warning: {
    icon: '\u26A0',
    label: '警告',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30 border-yellow-700',
  },
  error: {
    icon: '\u274C',
    label: '错误',
    color: 'text-red-400',
    bgColor: 'bg-red-900/30 border-red-700',
  },
};

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function truncate(str: string, max: number): string {
  if (str.length <= max) return str;
  return str.slice(0, max) + '...';
}

const TraceEventItem: React.FC<{ event: TraceEvent }> = ({ event }) => {
  const config = EVENT_CONFIG[event.type] || {
    icon: '\u25CF',
    label: event.type,
    color: 'text-gray-400',
    bgColor: 'bg-gray-800/50 border-gray-600',
  };

  const renderDetail = () => {
    const d = event.data;
    switch (event.type) {
      case 'skill_retrieval':
        return (
          <div className="mt-1 space-y-1">
            <div className="text-gray-500 text-xs">
              查询: {truncate(d.query || '', 60)}
            </div>
            <div className="text-gray-500 text-xs">
              匹配 {d.matched_count || 0} 个技能
            </div>
            {d.skills?.map((s: any, i: number) => (
              <div key={i} className="flex items-center text-xs ml-2">
                <span className="text-gray-400 mr-1">
                  {i === d.skills.length - 1 ? '\u2514' : '\u251C'}
                </span>
                <span className="text-blue-300">{s.name}</span>
                <span className="text-gray-600 ml-1">
                  (score: {typeof s.score === 'number' ? s.score.toFixed(2) : s.score})
                </span>
              </div>
            ))}
          </div>
        );

      case 'model_routing':
        return (
          <div className="mt-1 space-y-0.5 text-xs">
            <div className="text-purple-300">
              {d.routing_method === 'forced'
                ? '强制指定'
                : d.routing_method === 'llm'
                  ? 'LLM 路由'
                  : '关键词路由'}{' '}
              → {d.category || '未知'}
            </div>
            <div className="text-gray-400">
              选择 <span className="text-white font-mono">{d.model}</span>
            </div>
            <div className="text-gray-500">
              置信度: {((d.confidence || 0) * 100).toFixed(0)}%
            </div>
            {d.reason && (
              <div className="text-gray-500">{truncate(d.reason, 80)}</div>
            )}
          </div>
        );

      case 'llm_call_start':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className="text-orange-300 font-mono">{d.model}</div>
            <div className="text-gray-500">
              {d.provider} | {d.has_screenshot ? '截图 + 工具定义' : '文本 + 工具定义'}
            </div>
          </div>
        );

      case 'llm_call_end':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className="text-orange-300 font-mono">{d.model}</div>
            <div className="text-gray-500">
              {d.has_tool_calls
                ? `${d.tool_calls_count} 个工具调用`
                : '无工具调用'}
              {d.has_reasoning ? ' | 含推理' : ''}
              {d.content_length ? ` | ${d.content_length} 字符` : ''}
            </div>
            {d.usage && (d.usage.input_tokens > 0 || d.usage.output_tokens > 0 || d.usage.prompt_tokens > 0 || d.usage.completion_tokens > 0 || d.usage.total_tokens > 0) && (
              <div className="text-cyan-400">
                Tokens: {d.usage.input_tokens || d.usage.prompt_tokens || 0} in
                {' / '}{d.usage.output_tokens || d.usage.completion_tokens || 0} out
                {d.usage.total_tokens ? ` (${d.usage.total_tokens} total)` : ''}
              </div>
            )}
            {d.trace_url && (
              <a
                href={d.trace_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 underline"
              >
                View in Langfuse
              </a>
            )}
          </div>
        );

      case 'thinking': {
        const content = d.content || '';
        return (
          <div className="mt-1 text-xs space-y-0.5">
            {d.label && (
              <div className="text-purple-300 font-medium">{d.label}{d.model ? ` (${d.model})` : ''}</div>
            )}
            {d.reasoning && (
              <div className="text-gray-500 italic whitespace-pre-wrap max-h-16 overflow-y-auto">
                {truncate(d.reasoning, 200)}
              </div>
            )}
            <div className="text-gray-400 whitespace-pre-wrap max-h-24 overflow-y-auto">
              {truncate(content, 300)}
            </div>
          </div>
        );
      }

      case 'tool_call':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className="text-yellow-300 font-mono">{d.tool}</div>
            {d.args && (
              <pre className="text-gray-500 overflow-x-auto max-h-16 overflow-y-auto">
                {JSON.stringify(d.args, null, 2)}
              </pre>
            )}
          </div>
        );

      case 'tool_result':
        return (
          <div className="mt-1 text-xs">
            <span className="text-green-300 font-mono">{d.tool}</span>
            <span className="text-green-400 ml-1">→ 成功</span>
            {d.result && (
              <div className="text-gray-500 mt-0.5 max-h-16 overflow-y-auto">
                {truncate(
                  typeof d.result === 'string'
                    ? d.result
                    : JSON.stringify(d.result),
                  200,
                )}
              </div>
            )}
          </div>
        );

      case 'tool_error':
        return (
          <div className="mt-1 text-xs">
            <span className="text-red-300 font-mono">{d.tool}</span>
            <span className="text-red-400 ml-1">→ 失败</span>
            {d.error && (
              <div className="text-red-400/70 mt-0.5">
                {truncate(d.error, 200)}
              </div>
            )}
          </div>
        );

      case 'node_transition': {
        const nodeNames: Record<string, string> = {
          planner: '规划器',
          executor: '执行器',
          reviewer: '审查器',
        };
        return (
          <div className="mt-1 text-xs text-blue-300">
            {d.from_node
              ? `${nodeNames[d.from_node] || d.from_node} → ${nodeNames[d.to_node] || d.to_node}`
              : `→ ${nodeNames[d.to_node] || d.to_node}`}
            <span className="text-gray-500 ml-2">迭代 {d.iteration}</span>
          </div>
        );
      }

      case 'plan_created': {
        const plan = d.plan;
        const steps = Array.isArray(plan)
          ? plan.map((s: any) =>
              typeof s === 'object' && s !== null
                ? s.description || JSON.stringify(s)
                : String(s),
            )
          : typeof plan === 'string'
            ? [plan]
            : [];
        return (
          <div className="mt-1 text-xs space-y-0.5">
            {d.thinking && (
              <div className="text-gray-500 italic">
                {truncate(d.thinking, 120)}
              </div>
            )}
            <ol className="list-decimal list-inside text-gray-300 space-y-0.5">
              {steps.map((s: string, i: number) => (
                <li key={i}>{truncate(s, 100)}</li>
              ))}
            </ol>
          </div>
        );
      }

      case 'action_executed': {
        const toolName =
          d.tool_name || d.tool || d.action_type || d.type || '未知操作';
        return (
          <div className="mt-1 text-xs">
            <span className="text-yellow-300 font-mono">{toolName}</span>
            {d.success === true && (
              <span className="text-green-400 ml-1">成功</span>
            )}
            {d.success === false && (
              <span className="text-red-400 ml-1">失败</span>
            )}
            {d.error && (
              <div className="text-red-400/70 mt-0.5">
                {truncate(d.error, 150)}
              </div>
            )}
          </div>
        );
      }

      case 'review_result':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className={d.passed ? 'text-green-400' : 'text-red-400'}>
              {d.passed ? '通过' : '未通过'}
            </div>
            {d.feedback && (
              <div className="text-gray-400">
                {truncate(d.feedback, 150)}
              </div>
            )}
            {d.suggestions?.length > 0 && (
              <ul className="text-gray-500 list-disc list-inside">
                {d.suggestions.map((s: string, i: number) => (
                  <li key={i}>{truncate(s, 80)}</li>
                ))}
              </ul>
            )}
          </div>
        );

      case 'screenshot':
        return (
          <div className="mt-1 text-xs text-gray-500">
            {d.width && d.height
              ? `${d.width}x${d.height}`
              : '已截图'}
            {d.step && ` (步骤 ${d.step})`}
          </div>
        );

      case 'step_start':
        return (
          <div className="mt-1 text-xs text-blue-300">
            步骤 {d.step}/{d.max_steps}
            {d.mode && (
              <span className="text-gray-500 ml-1">({d.mode})</span>
            )}
          </div>
        );

      case 'step_end':
        return null;

      case 'execution_complete':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className="text-green-300">
              总步数: {d.total_steps} | 状态: {d.final_status}
            </div>
            {d.final_mode && (
              <div className="text-gray-500">模式: {d.final_mode}</div>
            )}
          </div>
        );

      case 'model_switch':
        return (
          <div className="mt-1 text-xs space-y-0.5">
            <div className="text-amber-300">
              <span className="font-mono">{d.from_model}</span>
              {' → '}
              <span className="font-mono">{d.to_model}</span>
            </div>
            {d.reason && (
              <div className="text-gray-500">{d.reason}</div>
            )}
            {d.step && (
              <div className="text-gray-600">步骤 {d.step}</div>
            )}
          </div>
        );

      case 'warning':
        return (
          <div className="mt-1 text-xs text-yellow-400">
            {d.message}
          </div>
        );

      case 'error':
        return (
          <div className="mt-1 text-xs text-red-400">
            {d.message}
          </div>
        );

      default:
        return (
          <div className="mt-1 text-xs text-gray-500">
            {truncate(JSON.stringify(d), 200)}
          </div>
        );
    }
  };

  return (
    <div className="flex items-start space-x-2 py-1.5">
      {/* 时间线圆点 */}
      <div className="flex flex-col items-center flex-shrink-0 w-5">
        <div className={`text-sm ${config.color}`}>{config.icon}</div>
      </div>

      {/* 内容 */}
      <div className={`flex-1 min-w-0 rounded border px-2 py-1.5 ${config.bgColor}`}>
        <div className="flex items-center justify-between">
          <span className={`text-xs font-medium ${config.color}`}>
            {config.label}
          </span>
          <span className="text-gray-600 text-xs flex-shrink-0 ml-2">
            {formatTime(event.timestamp)}
          </span>
        </div>
        {renderDetail()}
      </div>
    </div>
  );
};

export const TraceTimeline: React.FC<TraceTimelineProps> = ({
  events,
  isStreaming,
  onClose,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="flex flex-col h-full">
      {/* 标题栏 */}
      <div className="px-3 py-2 border-b border-gray-700 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center space-x-2">
          <span className="text-white text-sm font-medium">执行链路</span>
          {isStreaming && (
            <span className="flex items-center text-xs text-blue-400">
              <span className="animate-pulse mr-1">●</span>
              实时
            </span>
          )}
          <span className="text-gray-500 text-xs">{events.length} 事件</span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-white text-sm px-1"
          title="关闭"
        >
          ✕
        </button>
      </div>

      {/* 事件列表 */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5"
      >
        {events.length === 0 ? (
          <div className="text-gray-600 text-sm text-center py-8">
            发送消息后，执行链路将在此显示
          </div>
        ) : (
          events.map((event) => (
            <TraceEventItem key={event.id} event={event} />
          ))
        )}

        {/* 流式加载指示器 */}
        {isStreaming && events.length > 0 && (
          <div className="flex items-center space-x-2 py-2 text-gray-500 text-xs">
            <div className="animate-pulse">●</div>
            <span>等待下一个事件...</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default TraceTimeline;
