import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Brush
} from 'recharts'
import { Eye, EyeOff, ZoomIn, Calendar } from 'lucide-react'
import type { TimeSeriesData } from '../types'

interface TimeSeriesChartProps {
  data: TimeSeriesData
  onMonthClick: (month: string) => void
}

export default function TimeSeriesChart({ data, onMonthClick }: TimeSeriesChartProps) {
  const [visibleMetrics, setVisibleMetrics] = useState({
    stars: true,
    commits: true,
    prs: true,
    contributors: true
  })
  const [hoveredMonth, setHoveredMonth] = useState<string | null>(null)

  // 转换数据格式用于 Recharts
  const chartData = useMemo(() => {
    if (!data?.timeAxis) return []
    
    return data.timeAxis.map((month, index) => ({
      month,
      displayMonth: month.slice(2), // 简化显示：20-01
      stars: data.metrics.stars.data[index] || 0,
      commits: data.metrics.commits.data[index] || 0,
      prs: data.metrics.prs.data[index] || 0,
      contributors: data.metrics.contributors.data[index] || 0
    }))
  }, [data])

  const toggleMetric = (metric: keyof typeof visibleMetrics) => {
    setVisibleMetrics(prev => ({ ...prev, [metric]: !prev[metric] }))
  }

  // 找出波动最大的点
  const significantPoints = useMemo(() => {
    const points: Array<{ month: string; metric: string; change: number }> = []
    
    if (!chartData.length) return points
    
    const metrics = ['stars', 'commits', 'prs', 'contributors'] as const
    metrics.forEach(metric => {
      for (let i = 1; i < chartData.length; i++) {
        const prev = chartData[i - 1][metric] || 1
        const curr = chartData[i][metric]
        const change = ((curr - prev) / prev) * 100
        
        if (Math.abs(change) >= 40) {
          points.push({ month: chartData[i].month, metric, change })
        }
      }
    })
    
    return points
  }, [chartData])

  const CustomTooltip = ({ active, payload, label }: {
    active?: boolean
    payload?: Array<{ name: string; value: number; color: string }>
    label?: string
  }) => {
    if (!active || !payload) return null

    return (
      <div className="bg-cyber-card/95 backdrop-blur-md border border-cyber-border rounded-lg p-4 shadow-2xl">
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-cyber-border">
          <Calendar className="w-4 h-4 text-cyber-primary" />
          <span className="text-cyber-text font-mono font-semibold">{label}</span>
        </div>
        <div className="space-y-2">
          {payload.map((entry, index) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <div 
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-cyber-muted text-sm font-chinese">{entry.name}</span>
              </div>
              <span className="text-cyber-text font-mono font-semibold">
                {entry.value.toLocaleString()}
              </span>
            </div>
          ))}
        </div>
        <button
          onClick={() => onMonthClick(label || '')}
          className="mt-3 w-full py-2 bg-cyber-primary/20 hover:bg-cyber-primary/30 
                     text-cyber-primary text-sm rounded-lg transition-colors font-chinese"
        >
          查看该月 Issue 详情
        </button>
      </div>
    )
  }

  return (
    <motion.div
      className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3 }}
    >
      {/* 图表头部 */}
      <div className="px-6 py-4 border-b border-cyber-border">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-display font-bold text-cyber-text">
              时序指标折线图
            </h2>
            <p className="text-sm text-cyber-muted font-chinese mt-1">
              2020-01 至 2025-12 月度数据 · 点击数据点查看 Issue 详情
            </p>
          </div>
          
          {/* 指标切换 */}
          <div className="flex flex-wrap gap-2">
            {Object.entries(data?.metrics || {}).map(([key, metric]) => (
              <button
                key={key}
                onClick={() => toggleMetric(key as keyof typeof visibleMetrics)}
                className={`
                  flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all
                  ${visibleMetrics[key as keyof typeof visibleMetrics]
                    ? 'bg-cyber-surface border-2'
                    : 'bg-cyber-bg/50 border border-cyber-border opacity-50'
                  }
                `}
                style={{
                  borderColor: visibleMetrics[key as keyof typeof visibleMetrics] 
                    ? metric.color 
                    : undefined
                }}
              >
                {visibleMetrics[key as keyof typeof visibleMetrics] 
                  ? <Eye className="w-3 h-3" /> 
                  : <EyeOff className="w-3 h-3" />
                }
                <span className="font-chinese">{metric.name}</span>
                <div 
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: metric.color }}
                />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 图表区域 */}
      <div className="p-6">
        <div className="h-[500px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
              onMouseMove={(e) => {
                if (e?.activeLabel) {
                  setHoveredMonth(e.activeLabel as string)
                }
              }}
              onMouseLeave={() => setHoveredMonth(null)}
            >
              <defs>
                {/* 发光效果滤镜 */}
                <filter id="glow">
                  <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                  <feMerge>
                    <feMergeNode in="coloredBlur" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                
                {/* 渐变填充 */}
                <linearGradient id="starsGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FFD700" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#FFD700" stopOpacity={0} />
                </linearGradient>
              </defs>
              
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(45, 58, 79, 0.5)"
                vertical={false}
              />
              
              <XAxis 
                dataKey="displayMonth"
                stroke="#8b97a8"
                tick={{ fill: '#8b97a8', fontSize: 11 }}
                tickLine={{ stroke: '#2d3a4f' }}
                axisLine={{ stroke: '#2d3a4f' }}
                interval="preserveStartEnd"
                tickFormatter={(value) => {
                  // 只显示年份变化点
                  const year = value.slice(0, 2)
                  const month = value.slice(3)
                  return month === '01' ? `20${year}` : ''
                }}
              />
              
              <YAxis 
                stroke="#8b97a8"
                tick={{ fill: '#8b97a8', fontSize: 11 }}
                tickLine={{ stroke: '#2d3a4f' }}
                axisLine={{ stroke: '#2d3a4f' }}
                domain={[0, 'auto']}
                allowDataOverflow={false}
                tickFormatter={(value) => {
                  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
                  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
                  return Math.round(value)
                }}
              />
              
              <Tooltip content={<CustomTooltip />} />
              
              <Legend 
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value) => (
                  <span className="text-cyber-text font-chinese">{value}</span>
                )}
              />

              {/* 重要波动点的参考线 */}
              {significantPoints.slice(0, 5).map((point, idx) => (
                <ReferenceLine
                  key={idx}
                  x={point.month.slice(2)}
                  stroke={point.change > 0 ? '#00ff88' : '#ff6b9d'}
                  strokeDasharray="5 5"
                  strokeOpacity={0.5}
                />
              ))}

              {visibleMetrics.stars && (
                <Line
                  type="monotone"
                  dataKey="stars"
                  name="Star数"
                  stroke="#FFD700"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6, fill: '#FFD700', filter: 'url(#glow)' }}
                />
              )}

              {visibleMetrics.commits && (
                <Line
                  type="monotone"
                  dataKey="commits"
                  name="Commit数"
                  stroke="#00ff88"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6, fill: '#00ff88', filter: 'url(#glow)' }}
                />
              )}

              {visibleMetrics.prs && (
                <Line
                  type="monotone"
                  dataKey="prs"
                  name="PR数"
                  stroke="#7b61ff"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6, fill: '#7b61ff', filter: 'url(#glow)' }}
                />
              )}

              {visibleMetrics.contributors && (
                <Line
                  type="monotone"
                  dataKey="contributors"
                  name="贡献者数"
                  stroke="#ff6b9d"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 6, fill: '#ff6b9d', filter: 'url(#glow)' }}
                />
              )}

              {/* 时间范围选择器 */}
              <Brush
                dataKey="displayMonth"
                height={30}
                stroke="#2d3a4f"
                fill="#111827"
                tickFormatter={() => ''}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 波动提示 */}
        {significantPoints.length > 0 && (
          <div className="mt-4 p-4 bg-cyber-bg/50 rounded-lg border border-cyber-border">
            <div className="flex items-center gap-2 mb-2">
              <ZoomIn className="w-4 h-4 text-cyber-warning" />
              <span className="text-sm font-semibold text-cyber-warning font-chinese">
                检测到 {significantPoints.length} 个显著波动点
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {significantPoints.slice(0, 5).map((point, idx) => (
                <button
                  key={idx}
                  onClick={() => onMonthClick(point.month)}
                  className={`
                    px-3 py-1 rounded-full text-xs font-mono transition-all
                    ${point.change > 0 
                      ? 'bg-cyber-success/20 text-cyber-success border border-cyber-success/30 hover:bg-cyber-success/30' 
                      : 'bg-cyber-accent/20 text-cyber-accent border border-cyber-accent/30 hover:bg-cyber-accent/30'
                    }
                  `}
                >
                  {point.month} {point.metric} {point.change > 0 ? '↑' : '↓'}{Math.abs(point.change).toFixed(0)}%
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}














