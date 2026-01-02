import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Activity, TrendingUp, TrendingDown, Minus, Loader2, AlertCircle, ArrowUp, ArrowDown } from 'lucide-react'

interface TrendData {
  direction: string
  growth_rate: number
  volatility: string
  coefficient_of_variation: number
  first_half_avg: number
  second_half_avg: number
  current_value: number
  data_points: number
}

interface TrendAnalysisPanelProps {
  repoKey: string
}

export default function TrendAnalysisPanel({ repoKey }: TrendAnalysisPanelProps) {
  const [trends, setTrends] = useState<Record<string, TrendData> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchTrends()
  }, [repoKey])

  const fetchTrends = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/api/analysis/trend/${encodeURIComponent(repoKey)}`)
      const data = await response.json()
      
      if (data.error) {
        setError(data.error)
      } else {
        setTrends(data.trends || {})
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取趋势分析失败')
    } finally {
      setLoading(false)
    }
  }

  const getDirectionIcon = (direction: string) => {
    switch (direction) {
      case '上升':
        return <ArrowUp className="w-5 h-5 text-green-400" />
      case '下降':
        return <ArrowDown className="w-5 h-5 text-red-400" />
      default:
        return <Minus className="w-5 h-5 text-gray-400" />
    }
  }

  const getVolatilityColor = (volatility: string) => {
    switch (volatility) {
      case '高':
        return 'text-red-400'
      case '中':
        return 'text-yellow-400'
      default:
        return 'text-green-400'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
        <span className="ml-3 text-gray-400">正在分析趋势...</span>
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

  if (!trends || Object.keys(trends).length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
        <p>暂无趋势数据</p>
      </div>
    )
  }

  const sortedTrends = Object.entries(trends).sort((a, b) => 
    Math.abs(b[1].growth_rate) - Math.abs(a[1].growth_rate)
  )

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white mb-2">指标趋势分析</h3>
        <p className="text-sm text-gray-400">
          分析所有指标的历史趋势，包括增长率、波动性等
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sortedTrends.map(([metricName, trend]) => (
          <motion.div
            key={metricName}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gray-700/50 border border-gray-600 rounded-lg p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-white font-semibold">{metricName}</h4>
              {getDirectionIcon(trend.direction)}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">趋势方向</span>
                <span className={`font-semibold ${
                  trend.direction === '上升' ? 'text-green-400' :
                  trend.direction === '下降' ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {trend.direction}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">增长率</span>
                <span className={`font-semibold ${
                  trend.growth_rate > 0 ? 'text-green-400' : 
                  trend.growth_rate < 0 ? 'text-red-400' : 'text-gray-400'
                }`}>
                  {trend.growth_rate > 0 ? '+' : ''}{trend.growth_rate.toFixed(2)}%
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">波动性</span>
                <span className={`font-semibold ${getVolatilityColor(trend.volatility)}`}>
                  {trend.volatility}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">当前值</span>
                <span className="text-white font-mono">{trend.current_value.toFixed(2)}</span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">数据点</span>
                <span className="text-gray-300">{trend.data_points} 个月</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}














