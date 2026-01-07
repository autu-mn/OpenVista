import { useState, useEffect, useMemo, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  TrendingUp, TrendingDown, Loader2, AlertCircle, RefreshCw,
  ChevronDown, ChevronUp, Sparkles, BarChart3, Info
} from 'lucide-react'

interface PredictionData {
  forecast: Record<string, number>
  confidence: number
  reasoning: string
  trend?: string
  change_percent?: number
  historical_length?: number
}

interface ForecastResult {
  available: boolean
  predictions?: Record<string, PredictionData>
  forecast_months?: number
  historical_months?: number
  model?: string
  last_month?: string
  error?: string
  hint?: string
}

interface ForecastChartProps {
  repoKey: string
  historicalData?: Record<string, any>  // metric -> data (可能是 {raw: {...}} 或直接 {...})
}

// 16个核心指标
const ALL_METRICS = [
  'OpenRank', '活跃度', 'Star数', 'Fork数', '关注度', '参与者数',
  '新增贡献者', '贡献者', '不活跃贡献者', '总线因子', '新增Issue',
  '关闭Issue', 'Issue评论', '变更请求', 'PR接受数', 'PR审查'
]

// 指标颜色映射
const METRIC_COLORS: Record<string, string> = {
  'OpenRank': '#00f5d4',
  '活跃度': '#00bbf9',
  'Star数': '#fee440',
  'Fork数': '#9b5de5',
  '关注度': '#f15bb5',
  '参与者数': '#4ecdc4',
  '新增贡献者': '#45b7d1',
  '贡献者': '#96ceb4',
  '不活跃贡献者': '#ff6b6b',
  '总线因子': '#ffeaa7',
  '新增Issue': '#fd79a8',
  '关闭Issue': '#00b894',
  'Issue评论': '#e17055',
  '变更请求': '#74b9ff',
  'PR接受数': '#a29bfe',
  'PR审查': '#dfe6e9',
}

// 重要指标（默认显示）
const IMPORTANT_METRICS = ['OpenRank', '活跃度', 'Star数', 'Fork数', '新增Issue', '关闭Issue']

// tooltip 状态类型
interface TooltipState {
  show: boolean
  x: number
  y: number
  month: string
  value: number
  type: 'historical' | 'forecast'
}

export default function ForecastChart({ repoKey, historicalData }: ForecastChartProps) {
  const [loading, setLoading] = useState(false)
  const [forecast, setForecast] = useState<ForecastResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedMetric, setSelectedMetric] = useState<string>('OpenRank')
  const [showAllMetrics, setShowAllMetrics] = useState(false)
  const [forecastMonths, setForecastMonths] = useState(12)
  const [tooltip, setTooltip] = useState<TooltipState>({ show: false, x: 0, y: 0, month: '', value: 0, type: 'historical' })
  const chartRef = useRef<SVGSVGElement>(null)

  const fetchForecast = async () => {
    if (!repoKey) return
    
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(
        `/api/forecast/${encodeURIComponent(repoKey)}?months=${forecastMonths}`
      )
      const data = await response.json()
      
      if (!response.ok) {
        throw new Error(data.error || '预测失败')
      }
      
      console.log('[ForecastChart] 预测数据:', data)
      setForecast(data)
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '预测服务不可用')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchForecast()
  }, [repoKey, forecastMonths])

  // 提取历史数据
  const extractHistoricalData = (metricName: string): Record<string, number> => {
    if (!historicalData) return {}
    
    // 尝试多种键名格式
    const keysToTry = [
      `opendigger_${metricName}`,
      metricName,
      metricName.replace(/\s/g, '')
    ]
    
    for (const key of keysToTry) {
      const data = historicalData[key]
      if (data) {
        // 如果是 {raw: {...}} 格式
        if (typeof data === 'object' && data.raw && typeof data.raw === 'object') {
          return data.raw as Record<string, number>
        }
        // 如果直接是 {month: value} 格式
        if (typeof data === 'object') {
          // 过滤出有效的月份数据
          const result: Record<string, number> = {}
          for (const [k, v] of Object.entries(data)) {
            if (k.length === 7 && k[4] === '-' && typeof v === 'number') {
              result[k] = v
            }
          }
          if (Object.keys(result).length > 0) return result
        }
      }
    }
    
    return {}
  }

  // 构建图表数据
  const chartData = useMemo(() => {
    if (!forecast?.predictions || !selectedMetric) return null
    
    const prediction = forecast.predictions[selectedMetric]
    if (!prediction?.forecast) return null
    
    // 获取历史数据
    const historical = extractHistoricalData(selectedMetric)
    const forecastData = prediction.forecast
    
    console.log(`[ForecastChart] ${selectedMetric} 历史数据:`, Object.keys(historical).length, '条')
    console.log(`[ForecastChart] ${selectedMetric} 预测数据:`, Object.keys(forecastData).length, '条')
    
    // 合并所有月份
    const allMonths = new Set([
      ...Object.keys(historical),
      ...Object.keys(forecastData)
    ])
    
    const sortedMonths = Array.from(allMonths)
      .filter(m => m.length === 7 && m[4] === '-')
      .sort()
    
    // 取最近的数据
    const recentMonths = sortedMonths.slice(-48)
    
    // 找出历史和预测的分界点
    const forecastStartIndex = recentMonths.findIndex(m => forecastData[m] !== undefined)
    
    return {
      months: recentMonths,
      historical: recentMonths.map(m => historical[m] ?? null),
      forecast: recentMonths.map(m => forecastData[m] ?? null),
      forecastStartIndex: forecastStartIndex >= 0 ? forecastStartIndex : recentMonths.length
    }
  }, [forecast, selectedMetric, historicalData])

  // 计算 Y 轴范围和刻度
  const yAxisConfig = useMemo(() => {
    if (!chartData) return { min: 0, max: 100, ticks: [0, 25, 50, 75, 100] }
    
    const allValues = [
      ...chartData.historical.filter((v): v is number => v !== null),
      ...chartData.forecast.filter((v): v is number => v !== null)
    ]
    
    if (allValues.length === 0) return { min: 0, max: 100, ticks: [0, 25, 50, 75, 100] }
    
    const dataMin = Math.min(...allValues)
    const dataMax = Math.max(...allValues)
    
    // 计算合适的范围
    const range = dataMax - dataMin || dataMax * 0.5 || 10
    const padding = range * 0.15
    
    let min = Math.max(0, dataMin - padding)
    let max = dataMax + padding
    
    // 计算漂亮的刻度值
    const tickCount = 5
    const rawStep = (max - min) / (tickCount - 1)
    
    // 找到最接近的"漂亮"步长
    const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)))
    const normalized = rawStep / magnitude
    let niceStep: number
    
    if (normalized <= 1) niceStep = magnitude
    else if (normalized <= 2) niceStep = 2 * magnitude
    else if (normalized <= 5) niceStep = 5 * magnitude
    else niceStep = 10 * magnitude
    
    // 调整范围使刻度值更整齐
    min = Math.floor(min / niceStep) * niceStep
    max = Math.ceil(max / niceStep) * niceStep
    
    // 生成刻度值
    const ticks: number[] = []
    for (let v = min; v <= max + niceStep * 0.1; v += niceStep) {
      ticks.push(Math.round(v * 1000) / 1000)
    }
    
    return { min, max, ticks }
  }, [chartData])

  // 格式化数值
  const formatValue = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    if (value >= 100) return value.toFixed(0)
    if (value >= 10) return value.toFixed(1)
    return value.toFixed(2)
  }

  // 格式化月份
  const formatMonth = (month: string): string => {
    const [year, mon] = month.split('-')
    return `${year.slice(2)}-${mon}`
  }

  // 处理鼠标事件
  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>, index: number, month: string, value: number, type: 'historical' | 'forecast') => {
    const rect = chartRef.current?.getBoundingClientRect()
    if (!rect) return
    
    setTooltip({
      show: true,
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      month,
      value,
      type
    })
  }

  const handleMouseLeave = () => {
    setTooltip(prev => ({ ...prev, show: false }))
  }

  // 渲染图表
  const renderChart = () => {
    if (!chartData || chartData.months.length === 0) {
      return (
        <div className="flex items-center justify-center h-80 text-cyber-muted">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>暂无数据</p>
          </div>
        </div>
      )
    }

    const { months, historical, forecast: forecastValues, forecastStartIndex } = chartData
    const { min: yMin, max: yMax, ticks } = yAxisConfig
    
    const chartWidth = 900
    const chartHeight = 350
    const padding = { top: 30, right: 50, bottom: 60, left: 70 }
    const innerWidth = chartWidth - padding.left - padding.right
    const innerHeight = chartHeight - padding.top - padding.bottom

    const xScale = (index: number) => padding.left + (index / Math.max(months.length - 1, 1)) * innerWidth
    const yScale = (value: number) => chartHeight - padding.bottom - ((value - yMin) / (yMax - yMin || 1)) * innerHeight

    // 生成路径数据
    const buildPath = (data: (number | null)[], startFromPrevious: boolean = false, prevEndIndex: number = -1, prevEndValue: number | null = null) => {
      const segments: string[] = []
      let inPath = false
      
      if (startFromPrevious && prevEndIndex >= 0 && prevEndValue !== null) {
        segments.push(`M ${xScale(prevEndIndex)} ${yScale(prevEndValue)}`)
        inPath = true
      }
      
      data.forEach((value, i) => {
        if (value === null) {
          inPath = false
          return
        }
        
        if (!inPath) {
          segments.push(`M ${xScale(i)} ${yScale(value)}`)
          inPath = true
        } else {
          segments.push(`L ${xScale(i)} ${yScale(value)}`)
        }
      })
      
      return segments.join(' ')
    }

    // 历史数据路径
    const historicalPath = buildPath(historical)
    
    // 找到历史数据的最后一个点
    let lastHistoricalIndex = -1
    let lastHistoricalValue: number | null = null
    for (let i = historical.length - 1; i >= 0; i--) {
      if (historical[i] !== null) {
        lastHistoricalIndex = i
        lastHistoricalValue = historical[i]
        break
      }
    }
    
    // 预测数据路径（从历史最后一点开始）
    const forecastPath = buildPath(forecastValues, true, lastHistoricalIndex, lastHistoricalValue)

    const metricColor = METRIC_COLORS[selectedMetric] || '#00f5d4'

    // X轴标签：每隔一定数量显示
    const xLabelInterval = Math.max(1, Math.ceil(months.length / 12))

    return (
      <div className="relative overflow-x-auto">
        <svg 
          ref={chartRef}
          width={chartWidth} 
          height={chartHeight} 
          className="min-w-full"
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            {/* 历史数据渐变 */}
            <linearGradient id={`hist-gradient-${selectedMetric}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={metricColor} stopOpacity="0.25"/>
              <stop offset="100%" stopColor={metricColor} stopOpacity="0.02"/>
            </linearGradient>
            {/* 预测数据渐变 */}
            <linearGradient id="forecast-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f97316" stopOpacity="0.25"/>
              <stop offset="100%" stopColor="#f97316" stopOpacity="0.02"/>
            </linearGradient>
            {/* 发光效果 */}
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>

          {/* 背景 */}
          <rect 
            x={padding.left} 
            y={padding.top} 
            width={innerWidth} 
            height={innerHeight} 
            fill="rgba(10, 15, 26, 0.5)"
            rx="4"
          />

          {/* Y 轴网格线和标签 */}
          {ticks.map((tick, i) => {
            const y = yScale(tick)
            return (
              <g key={`y-${i}`}>
                <line 
                  x1={padding.left} 
                  y1={y} 
                  x2={chartWidth - padding.right} 
                  y2={y}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray={i === 0 ? "none" : "4,4"}
                />
                <text 
                  x={padding.left - 12} 
                  y={y + 4} 
                  textAnchor="end" 
                  className="text-xs fill-cyber-muted font-mono"
                >
                  {formatValue(tick)}
                </text>
              </g>
            )
          })}

          {/* X 轴线 */}
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="rgba(255,255,255,0.2)"
          />

          {/* Y 轴线 */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={chartHeight - padding.bottom}
            stroke="rgba(255,255,255,0.2)"
          />

          {/* X 轴标签 */}
          {months.map((month, i) => {
            if (i % xLabelInterval !== 0 && i !== months.length - 1) return null
            const x = xScale(i)
            const isForecast = i >= forecastStartIndex
            return (
              <g key={`x-${i}`}>
                {/* 刻度线 */}
                <line
                  x1={x}
                  y1={chartHeight - padding.bottom}
                  x2={x}
                  y2={chartHeight - padding.bottom + 6}
                  stroke={isForecast ? "rgba(249, 115, 22, 0.5)" : "rgba(255,255,255,0.3)"}
                />
                {/* 标签 */}
                <text 
                  x={x} 
                  y={chartHeight - padding.bottom + 22} 
                  textAnchor="middle" 
                  className={`text-xs font-mono ${isForecast ? 'fill-orange-400' : 'fill-cyber-muted'}`}
                >
                  {formatMonth(month)}
                </text>
              </g>
            )
          })}

          {/* 预测区域背景 */}
          {forecastStartIndex < months.length && (
            <rect
              x={xScale(forecastStartIndex) - 5}
              y={padding.top}
              width={chartWidth - padding.right - xScale(forecastStartIndex) + 5}
              height={innerHeight}
              fill="rgba(249, 115, 22, 0.05)"
              rx="4"
            />
          )}

          {/* 预测分界线 */}
          {forecastStartIndex > 0 && forecastStartIndex < months.length && (
            <>
              <line
                x1={xScale(forecastStartIndex) - 5}
                y1={padding.top}
                x2={xScale(forecastStartIndex) - 5}
                y2={chartHeight - padding.bottom}
                stroke="rgba(249, 115, 22, 0.6)"
                strokeDasharray="6,4"
                strokeWidth="2"
              />
              <text
                x={xScale(forecastStartIndex) + 5}
                y={padding.top + 18}
                className="text-xs fill-orange-400 font-medium"
              >
                ← 历史 | 预测 →
              </text>
            </>
          )}

          {/* 历史数据填充 */}
          {historicalPath && lastHistoricalIndex >= 0 && (
            <path
              d={`${historicalPath} L ${xScale(lastHistoricalIndex)} ${chartHeight - padding.bottom} L ${xScale(0)} ${chartHeight - padding.bottom} Z`}
              fill={`url(#hist-gradient-${selectedMetric})`}
            />
          )}

          {/* 历史数据线 */}
          {historicalPath && (
            <motion.path
              d={historicalPath}
              fill="none"
              stroke={metricColor}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              filter="url(#glow)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 1.2, ease: "easeOut" }}
            />
          )}

          {/* 预测数据线 */}
          {forecastPath && (
            <motion.path
              d={forecastPath}
              fill="none"
              stroke="#f97316"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="8,5"
              filter="url(#glow)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              transition={{ duration: 0.8, delay: 0.6 }}
            />
          )}

          {/* 历史数据点 */}
          {historical.map((value, i) => {
            if (value === null) return null
            return (
              <motion.circle
                key={`h-${i}`}
                cx={xScale(i)}
                cy={yScale(value)}
                r="5"
                fill={metricColor}
                stroke="#0a0f1a"
                strokeWidth="2"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.05 * Math.min(i, 20) }}
                style={{ cursor: 'pointer' }}
                onMouseEnter={(e) => handleMouseMove(e, i, months[i], value, 'historical')}
                onMouseMove={(e) => handleMouseMove(e, i, months[i], value, 'historical')}
              />
            )
          })}

          {/* 预测数据点 */}
          {forecastValues.map((value, i) => {
            if (value === null) return null
            return (
              <motion.circle
                key={`f-${i}`}
                cx={xScale(i)}
                cy={yScale(value)}
                r="6"
                fill="#f97316"
                stroke="#0a0f1a"
                strokeWidth="2"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.8 + 0.08 * (i - forecastStartIndex) }}
                style={{ cursor: 'pointer' }}
                onMouseEnter={(e) => handleMouseMove(e, i, months[i], value, 'forecast')}
                onMouseMove={(e) => handleMouseMove(e, i, months[i], value, 'forecast')}
              />
            )
          })}

          {/* Y 轴标题 */}
          <text
            x={20}
            y={chartHeight / 2}
            textAnchor="middle"
            transform={`rotate(-90, 20, ${chartHeight / 2})`}
            className="text-xs fill-cyber-muted font-chinese"
          >
            {selectedMetric}
          </text>

          {/* X 轴标题 */}
          <text
            x={chartWidth / 2}
            y={chartHeight - 8}
            textAnchor="middle"
            className="text-xs fill-cyber-muted font-chinese"
          >
            月份
          </text>
        </svg>

        {/* Tooltip */}
        <AnimatePresence>
          {tooltip.show && (
            <motion.div
              className="absolute pointer-events-none z-50"
              style={{ left: tooltip.x + 10, top: tooltip.y - 60 }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.1 }}
            >
              <div className={`px-3 py-2 rounded-lg shadow-xl border ${
                tooltip.type === 'forecast' 
                  ? 'bg-orange-950/95 border-orange-500/50' 
                  : 'bg-cyber-card/95 border-cyber-primary/50'
              }`}>
                <div className="text-xs text-cyber-muted mb-1">{tooltip.month}</div>
                <div className={`text-base font-bold ${
                  tooltip.type === 'forecast' ? 'text-orange-400' : 'text-cyber-primary'
                }`}>
                  {formatValue(tooltip.value)}
                </div>
                <div className={`text-xs mt-1 ${
                  tooltip.type === 'forecast' ? 'text-orange-300/70' : 'text-cyber-muted'
                }`}>
                  {tooltip.type === 'forecast' ? '🔮 预测值' : '📊 实际值'}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 图例 */}
        <div className="flex items-center justify-center gap-8 mt-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 rounded" style={{ backgroundColor: metricColor }} />
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: metricColor }} />
            <span className="text-sm text-cyber-muted font-chinese">历史数据</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-0.5 rounded bg-orange-500" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #f97316 0, #f97316 4px, transparent 4px, transparent 8px)' }} />
            <div className="w-2 h-2 rounded-full bg-orange-500" />
            <span className="text-sm text-cyber-muted font-chinese">预测数据</span>
          </div>
        </div>
      </div>
    )
  }

  // 渲染指标选择器（显示所有16个）
  const renderMetricSelector = () => {
    const predictions = forecast?.predictions || {}
    const availableMetrics = Object.keys(predictions)
    
    // 按重要性排序
    const sortedMetrics = [
      ...IMPORTANT_METRICS.filter(m => availableMetrics.includes(m)),
      ...availableMetrics.filter(m => !IMPORTANT_METRICS.includes(m))
    ]
    
    // 默认显示重要指标，showAllMetrics 时显示全部
    const displayMetrics = showAllMetrics ? sortedMetrics : sortedMetrics.slice(0, 8)
    
    return (
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-sm text-cyber-muted font-chinese">选择指标</span>
          <span className="text-xs text-cyber-primary/70 bg-cyber-primary/10 px-2 py-0.5 rounded-full">
            共 {availableMetrics.length} 个可预测
          </span>
        </div>
        
        <div className="flex flex-wrap gap-2">
          {displayMetrics.map(metric => {
            const prediction = predictions[metric]
            const isUp = prediction?.trend === 'up' || 
              (prediction?.change_percent !== undefined && prediction.change_percent > 0)
            const color = METRIC_COLORS[metric] || '#00f5d4'
            
            return (
              <button
                key={metric}
                onClick={() => setSelectedMetric(metric)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${
                  selectedMetric === metric
                    ? 'ring-2 ring-offset-2 ring-offset-cyber-bg'
                    : 'hover:opacity-80'
                }`}
                style={{
                  backgroundColor: selectedMetric === metric ? `${color}20` : 'rgba(30, 40, 60, 0.5)',
                  borderColor: selectedMetric === metric ? color : 'rgba(100, 120, 150, 0.3)',
                  borderWidth: '1px',
                  borderStyle: 'solid',
                  color: selectedMetric === metric ? color : '#a0aec0',
                  ringColor: color
                }}
              >
                <span 
                  className="w-2 h-2 rounded-full" 
                  style={{ backgroundColor: color }}
                />
                {metric}
                {prediction && (
                  isUp ? (
                    <TrendingUp className="w-3 h-3 text-green-400" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-400" />
                  )
                )}
              </button>
            )
          })}
        </div>
        
        {sortedMetrics.length > 8 && (
          <button
            onClick={() => setShowAllMetrics(!showAllMetrics)}
            className="mt-3 text-sm text-cyber-primary hover:text-cyber-secondary transition-colors flex items-center gap-1"
          >
            {showAllMetrics ? (
              <>收起指标 <ChevronUp className="w-4 h-4" /></>
            ) : (
              <>显示全部 {sortedMetrics.length} 个指标 <ChevronDown className="w-4 h-4" /></>
            )}
          </button>
        )}
      </div>
    )
  }

  // 渲染预测详情
  const renderPredictionDetails = () => {
    if (!forecast?.predictions || !selectedMetric) return null
    
    const prediction = forecast.predictions[selectedMetric]
    if (!prediction) return null
    
    const forecastEntries = Object.entries(prediction.forecast || {}).sort(([a], [b]) => a.localeCompare(b))
    const firstValue = forecastEntries[0]?.[1]
    const lastValue = forecastEntries[forecastEntries.length - 1]?.[1]
    
    const changePercent = prediction.change_percent ?? 
      (firstValue && lastValue ? ((lastValue - firstValue) / firstValue * 100) : 0)
    const isPositive = changePercent >= 0
    
    return (
      <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="p-4 bg-gradient-to-br from-cyber-bg/60 to-cyber-bg/30 rounded-xl border border-cyber-border/50">
          <div className="text-xs text-cyber-muted mb-1 font-chinese">预测趋势</div>
          <div className={`text-xl font-bold flex items-center gap-2 ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {isPositive ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
            {isPositive ? '+' : ''}{changePercent.toFixed(1)}%
          </div>
        </div>
        
        <div className="p-4 bg-gradient-to-br from-cyber-bg/60 to-cyber-bg/30 rounded-xl border border-cyber-border/50">
          <div className="text-xs text-cyber-muted mb-1 font-chinese">模型置信度</div>
          <div className="text-xl font-bold text-cyber-primary">
            {(prediction.confidence * 100).toFixed(0)}%
          </div>
        </div>
        
        <div className="p-4 bg-gradient-to-br from-cyber-bg/60 to-cyber-bg/30 rounded-xl border border-cyber-border/50">
          <div className="text-xs text-cyber-muted mb-1 font-chinese">预测周期</div>
          <div className="text-xl font-bold text-orange-400">
            {forecastEntries.length} 个月
          </div>
        </div>
        
        <div className="p-4 bg-gradient-to-br from-cyber-bg/60 to-cyber-bg/30 rounded-xl border border-cyber-border/50">
          <div className="text-xs text-cyber-muted mb-1 font-chinese">起始预测值</div>
          <div className="text-xl font-bold text-cyber-secondary">
            {firstValue !== undefined ? formatValue(firstValue) : '-'}
          </div>
        </div>
        
        <div className="p-4 bg-gradient-to-br from-cyber-bg/60 to-cyber-bg/30 rounded-xl border border-cyber-border/50">
          <div className="text-xs text-cyber-muted mb-1 font-chinese">末期预测值</div>
          <div className="text-xl font-bold text-cyber-text">
            {lastValue !== undefined ? formatValue(lastValue) : '-'}
          </div>
        </div>
      </div>
    )
  }

  // 加载状态
  if (loading) {
    return (
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-8">
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <div className="relative">
            <Loader2 className="w-10 h-10 text-cyber-primary animate-spin" />
            <Sparkles className="w-5 h-5 text-orange-400 absolute -top-1 -right-1 animate-pulse" />
          </div>
          <div className="text-center">
            <p className="text-cyber-text font-chinese font-medium">正在加载 GitPulse 预测模型</p>
            <p className="text-sm text-cyber-muted mt-1">Transformer + Text 多模态分析中...</p>
          </div>
        </div>
      </div>
    )
  }

  // 错误状态
  if (error) {
    return (
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-red-500/30 p-8">
        <div className="flex flex-col items-center justify-center gap-4 py-8">
          <AlertCircle className="w-10 h-10 text-red-400" />
          <div className="text-center">
            <p className="text-red-400 font-chinese font-medium">{error}</p>
            {forecast?.hint && (
              <p className="text-xs text-cyber-muted mt-2 font-mono">{forecast.hint}</p>
            )}
          </div>
          <button
            onClick={fetchForecast}
            className="mt-2 px-5 py-2.5 bg-cyber-primary/20 text-cyber-primary rounded-lg hover:bg-cyber-primary/30 transition-colors flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            重新加载
          </button>
        </div>
      </div>
    )
  }

  // 不可用状态
  if (!forecast?.available) {
    return (
      <div className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border p-8">
        <div className="flex flex-col items-center justify-center gap-4 py-8 text-cyber-muted">
          <BarChart3 className="w-10 h-10" />
          <div className="text-center">
            <p className="font-chinese font-medium">预测服务暂不可用</p>
            {forecast?.error && (
              <p className="text-xs text-cyber-muted/70 mt-2">{forecast.error}</p>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <motion.div
      className="bg-gradient-to-br from-cyber-card/80 via-cyber-card/60 to-cyber-bg/40 rounded-2xl border border-cyber-secondary/20 overflow-hidden shadow-2xl"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {/* 标题栏 */}
      <div className="px-6 py-5 border-b border-cyber-border/50 bg-gradient-to-r from-orange-500/10 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-gradient-to-br from-orange-500/30 to-amber-500/20 rounded-xl">
              <Sparkles className="w-6 h-6 text-orange-400" />
            </div>
            <div>
              <h3 className="text-xl font-display font-bold text-cyber-text flex items-center gap-3">
                智能趋势预测
                <span className="text-xs font-normal text-orange-400 bg-orange-500/15 px-2.5 py-1 rounded-full border border-orange-500/30">
                  GitPulse AI · R²=0.76
                </span>
              </h3>
              <p className="text-sm text-cyber-muted font-chinese mt-0.5">
                基于 {forecast.historical_months || 0} 个月历史数据，预测未来 {forecastMonths} 个月走势
              </p>
            </div>
          </div>
          
          {/* 控制区 */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-cyber-bg/50 rounded-lg px-3 py-1.5 border border-cyber-border/50">
              <span className="text-xs text-cyber-muted">预测周期:</span>
              <select
                value={forecastMonths}
                onChange={(e) => setForecastMonths(Number(e.target.value))}
                className="bg-transparent text-sm text-cyber-text font-medium outline-none cursor-pointer"
              >
                <option value={6} className="bg-cyber-bg">6 个月</option>
                <option value={12} className="bg-cyber-bg">12 个月</option>
                <option value={24} className="bg-cyber-bg">24 个月</option>
              </select>
            </div>
            <button
              onClick={fetchForecast}
              disabled={loading}
              className="p-2.5 text-cyber-muted hover:text-cyber-primary hover:bg-cyber-primary/10 rounded-lg transition-all"
              title="刷新预测"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* 指标选择器 */}
        {renderMetricSelector()}
        
        {/* 图表 */}
        <div className="bg-cyber-bg/30 rounded-xl p-4 border border-cyber-border/30">
          {renderChart()}
        </div>
        
        {/* 预测详情 */}
        {renderPredictionDetails()}
        
        {/* 模型说明 */}
        <div className="mt-6 p-4 bg-gradient-to-r from-cyber-primary/5 to-transparent rounded-xl border border-cyber-primary/20">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-cyber-primary flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-cyber-text font-medium font-chinese mb-1">模型说明</p>
              <p className="text-xs text-cyber-muted font-chinese leading-relaxed">
                {forecast.predictions?.[selectedMetric]?.reasoning || 
                  'GitPulse 采用 Transformer+Text 多模态架构，融合历史时序数据与项目文本语义进行智能预测。模型在验证集上达到 R²=0.7559，方向准确率 86.7%。'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
