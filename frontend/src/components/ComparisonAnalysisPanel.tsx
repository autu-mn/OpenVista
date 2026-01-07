import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Zap, Loader2, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface ComparisonData {
  current_avg: number
  benchmark_avg: number
  relative_performance: number
  performance_level: string
  current_value: number
  max: number
  min: number
}

interface ComparisonAnalysisPanelProps {
  repoKey: string
}

export default function ComparisonAnalysisPanel({ repoKey }: ComparisonAnalysisPanelProps) {
  const [comparison, setComparison] = useState<Record<string, ComparisonData> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [comparedWith, setComparedWith] = useState(0)

  useEffect(() => {
    fetchComparison()
  }, [repoKey])

  const fetchComparison = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/api/analysis/comparison/${encodeURIComponent(repoKey)}`)
      const data = await response.json()
      
      if (data.error) {
        setError(data.error)
      } else {
        setComparison(data.comparison || {})
        setComparedWith(data.compared_with || 0)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取对比分析失败')
    } finally {
      setLoading(false)
    }
  }

  const getPerformanceIcon = (level: string) => {
    switch (level) {
      case '高于平均':
        return <TrendingUp className="w-5 h-5 text-green-400" />
      case '低于平均':
        return <TrendingDown className="w-5 h-5 text-red-400" />
      default:
        return <Minus className="w-5 h-5 text-gray-400" />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
        <span className="ml-3 text-gray-400">正在对比分析...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
        <div className="flex items-center space-x-3 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  if (!comparison || Object.keys(comparison).length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Zap className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p>暂无对比数据（需要至少2个仓库的数据）</p>
      </div>
    )
  }

  const sortedComparison = Object.entries(comparison).sort((a, b) => 
    Math.abs(b[1].relative_performance) - Math.abs(a[1].relative_performance)
  )

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">对比分析</h3>
        <p className="text-sm text-gray-400">
          与 {comparedWith} 个其他仓库的平均水平对比
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sortedComparison.map(([metricName, comp]) => (
          <motion.div
            key={metricName}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-700/50 border border-gray-600 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold">{metricName}</h4>
              {getPerformanceIcon(comp.performance_level)}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">当前平均值</span>
                <span className="text-white font-mono">{comp.current_avg.toFixed(2)}</span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">行业平均值</span>
                <span className="text-gray-300 font-mono">{comp.benchmark_avg.toFixed(2)}</span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">相对表现</span>
                <span className={`font-semibold ${
                  comp.relative_performance > 10 ? 'text-green-400' :
                  comp.relative_performance < -10 ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {comp.relative_performance > 0 ? '+' : ''}{comp.relative_performance.toFixed(2)}%
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">表现水平</span>
                <span className={`font-semibold ${
                  comp.performance_level === '高于平均' ? 'text-green-400' :
                  comp.performance_level === '低于平均' ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {comp.performance_level}
                </span>
              </div>

              <div className="mt-3 pt-3 border-t border-gray-600">
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>当前值: {comp.current_value.toFixed(2)}</span>
                  <span>范围: {comp.min.toFixed(2)} ~ {comp.max.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}















