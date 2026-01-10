import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Award, AlertCircle, CheckCircle2, TrendingUp, TrendingDown, BarChart3, Info, Sparkles, ChevronDown, ChevronUp } from 'lucide-react'

interface MonthlyScore {
  month: string
  score: {
    overall_score: number
    dimensions: Record<string, {
      score: number
      metrics_count: number
    }>
  }
}

interface FinalScores {
  overall_score: number
  overall_level: string
  _raw_overall_score?: number
  _percentile?: number
  dimensions: Record<string, {
    score: number
    level: string
    monthly_count: number
    outliers_removed: number
    quality?: number
  }>
}

interface CHAOSSData {
  repo_key: string
  time_range: {
    start: string
    end: string
    total_months: number
    evaluated_months: number
    valid_months?: number
    repo_created_month?: string
  }
  monthly_scores: MonthlyScore[]
  final_scores: FinalScores
  report: {
    summary: string
    recommendations: string[]
  }
}

interface CHAOSSEvaluationProps {
  repoKey: string
}

// 维度说明
const dimensionDescriptions: Record<string, { description: string; metrics: string[] }> = {
  'Activity': {
    description: '衡量项目的活跃程度，包括代码提交、Issue 讨论等',
    metrics: ['活跃度', 'Issue评论', '变更请求']
  },
  'Contributors': {
    description: '评估贡献者社区的健康程度和多样性',
    metrics: ['贡献者数', '新增贡献者', '不活跃贡献者']
  },
  'Responsiveness': {
    description: '衡量项目对 Issue 和 PR 的响应速度',
    metrics: ['关闭Issue', 'PR接受数', 'PR审查']
  },
  'Quality': {
    description: '评估代码质量和项目维护水平',
    metrics: ['Bug修复率', 'PR通过率']
  },
  'Risk': {
    description: '识别项目潜在风险因素',
    metrics: ['总线因子', '关键贡献者依赖']
  },
  'Community Interest': {
    description: '衡量社区对项目的兴趣和关注度',
    metrics: ['Star数', 'Fork数', '关注度']
  }
}

export default function CHAOSSEvaluation({ repoKey }: CHAOSSEvaluationProps) {
  const [data, setData] = useState<CHAOSSData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedDimension, setExpandedDimension] = useState<string | null>(null)

  useEffect(() => {
    if (!repoKey) {
      setLoading(false)
      setData(null)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)

    const normalizedKey = repoKey.includes('/') ? repoKey.replace('/', '_') : repoKey
    
    fetch(`/api/chaoss/${normalizedKey}`)
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            throw new Error(err.error || '获取CHAOSS评价失败')
          })
        }
        return res.json()
      })
      .then((result: CHAOSSData) => {
        if ('error' in result) {
          throw new Error((result as any).error)
        }
        setData(result)
      })
      .catch(err => {
        console.error('CHAOSS评估错误:', err)
        setError(err.message || '获取CHAOSS评价失败')
        setData(null)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [repoKey])

  // 雷达图数据
  const radarData = useMemo(() => {
    if (!data?.final_scores?.dimensions) return []
    
    const dimensionNames: Record<string, string> = {
      'Activity': '活动度',
      'Contributors': '贡献者',
      'Responsiveness': '响应性',
      'Quality': '代码质量',
      'Risk': '风险',
      'Community Interest': '社区兴趣'
    }
    
    return Object.entries(data.final_scores.dimensions).map(([key, dim]) => ({
      dimension: dimensionNames[key] || key,
      key,
      score: dim.score,
      level: dim.level
    }))
  }, [data])

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400'
    if (score >= 60) return 'text-cyber-primary'
    if (score >= 40) return 'text-yellow-400'
    if (score >= 20) return 'text-orange-400'
    return 'text-red-400'
  }

  const getScoreBgColor = (score: number) => {
    if (score >= 80) return 'bg-green-500/20 border-green-500/30'
    if (score >= 60) return 'bg-cyber-primary/20 border-cyber-primary/30'
    if (score >= 40) return 'bg-yellow-500/20 border-yellow-500/30'
    if (score >= 20) return 'bg-orange-500/20 border-orange-500/30'
    return 'bg-red-500/20 border-red-500/30'
  }

  const getScoreGradient = (score: number) => {
    if (score >= 80) return 'from-green-500 to-green-400'
    if (score >= 60) return 'from-cyber-primary to-cyan-400'
    if (score >= 40) return 'from-yellow-500 to-yellow-400'
    if (score >= 20) return 'from-orange-500 to-orange-400'
    return 'from-red-500 to-red-400'
  }

  const getProgressBarColor = (score: number) => {
    if (score >= 80) return 'bg-gradient-to-r from-green-500 to-green-400'
    if (score >= 60) return 'bg-gradient-to-r from-cyber-primary to-cyan-400'
    if (score >= 40) return 'bg-gradient-to-r from-yellow-500 to-yellow-400'
    if (score >= 20) return 'bg-gradient-to-r from-orange-500 to-orange-400'
    return 'bg-gradient-to-r from-red-500 to-red-400'
  }

  // 渲染雷达图
  const renderRadarChart = () => {
    if (radarData.length === 0) return null
    
    const size = 280
    const center = size / 2
    const maxRadius = size / 2 - 40
    const levels = [20, 40, 60, 80, 100]
    
    // 计算每个维度的角度
    const angleStep = (2 * Math.PI) / radarData.length
    const startAngle = -Math.PI / 2 // 从顶部开始
    
    // 生成维度点
    const points = radarData.map((d, i) => {
      const angle = startAngle + i * angleStep
      const r = (d.score / 100) * maxRadius
      return {
        x: center + r * Math.cos(angle),
        y: center + r * Math.sin(angle),
        labelX: center + (maxRadius + 25) * Math.cos(angle),
        labelY: center + (maxRadius + 25) * Math.sin(angle),
        ...d
      }
    })
    
    // 生成多边形路径
    const pathData = points.map((p, i) => 
      `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`
    ).join(' ') + ' Z'
    
    return (
      <svg width={size} height={size} className="mx-auto">
        {/* 背景层 */}
        {levels.map((level) => {
          const r = (level / 100) * maxRadius
          const levelPoints = radarData.map((_, i) => {
            const angle = startAngle + i * angleStep
            return `${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`
          }).join(' ')
          
          return (
            <polygon
              key={level}
              points={levelPoints}
              fill="none"
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          )
        })}
        
        {/* 轴线 */}
        {radarData.map((_, i) => {
          const angle = startAngle + i * angleStep
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={center + maxRadius * Math.cos(angle)}
              y2={center + maxRadius * Math.sin(angle)}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          )
        })}
        
        {/* 数据区域 */}
        <motion.polygon
          points={points.map(p => `${p.x},${p.y}`).join(' ')}
          fill="url(#radarGradient)"
          stroke="rgba(0,245,212,0.8)"
          strokeWidth="2"
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
        />
        
        {/* 渐变定义 */}
        <defs>
          <linearGradient id="radarGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="rgba(0,245,212,0.3)" />
            <stop offset="100%" stopColor="rgba(0,187,249,0.2)" />
          </linearGradient>
        </defs>
        
        {/* 数据点 */}
        {points.map((p, i) => (
          <motion.circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="6"
            fill={p.score >= 60 ? '#00f5d4' : p.score >= 40 ? '#eab308' : '#ef4444'}
            stroke="white"
            strokeWidth="2"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: i * 0.1 }}
          />
        ))}
        
        {/* 维度标签 */}
        {points.map((p, i) => (
          <text
            key={`label-${i}`}
            x={p.labelX}
            y={p.labelY}
            textAnchor="middle"
            dominantBaseline="middle"
            className="text-xs fill-cyber-text font-medium"
          >
            {p.dimension}
          </text>
        ))}
        
        {/* 分数标签 */}
        {points.map((p, i) => (
          <text
            key={`score-${i}`}
            x={p.labelX}
            y={p.labelY + 14}
            textAnchor="middle"
            dominantBaseline="middle"
            className={`text-xs font-bold ${getScoreColor(p.score)}`}
          >
            {p.score.toFixed(0)}
          </text>
        ))}
      </svg>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyber-primary mx-auto mb-4"></div>
          <p className="text-cyber-muted font-chinese">正在计算 CHAOSS 评价...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6">
        <div className="flex items-center gap-2 text-red-400 mb-2">
          <AlertCircle className="w-5 h-5" />
          <h3 className="font-semibold font-chinese">获取评价失败</h3>
        </div>
        <p className="text-red-300">{error}</p>
      </div>
    )
  }

  if (!repoKey || (!data && !loading && !error)) {
    return (
      <div className="text-center py-12 text-cyber-muted">
        <p className="font-chinese">{!repoKey ? '请先选择一个项目' : '暂无评价数据'}</p>
      </div>
    )
  }

  const { final_scores, monthly_scores, report, time_range } = data!

  // 维度名称映射
  const dimensionNames: Record<string, string> = {
    'Activity': '活动度',
    'Contributors': '贡献者',
    'Responsiveness': '响应性',
    'Quality': '代码质量',
    'Risk': '风险',
    'Community Interest': '社区兴趣'
  }

  return (
    <div className="space-y-6">
      {/* 总体评分卡片 */}
      <motion.div 
        className="bg-gradient-to-br from-cyber-card/80 to-cyber-card/40 backdrop-blur-sm rounded-xl border border-cyber-primary/20 p-6 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-gradient-to-br from-cyber-primary/30 to-cyber-secondary/30 rounded-lg">
            <Award className="w-6 h-6 text-cyber-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-cyber-text font-chinese">CHAOSS 社区健康评价</h2>
            <p className="text-sm text-cyber-muted">基于 CHAOSS 标准的多维度综合评估</p>
          </div>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 左侧：雷达图 */}
          <div className="flex flex-col items-center justify-center">
            <div className="relative">
              {renderRadarChart()}
              {/* 中心分数 */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="text-center">
                  <div className={`text-4xl font-bold ${getScoreColor(final_scores.overall_score)}`}>
                    {final_scores.overall_score.toFixed(0)}
                  </div>
                  <div className="text-sm text-cyber-muted">{final_scores.overall_level}</div>
                </div>
              </div>
            </div>
          </div>
          
          {/* 右侧：统计信息 */}
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className={`${getScoreBgColor(final_scores.overall_score)} border rounded-xl p-4`}>
                <div className="text-sm text-cyber-muted mb-1 font-chinese">综合评分</div>
                <div className={`text-3xl font-bold ${getScoreColor(final_scores.overall_score)}`}>
                  {final_scores.overall_score.toFixed(1)}
                </div>
                <div className="text-sm text-cyber-muted mt-1 font-chinese">{final_scores.overall_level}</div>
              </div>
              
              <div className="bg-cyber-surface/50 border border-cyber-border rounded-xl p-4">
                <div className="text-sm text-cyber-muted mb-1 font-chinese">评估周期</div>
                <div className="text-3xl font-bold text-cyber-text">
                  {time_range.evaluated_months}
                </div>
                <div className="text-sm text-cyber-muted mt-1 font-chinese">个月</div>
              </div>
            </div>
            
            <div className="bg-cyber-surface/50 border border-cyber-border rounded-xl p-4">
              <div className="text-sm text-cyber-muted mb-2 font-chinese">数据范围</div>
              <div className="text-lg font-semibold text-cyber-text">
                {time_range.start} ~ {time_range.end}
              </div>
              <div className="flex items-center gap-4 mt-2 text-xs text-cyber-muted">
                <span>共 {time_range.total_months} 个月</span>
                {time_range.valid_months !== undefined && (
                  <span>有效: {time_range.valid_months} 个月</span>
                )}
              </div>
            </div>

            {/* 评价摘要 */}
            {report.summary && (
              <div className="bg-gradient-to-r from-cyber-primary/10 to-cyber-secondary/5 border border-cyber-primary/30 rounded-xl p-4">
                <div className="flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-cyber-primary mt-0.5 flex-shrink-0" />
                  <p className="text-cyber-text text-sm font-chinese leading-relaxed">{report.summary}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* 各维度评分 - 详细卡片 */}
      <motion.div 
        className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h3 className="text-xl font-bold text-cyber-text mb-4 font-chinese flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyber-primary" />
          维度详情分析
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(final_scores.dimensions).map(([dimension, dimData], idx) => {
            const displayName = dimensionNames[dimension] || dimension
            const description = dimensionDescriptions[dimension]
            const isExpanded = expandedDimension === dimension
            
            return (
              <motion.div
                key={dimension}
                className={`border rounded-xl overflow-hidden transition-all ${getScoreBgColor(dimData.score)}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <div 
                  className="p-4 cursor-pointer hover:bg-white/5 transition-colors"
                  onClick={() => setExpandedDimension(isExpanded ? null : dimension)}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-semibold text-cyber-text font-chinese text-lg">{displayName}</h4>
                    <div className="flex items-center gap-2">
                      <span className={`text-2xl font-bold ${getScoreColor(dimData.score)}`}>
                        {dimData.score.toFixed(0)}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-cyber-muted" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-cyber-muted" />
                      )}
                    </div>
                  </div>
                  
                  {/* 进度条 */}
                  <div className="w-full bg-cyber-border/50 rounded-full h-2.5 mb-3">
                    <motion.div
                      className={`h-2.5 rounded-full ${getProgressBarColor(dimData.score)}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${dimData.score}%` }}
                      transition={{ duration: 0.8, delay: idx * 0.1 }}
                    />
                  </div>
                  
                  <div className="flex items-center justify-between text-sm">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${getScoreBgColor(dimData.score)} ${getScoreColor(dimData.score)}`}>
                      {dimData.level}
                    </span>
                    <span className="text-cyber-muted text-xs">
                      {dimData.monthly_count} 个月数据
                    </span>
                  </div>
                </div>
                
                {/* 展开详情 */}
                <AnimatePresence>
                  {isExpanded && description && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="border-t border-white/10"
                    >
                      <div className="p-4 space-y-3">
                        <p className="text-sm text-cyber-text/80 font-chinese">
                          {description.description}
                        </p>
                        
                        <div>
                          <div className="text-xs text-cyber-muted mb-1">相关指标:</div>
                          <div className="flex flex-wrap gap-1">
                            {description.metrics.map((metric, i) => (
                              <span 
                                key={i}
                                className="px-2 py-0.5 bg-cyber-surface/50 rounded-full text-xs text-cyber-text/70"
                              >
                                {metric}
                              </span>
                            ))}
                          </div>
                        </div>
                        
                        {dimData.quality !== undefined && (
                          <div className="text-xs text-cyber-primary/70">
                            <Info className="w-3 h-3 inline mr-1" />
                            数据质量: {(dimData.quality * 100).toFixed(0)}%
                          </div>
                        )}
                        
                        {dimData.outliers_removed > 0 && (
                          <div className="text-xs text-orange-400">
                            <AlertCircle className="w-3 h-3 inline mr-1" />
                            已去除 {dimData.outliers_removed} 个异常值
                          </div>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            )
          })}
        </div>
      </motion.div>

      {/* 月度趋势 */}
      {monthly_scores.length > 0 && (
        <motion.div 
          className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <h3 className="text-xl font-bold text-cyber-text mb-4 font-chinese flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyber-primary" />
            月度评分趋势
          </h3>
          
          <div className="space-y-2">
            {monthly_scores
              .filter(monthData => monthData.score && monthData.score.overall_score > 0.1)
              .slice(-8)
              .reverse()
              .map((monthData, idx) => {
                const prevScore = idx < monthly_scores.length - 1 
                  ? monthly_scores[monthly_scores.length - idx - 2]?.score?.overall_score 
                  : monthData.score.overall_score
                const change = monthData.score.overall_score - (prevScore || monthData.score.overall_score)
                
                return (
                  <motion.div 
                    key={monthData.month} 
                    className="flex items-center justify-between p-3 bg-cyber-surface/30 border border-cyber-border/50 rounded-lg hover:bg-cyber-surface/50 transition-colors"
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.05 }}
                  >
                    <span className="font-medium text-cyber-text w-20">{monthData.month}</span>
                    
                    <div className="flex-1 mx-4">
                      <div className="w-full bg-cyber-border/30 rounded-full h-2">
                        <motion.div
                          className={`h-2 rounded-full ${getProgressBarColor(monthData.score.overall_score)}`}
                          initial={{ width: 0 }}
                          animate={{ width: `${monthData.score.overall_score}%` }}
                          transition={{ duration: 0.5, delay: idx * 0.05 }}
                        />
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-3">
                      <span className={`text-lg font-bold w-12 text-right ${getScoreColor(monthData.score.overall_score)}`}>
                        {monthData.score.overall_score.toFixed(1)}
                      </span>
                      {change !== 0 && (
                        <span className={`text-xs flex items-center gap-0.5 w-14 ${change > 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {change > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {Math.abs(change).toFixed(1)}
                        </span>
                      )}
                    </div>
                  </motion.div>
                )
              })}
          </div>
        </motion.div>
      )}

      {/* 改进建议 */}
      {report.recommendations && report.recommendations.length > 0 && (
        <motion.div 
          className="bg-gradient-to-br from-green-500/10 to-cyber-card/50 backdrop-blur-sm rounded-xl border border-green-500/20 p-6 shadow-lg"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h3 className="text-xl font-bold text-cyber-text mb-4 flex items-center gap-2 font-chinese">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            改进建议
          </h3>
          <ul className="space-y-3">
            {report.recommendations.map((rec, index) => (
              <motion.li 
                key={index} 
                className="flex items-start gap-3 p-3 bg-green-500/5 rounded-lg border border-green-500/10"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + index * 0.1 }}
              >
                <span className="w-6 h-6 flex items-center justify-center bg-green-500/20 text-green-400 rounded-full text-sm font-bold flex-shrink-0">
                  {index + 1}
                </span>
                <span className="text-cyber-text font-chinese">{rec}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      )}
    </div>
  )
}
