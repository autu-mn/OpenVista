import { useState, useEffect, ReactNode } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Loader2, RefreshCw, AlertCircle, Bug, TrendingUp, MessageCircle, Tag, Sparkles } from 'lucide-react'

// 渲染内联 Markdown（加粗、斜体等）
function renderInlineMarkdown(text: string): ReactNode {
  // 处理 **加粗**
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <span key={i} className="text-cyber-primary font-medium">
          {part.slice(2, -2)}
        </span>
      )
    }
    // 处理 *斜体*
    if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
      return (
        <span key={i} className="italic text-cyber-secondary">
          {part.slice(1, -1)}
        </span>
      )
    }
    return part
  })
}

interface IssueStats {
  total: number
  open: number
  closed: number
  categories: {
    bug: number
    feature: number
    question: number
    other: number
  }
  hot_issues?: Array<{
    number: number
    title: string
    state: string
    heat: number
    month: string
    ai_summary?: string  // AI 生成的简要概述
  }>
}

interface IssueAnalysisResult {
  summary: string
  stats: IssueStats
  ai_enabled: boolean
  error?: string
}

interface IssueAIAnalysisProps {
  repoKey: string
}

export default function IssueAIAnalysis({ repoKey }: IssueAIAnalysisProps) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<IssueAnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchAnalysis = async () => {
    if (!repoKey) return
    
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/api/issues/analyze/${encodeURIComponent(repoKey)}`)
      const data = await response.json()
      
      if (data.error && !data.summary) {
        setError(data.error)
      } else {
        setResult(data)
      }
    } catch (err) {
      setError('加载分析数据失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalysis()
  }, [repoKey])

  if (loading) {
    return (
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6">
        <div className="flex items-center justify-center gap-3 py-8">
          <Loader2 className="w-6 h-6 text-cyber-primary animate-spin" />
          <span className="text-cyber-muted font-chinese">正在使用 AI 分析 Issue 数据...</span>
        </div>
      </div>
    )
  }

  if (error && !result) {
    return (
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6">
        <div className="flex items-center justify-center gap-3 py-8 text-cyber-accent">
          <AlertCircle className="w-6 h-6" />
          <span className="font-chinese">{error}</span>
        </div>
      </div>
    )
  }

  if (!result) return null

  return (
    <motion.div
      className="bg-gradient-to-br from-cyber-card/80 to-cyber-card/40 rounded-xl border border-cyber-secondary/20 overflow-hidden shadow-lg"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {/* 标题栏 */}
      <div className="px-6 py-4 border-b border-cyber-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-cyber-secondary/30 to-cyber-accent/30 rounded-lg">
            <Bot className="w-5 h-5 text-cyber-secondary" />
          </div>
          <div>
            <h3 className="text-lg font-display font-bold text-cyber-text flex items-center gap-2">
              Issue 智能分析
              {result.ai_enabled && (
                <span className="text-xs font-normal text-cyber-secondary bg-cyber-secondary/10 px-2 py-0.5 rounded-full">
                  DeepSeek AI
                </span>
              )}
            </h3>
            <p className="text-sm text-cyber-muted font-chinese">
              分析 {result.stats?.total || 0} 个 Issue，识别问题趋势
            </p>
          </div>
        </div>
        <button
          onClick={fetchAnalysis}
          disabled={loading}
          className="p-2 text-cyber-muted hover:text-cyber-primary transition-colors"
          title="刷新分析"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="p-6 space-y-6">
        {/* 统计卡片 */}
        {result.stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 bg-cyber-bg/50 rounded-lg border border-cyber-border/50 text-center">
              <div className="text-2xl font-display font-bold text-cyber-primary">
                {result.stats.total?.toLocaleString() || 0}
              </div>
              <div className="text-xs text-cyber-muted font-chinese">分析总数</div>
            </div>
            <div className="p-3 bg-cyber-bg/50 rounded-lg border border-cyber-border/50 text-center">
              <div className="text-2xl font-display font-bold text-cyber-accent flex items-center justify-center gap-1">
                <Bug className="w-4 h-4" />
                {result.stats.categories?.bug || 0}
              </div>
              <div className="text-xs text-cyber-muted font-chinese">Bug 报告</div>
            </div>
            <div className="p-3 bg-cyber-bg/50 rounded-lg border border-cyber-border/50 text-center">
              <div className="text-2xl font-display font-bold text-cyber-success flex items-center justify-center gap-1">
                <TrendingUp className="w-4 h-4" />
                {result.stats.categories?.feature || 0}
              </div>
              <div className="text-xs text-cyber-muted font-chinese">功能需求</div>
            </div>
            <div className="p-3 bg-cyber-bg/50 rounded-lg border border-cyber-border/50 text-center">
              <div className="text-2xl font-display font-bold text-cyber-secondary flex items-center justify-center gap-1">
                <MessageCircle className="w-4 h-4" />
                {result.stats.categories?.question || 0}
              </div>
              <div className="text-xs text-cyber-muted font-chinese">问题咨询</div>
            </div>
          </div>
        )}

        {/* AI 分析摘要 - 完整 Markdown 渲染 */}
        <div className="prose prose-invert max-w-none">
          {result.summary.split('\n').map((line, idx) => {
            // 处理 ### 三级标题
            if (line.startsWith('### ')) {
              return (
                <h5 key={idx} className="text-base font-display font-bold text-cyber-primary mt-3 mb-2 flex items-center gap-2">
                  <span className="w-1 h-4 bg-cyber-primary rounded-full"></span>
                  {line.replace('### ', '')}
                </h5>
              )
            }
            // 处理 ## 二级标题
            if (line.startsWith('## ')) {
              return (
                <h4 key={idx} className="text-lg font-display font-bold text-cyber-secondary mt-4 mb-2 flex items-center gap-2">
                  <span className="w-1 h-5 bg-cyber-secondary rounded-full"></span>
                  {line.replace('## ', '')}
                </h4>
              )
            }
            // 处理 # 一级标题
            if (line.startsWith('# ') && !line.startsWith('## ') && !line.startsWith('### ')) {
              return (
                <h3 key={idx} className="text-xl font-display font-bold text-cyber-text mt-4 mb-3">
                  {line.replace('# ', '')}
                </h3>
              )
            }
            // 处理数字列表 (1. 2. 3.)
            const numListMatch = line.match(/^(\d+)\.\s+(.+)$/)
            if (numListMatch) {
              return (
                <div key={idx} className="flex items-start gap-2 text-sm text-cyber-text/90 font-chinese ml-2 mb-1">
                  <span className="text-cyber-secondary font-mono min-w-[1.5rem]">{numListMatch[1]}.</span>
                  <span>{renderInlineMarkdown(numListMatch[2])}</span>
                </div>
              )
            }
            // 处理列表项
            if (line.startsWith('- ') || line.startsWith('* ')) {
              return (
                <div key={idx} className="flex items-start gap-2 text-sm text-cyber-text/80 font-chinese ml-2 mb-1">
                  <span className="text-cyber-primary mt-1">•</span>
                  <span>{renderInlineMarkdown(line.slice(2))}</span>
                </div>
              )
            }
            // 普通段落（处理内联 Markdown）
            if (line.trim()) {
              return (
                <p key={idx} className="text-cyber-text/90 font-chinese leading-relaxed mb-2 text-sm">
                  {renderInlineMarkdown(line)}
                </p>
              )
            }
            return null
          })}
        </div>

        {/* 热门 Issue - 带 AI 概述 */}
        {result.stats?.hot_issues && result.stats.hot_issues.length > 0 && (
          <div className="mt-4 pt-4 border-t border-cyber-border/50">
            <h5 className="text-sm font-display font-bold text-cyber-muted mb-3 flex items-center gap-2">
              <Tag className="w-4 h-4" />
              热门讨论 Top 5
              {result.ai_enabled && (
                <span className="text-xs font-normal text-cyber-secondary/70 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" />
                  AI 概述
                </span>
              )}
            </h5>
            <div className="space-y-3">
              {result.stats.hot_issues.slice(0, 5).map((issue, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-cyber-bg/30 rounded-lg border border-cyber-border/30 hover:border-cyber-primary/30 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        issue.state === 'open' ? 'bg-cyber-success' : 'bg-cyber-muted'
                      }`} />
                      <span className="text-cyber-muted font-mono text-sm">#{issue.number}</span>
                      <span className="text-cyber-text text-sm truncate font-medium">{issue.title}</span>
                    </div>
                    <span className="text-xs text-cyber-accent bg-cyber-accent/10 px-2 py-0.5 rounded ml-2 flex-shrink-0">
                      🔥 {issue.heat}
                    </span>
                  </div>
                  {/* AI 生成的概述 */}
                  {issue.ai_summary && (
                    <p className="text-xs text-cyber-muted/80 font-chinese mt-1 pl-4 border-l-2 border-cyber-secondary/30">
                      💡 {issue.ai_summary}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}

