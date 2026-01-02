import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, ComposedChart
} from 'recharts'
import { TrendingUp, AlertCircle, Loader2, Plus, X, Info, Sparkles } from 'lucide-react'

interface MetricResult {
  historical: Record<string, number>
  forecast: Record<string, number>
  confidence: number
  trend: {
    direction: string
    strength: string
    volatility: string
  }
  error?: string
}

interface MultiMetricPredictionProps {
  repoKey: string
  availableMetrics: string[]
  onClose?: () => void
}

const METRIC_COLORS = [
  { line: '#3b82f6', area: 'rgba(59, 130, 246, 0.2)' },  // 蓝色
  { line: '#10b981', area: 'rgba(16, 185, 129, 0.2)' },  // 绿色
  { line: '#f59e0b', area: 'rgba(245, 158, 11, 0.2)' },  // 橙色
  { line: '#ef4444', area: 'rgba(239, 68, 68, 0.2)' },   // 红色
]

export default function MultiMetricPrediction({ 
  repoKey, 
  availableMetrics,
  onClose 
}: MultiMetricPredictionProps) {
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([])
  const [results, setResults] = useState<Record<string, MetricResult>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forecastMonths, setForecastMonths] = useState(6)
  const [showMetricSelector, setShowMetricSelector] = useState(true)

  // 获取预测
  const fetchPredictions = async () => {
    if (selectedMetrics.length === 0) return

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/predict/${encodeURIComponent(repoKey)}/multi-metric`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric_names: selectedMetrics,
          forecast_months: forecastMonths
        })
      })

      const data = await response.json()
      if (data.error) {
        setError(data.error)
      } else if (data.results && Object.keys(data.results).length > 0) {
        setResults(data.results)
        setShowMetricSelector(false)
      } else {
        setError('预测结果为空')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '预测失败')
    } finally {
      setLoading(false)
    }
  }

  // 过滤出成功的结果（排除有error的）
  const validResults = useMemo(() => {
    const valid: Record<string, MetricResult> = {}
    Object.entries(results).forEach(([metric, result]) => {
      if (!result.error && result.historical && result.forecast) {
        valid[metric] = result
      }
    })
    return valid
  }, [results])

  // 成功预测的指标列表
  const validMetrics = useMemo(() => {
    return selectedMetrics.filter(m => validResults[m])
  }, [selectedMetrics, validResults])

  // 合并图表数据
  const chartData = useMemo(() => {
    if (Object.keys(validResults).length === 0) return []

    const allMonths = new Set<string>()
    
    // 收集所有月份（只从有效结果中收集）
    Object.values(validResults).forEach(result => {
      if (result.historical) {
        Object.keys(result.historical).forEach(m => allMonths.add(m))
      }
      if (result.forecast) {
        Object.keys(result.forecast).forEach(m => allMonths.add(m))
      }
    })

    const sortedMonths = Array.from(allMonths).sort()
    
    // 找出历史数据的最后一个月
    let lastHistoricalMonth = ''
    Object.values(validResults).forEach(result => {
      if (result.historical) {
        const months = Object.keys(result.historical).sort()
        if (months.length > 0) {
          const last = months[months.length - 1]
          if (last > lastHistoricalMonth) lastHistoricalMonth = last
        }
      }
    })

    return sortedMonths.map(month => {
      const point: any = {
        month,
        displayMonth: month.slice(2),
        isForecast: month > lastHistoricalMonth
      }

      Object.entries(validResults).forEach(([metric, result]) => {
        if (result.historical && result.historical[month] !== undefined) {
          point[`${metric}_hist`] = result.historical[month]
        }
        if (result.forecast && result.forecast[month] !== undefined) {
          point[`${metric}_pred`] = result.forecast[month]
        }
      })

      return point
    })
  }, [validResults])

  // 找出分界点
  const dividerMonth = useMemo(() => {
    let lastHist = ''
    Object.values(validResults).forEach(result => {
      if (result.historical) {
        const months = Object.keys(result.historical).sort()
        if (months.length > 0) {
          const last = months[months.length - 1]
          if (last > lastHist) lastHist = last
        }
      }
    })
    return lastHist.slice(2)
  }, [validResults])

  const toggleMetric = (metric: string) => {
    if (selectedMetrics.includes(metric)) {
      setSelectedMetrics(selectedMetrics.filter(m => m !== metric))
    } else if (selectedMetrics.length < 4) {
      setSelectedMetrics([...selectedMetrics, metric])
    }
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null

    return (
      <div className="bg-gray-900/95 border border-gray-700 rounded-lg p-4 shadow-xl backdrop-blur-sm">
        <p className="text-white font-semibold mb-3 border-b border-gray-700 pb-2">
          20{label}
        </p>
        <div className="space-y-2">
          {payload.map((entry: any, index: number) => {
            const isHistory = entry.dataKey.includes('_hist')
            const metricName = entry.dataKey.replace('_hist', '').replace('_pred', '')
            return (
              <div key={index} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  <span className="text-gray-300 text-sm">
                    {metricName}
                    <span className="text-xs text-gray-500 ml-1">
                      {isHistory ? '(历史)' : '(预测)'}
                    </span>
                  </span>
                </div>
                <span className="text-white font-mono text-sm">
                  {entry.value?.toFixed(2)}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-gray-800/80 to-gray-900/80 rounded-xl p-6 border border-gray-700/50 backdrop-blur-sm"
    >
      {/* 标题 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-blue-500/30 to-purple-500/30 rounded-lg">
            <TrendingUp className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-white">多指标预测对比</h3>
            <p className="text-sm text-gray-400">同时分析多个指标的预测趋势</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        )}
      </div>

      {/* 指标选择器 */}
      <AnimatePresence>
        {showMetricSelector && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6"
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-gray-300">
                选择指标（最多4个）
              </h4>
              <span className="text-xs text-gray-500">
                已选 {selectedMetrics.length}/4
              </span>
            </div>
            
            <div className="flex flex-wrap gap-2 mb-4">
              {availableMetrics && availableMetrics.length > 0 ? (
                availableMetrics.map((metric, index) => (
                  <button
                    key={metric}
                    onClick={() => toggleMetric(metric)}
                    disabled={!selectedMetrics.includes(metric) && selectedMetrics.length >= 4}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      selectedMetrics.includes(metric)
                        ? 'text-white shadow-lg'
                        : 'bg-gray-700/50 text-gray-400 hover:bg-gray-700 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed'
                    }`}
                    style={selectedMetrics.includes(metric) ? {
                      backgroundColor: METRIC_COLORS[selectedMetrics.indexOf(metric) % 4].line
                    } : {}}
                  >
                    {metric}
                  </button>
                ))
              ) : (
                <div className="text-gray-400 text-sm py-4">
                  <Info className="w-5 h-5 inline mr-2" />
                  暂无可用指标，请确保数据已加载
                </div>
              )}
            </div>

            <div className="flex items-center gap-4">
              <select
                value={forecastMonths}
                onChange={(e) => setForecastMonths(Number(e.target.value))}
                className="bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={3}>预测3个月</option>
                <option value={6}>预测6个月</option>
                <option value={9}>预测9个月</option>
                <option value={12}>预测12个月</option>
              </select>

              <button
                onClick={fetchPredictions}
                disabled={selectedMetrics.length === 0 || loading}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-lg transition-all disabled:cursor-not-allowed"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                开始预测
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 错误提示 */}
      {error && (
        <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <span className="text-red-300">{error}</span>
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
          <span className="ml-3 text-white">正在生成多指标预测...</span>
        </div>
      )}

      {/* 所有预测失败的提示 */}
      {!loading && Object.keys(results).length > 0 && validMetrics.length === 0 && (
        <div className="p-6 bg-red-500/20 border border-red-500/50 rounded-lg text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h4 className="text-lg font-semibold text-red-300 mb-2">所有指标预测失败</h4>
          <p className="text-sm text-red-300/70 mb-4">
            {selectedMetrics.map(m => `${m}: ${results[m]?.error || '未知错误'}`).join(', ')}
          </p>
          <button
            onClick={() => {
              setResults({})
              setShowMetricSelector(true)
            }}
            className="px-4 py-2 bg-red-500/30 hover:bg-red-500/50 text-white rounded-lg transition-colors"
          >
            重新选择指标
          </button>
        </div>
      )}

      {/* 图表 */}
      {!loading && Object.keys(results).length > 0 && validMetrics.length > 0 && chartData.length > 0 && (
        <>
          {/* 错误提示 - 如果某些指标预测失败 */}
          {selectedMetrics.some(m => results[m]?.error) && (
            <div className="mb-4 p-3 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
              <div className="text-sm text-yellow-300">
                部分指标预测失败: {selectedMetrics.filter(m => results[m]?.error).map(m => `${m} (${results[m]?.error})`).join(', ')}
              </div>
            </div>
          )}

          {/* 置信度指示器 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {validMetrics.map((metric, index) => {
              const result = validResults[metric]
              if (!result) return null
              return (
                <div
                  key={metric}
                  className="bg-gray-700/30 rounded-lg p-3 border-l-4"
                  style={{ borderColor: METRIC_COLORS[index % 4].line }}
                >
                  <div className="text-xs text-gray-400 mb-1">{metric}</div>
                  <div className="flex items-center justify-between">
                    <span className="text-lg font-bold text-white">
                      {((result.confidence || 0) * 100).toFixed(0)}%
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      result.trend?.direction === '上升' 
                        ? 'bg-green-500/20 text-green-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {result.trend?.direction || '稳定'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 返回选择按钮 */}
          <div className="flex justify-between items-center mb-4">
            <button
              onClick={() => setShowMetricSelector(true)}
              className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              修改指标选择
            </button>
          </div>

          {/* 双轴图表 */}
          <div className="h-[450px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 40 }}>
                <defs>
                  {validMetrics.map((metric, index) => (
                    <linearGradient 
                      key={`gradient-${metric}`} 
                      id={`gradient-${metric}`} 
                      x1="0" y1="0" x2="0" y2="1"
                    >
                      <stop offset="5%" stopColor={METRIC_COLORS[index % 4].line} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={METRIC_COLORS[index % 4].line} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>

                <CartesianGrid 
                  strokeDasharray="3 3" 
                  stroke="rgba(45, 58, 79, 0.5)"
                  vertical={false}
                />

                <XAxis 
                  dataKey="displayMonth"
                  stroke="#8b97a8"
                  tick={{ fill: '#8b97a8', fontSize: 10 }}
                  tickLine={{ stroke: '#2d3a4f' }}
                  axisLine={{ stroke: '#2d3a4f' }}
                  interval="preserveStartEnd"
                />

                {/* 左Y轴 */}
                <YAxis
                  yAxisId="left"
                  stroke="#8b97a8"
                  tick={{ fill: '#8b97a8', fontSize: 10 }}
                  tickLine={{ stroke: '#2d3a4f' }}
                  axisLine={{ stroke: '#2d3a4f' }}
                />

                {/* 右Y轴（如果有多个指标且数值差异大） */}
                {validMetrics.length > 1 && (
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#8b97a8"
                    tick={{ fill: '#8b97a8', fontSize: 10 }}
                    tickLine={{ stroke: '#2d3a4f' }}
                    axisLine={{ stroke: '#2d3a4f' }}
                  />
                )}

                <Tooltip content={<CustomTooltip />} />

                <Legend 
                  wrapperStyle={{ paddingTop: '20px' }}
                  formatter={(value: string) => {
                    const name = value.replace('_hist', '').replace('_pred', '')
                    const type = value.includes('_hist') ? '历史' : '预测'
                    return <span className="text-gray-300">{name} ({type})</span>
                  }}
                />

                {/* 分界线 */}
                {dividerMonth && (
                  <ReferenceLine
                    x={dividerMonth}
                    yAxisId="left"
                    stroke="#ef4444"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    label={{ 
                      value: "预测起点", 
                      position: "top", 
                      fill: "#ef4444",
                      fontSize: 12
                    }}
                  />
                )}

                {/* 历史数据线 - 实线 */}
                {validMetrics.map((metric, index) => (
                  <Area
                    key={`hist-${metric}`}
                    yAxisId={index === 0 ? "left" : (validMetrics.length > 1 ? "right" : "left")}
                    type="monotone"
                    dataKey={`${metric}_hist`}
                    stroke={METRIC_COLORS[index % 4].line}
                    strokeWidth={2}
                    fill={`url(#gradient-${metric})`}
                    name={`${metric}_hist`}
                    dot={{ r: 2, fill: METRIC_COLORS[index % 4].line }}
                    activeDot={{ r: 4 }}
                    connectNulls
                  />
                ))}

                {/* 预测数据线 - 虚线 */}
                {validMetrics.map((metric, index) => (
                  <Line
                    key={`pred-${metric}`}
                    yAxisId={index === 0 ? "left" : (validMetrics.length > 1 ? "right" : "left")}
                    type="monotone"
                    dataKey={`${metric}_pred`}
                    stroke={METRIC_COLORS[index % 4].line}
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    name={`${metric}_pred`}
                    dot={{ r: 3, fill: METRIC_COLORS[index % 4].line, strokeWidth: 2, stroke: '#1f2937' }}
                    activeDot={{ r: 5 }}
                    connectNulls
                  />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* 图例说明 */}
          <div className="mt-4 p-3 bg-gray-700/30 rounded-lg">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Info className="w-4 h-4" />
              <span>实线代表历史数据，虚线代表预测数据。红色分界线标记预测起点。</span>
            </div>
          </div>
        </>
      )}
    </motion.div>
  )
}

