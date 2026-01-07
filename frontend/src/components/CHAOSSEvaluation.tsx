import { useState, useEffect } from 'react'
import { Award, AlertCircle, CheckCircle2 } from 'lucide-react'

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
  _raw_overall_score?: number  // 原始分数（用于研究和解释）
  _percentile?: number  // 百分位排名（0-100）
  dimensions: Record<string, {
    score: number
    level: string
    monthly_count: number
    outliers_removed: number
    quality?: number  // 数据质量得分
  }>
}

interface CHAOSSData {
  repo_key: string
  time_range: {
    start: string
    end: string
    total_months: number
    evaluated_months: number
    valid_months?: number  // 实际有评分的月份数
    repo_created_month?: string  // 仓库创建月份
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

export default function CHAOSSEvaluation({ repoKey }: CHAOSSEvaluationProps) {
  const [data, setData] = useState<CHAOSSData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!repoKey) {
      setLoading(false)
      setData(null)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)

    // 支持两种格式：owner/repo 或 owner_repo
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
          throw new Error(result.error)
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

  const getProgressBarColor = (score: number) => {
    if (score >= 80) return 'bg-green-500'
    if (score >= 60) return 'bg-cyber-primary'
    if (score >= 40) return 'bg-yellow-500'
    if (score >= 20) return 'bg-orange-500'
    return 'bg-red-500'
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

  if (!repoKey) {
    return (
      <div className="text-center py-12 text-cyber-muted">
        <p className="font-chinese">请先选择一个项目</p>
      </div>
    )
  }

  if (!data && !loading && !error) {
    return (
      <div className="text-center py-12 text-cyber-muted">
        <p className="font-chinese">暂无评价数据</p>
      </div>
    )
  }

  const { final_scores, monthly_scores, report, time_range } = data!

  return (
    <div className="space-y-6">
      {/* 总体评分卡片 */}
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg">
        <div className="flex items-center gap-3 mb-4">
          <Award className="w-6 h-6 text-cyber-primary" />
          <h2 className="text-2xl font-bold text-cyber-text font-chinese">CHAOSS 社区健康评价</h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className={`${getScoreBgColor(final_scores.overall_score)} border rounded-xl p-4`}>
            <div className="text-sm text-cyber-muted mb-1 font-chinese">综合评分</div>
            <div className={`text-3xl font-bold ${getScoreColor(final_scores.overall_score)}`}>
              {final_scores.overall_score.toFixed(1)}
            </div>
            <div className="text-sm text-cyber-muted mt-1 font-chinese">{final_scores.overall_level}</div>
            {/* 显示百分位排名 */}
            {final_scores._percentile !== undefined && final_scores._percentile !== null && (
              <div className="text-xs text-cyber-muted mt-2 pt-2 border-t border-cyber-border/50 font-chinese">
                排名前 {final_scores._percentile.toFixed(1)}%
              </div>
            )}
          </div>
          
          <div className="bg-cyber-surface/50 border border-cyber-border rounded-xl p-4">
            <div className="text-sm text-cyber-muted mb-1 font-chinese">评估月份数</div>
            <div className="text-3xl font-bold text-cyber-text">
              {time_range.evaluated_months}
            </div>
            <div className="text-sm text-cyber-muted mt-1 font-chinese">共 {time_range.total_months} 个月数据</div>
            {time_range.valid_months !== undefined && (
              <div className="text-xs text-cyber-muted mt-1 font-chinese">
                有效评分: {time_range.valid_months} 个月
              </div>
            )}
          </div>
          
          <div className="bg-cyber-surface/50 border border-cyber-border rounded-xl p-4">
            <div className="text-sm text-cyber-muted mb-1 font-chinese">数据范围</div>
            <div className="text-lg font-semibold text-cyber-text">
              {time_range.start} ~ {time_range.end}
            </div>
            {time_range.repo_created_month && (
              <div className="text-xs text-cyber-muted mt-1 font-chinese">
                创建于: {time_range.repo_created_month}
              </div>
            )}
          </div>
        </div>

        {/* 评价摘要 */}
        {report.summary && (
          <div className="bg-cyber-primary/10 border border-cyber-primary/30 rounded-xl p-4 mb-4">
            <p className="text-cyber-primary font-medium font-chinese">{report.summary}</p>
          </div>
        )}
      </div>

      {/* 各维度评分 */}
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg">
        <h3 className="text-xl font-bold text-cyber-text mb-4 font-chinese">维度评分</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(final_scores.dimensions).map(([dimension, dimData]) => {
            // 维度名称映射（英文转中文）
            const dimensionNames: Record<string, string> = {
              'Activity': '活动度',
              'Contributors': '贡献者',
              'Responsiveness': '响应性',
              'Quality': '代码质量',
              'Risk': '风险',
              'Community Interest': '社区兴趣'
            }
            const displayName = dimensionNames[dimension] || dimension
            
            return (
            <div
              key={dimension}
              className={`border rounded-xl p-4 ${getScoreBgColor(dimData.score)}`}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-cyber-text font-chinese">{displayName}</h4>
                <span className={`text-2xl font-bold ${getScoreColor(dimData.score)}`}>
                  {dimData.score.toFixed(1)}
                </span>
              </div>
              <div className="text-sm text-cyber-muted space-y-1 font-chinese">
                <div>等级: {dimData.level}</div>
                <div>基于 {dimData.monthly_count} 个月的数据</div>
                {dimData.quality !== undefined && (
                  <div className="text-cyber-primary/70">
                    数据质量: {(dimData.quality * 100).toFixed(0)}%
                  </div>
                )}
                {dimData.outliers_removed > 0 && (
                  <div className="text-orange-400">
                    已去除 {dimData.outliers_removed} 个异常值
                  </div>
                )}
              </div>
            </div>
            )
          })}
        </div>
      </div>

      {/* 月度评分趋势 */}
      {monthly_scores.length > 0 && (
        <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg">
          <h3 className="text-xl font-bold text-cyber-text mb-4 font-chinese">月度评分趋势</h3>
          <div className="space-y-2">
            {monthly_scores
              .filter(monthData => monthData.score && monthData.score.overall_score > 0.1) // 过滤掉得分过低（可能是缺失数据）的月份
              .slice(-6)
              .reverse()
              .map((monthData) => (
              <div key={monthData.month} className="flex items-center justify-between p-3 bg-cyber-surface/50 border border-cyber-border rounded-lg">
                <span className="font-medium text-cyber-text">{monthData.month}</span>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${getScoreColor(monthData.score.overall_score)}`}>
                      {monthData.score.overall_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="w-32 bg-cyber-border rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${getProgressBarColor(monthData.score.overall_score)}`}
                      style={{ width: `${monthData.score.overall_score}%` }}
                    ></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 改进建议 */}
      {report.recommendations && report.recommendations.length > 0 && (
        <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-6 shadow-lg">
          <h3 className="text-xl font-bold text-cyber-text mb-4 flex items-center gap-2 font-chinese">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            改进建议
          </h3>
          <ul className="space-y-2">
            {report.recommendations.map((rec, index) => (
              <li key={index} className="flex items-start gap-2 text-cyber-text font-chinese">
                <span className="text-cyber-primary mt-1">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

