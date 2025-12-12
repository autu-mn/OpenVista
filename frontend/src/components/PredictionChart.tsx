import { useState, useEffect, useMemo } from 'react'
import { motion } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Area, AreaChart, ComposedChart
} from 'recharts'
import { TrendingUp, AlertCircle, Loader2, RefreshCw, Info } from 'lucide-react'

interface PredictionData {
  forecast: Record<string, number>
  confidence: number
  reasoning: string
  trend_analysis?: {
    direction: string
    strength: string
    volatility: string
  }
  metric_name: string
  historical_data_points: number
  forecast_months: number
}

interface HistoricalData {
  [month: string]: number
}

interface PredictionChartProps {
  repoKey: string
  metricName: string
  historicalData: HistoricalData
  onClose?: () => void
}

export default function PredictionChart({ 
  repoKey, 
  metricName, 
  historicalData,
  onClose 
}: PredictionChartProps) {
  const [prediction, setPrediction] = useState<PredictionData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forecastMonths, setForecastMonths] = useState(6)

  useEffect(() => {
    if (repoKey && metricName && historicalData) {
      fetchPrediction()
    }
  }, [repoKey, metricName, forecastMonths])

  const fetchPrediction = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/api/predict/${encodeURIComponent(repoKey)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          metric_name: metricName,
          forecast_months: forecastMonths,
          include_reasoning: true
        })
      })

      const data = await response.json()
      
      if (data.error) {
        setError(data.error)
        setPrediction(null)
      } else {
        setPrediction(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '预测失败')
      setPrediction(null)
    } finally {
      setLoading(false)
    }
  }

  // 合并历史数据和预测数据
  const chartData = useMemo(() => {
    if (!historicalData || !prediction) return []

    const data: Array<{
      month: string
      displayMonth: string
      historical: number | null
      forecast: number | null
      isForecast: boolean
    }> = []

    // 添加历史数据
    const sortedHistorical = Object.entries(historicalData).sort()
    sortedHistorical.forEach(([month, value]) => {
      data.push({
        month,
        displayMonth: month.slice(2), // 20-01 -> 01
        historical: value,
        forecast: null,
        isForecast: false
      })
    })

    // 添加预测数据
    const sortedForecast = Object.entries(prediction.forecast).sort()
    sortedForecast.forEach(([month, value]) => {
      data.push({
        month,
        displayMonth: month.slice(2),
        historical: null,
        forecast: value,
        isForecast: true
      })
    })

    return data
  }, [historicalData, prediction])

  // 找到历史数据和预测数据的分界点
  const lastHistoricalMonth = useMemo(() => {
    if (!historicalData) return null
    return Object.keys(historicalData).sort().pop() || null
  }, [historicalData])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null

    const dataPoint = payload[0].payload
    const isForecast = dataPoint.isForecast

    return (
      <div className="bg-gray-800/95 border border-gray-700 rounded-lg p-3 shadow-xl">
        <p className="text-white font-semibold mb-2">{`20${label}`}</p>
        {dataPoint.historical !== null && (
          <p className="text-blue-400">
            历史值: <span className="text-white font-mono">{dataPoint.historical.toFixed(2)}</span>
          </p>
        )}
        {dataPoint.forecast !== null && (
          <p className="text-yellow-400">
            预测值: <span className="text-white font-mono">{dataPoint.forecast.toFixed(2)}</span>
            {isForecast && (
              <span className="text-xs text-gray-400 ml-2">(预测)</span>
            )}
          </p>
        )}
      </div>
    )
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'text-green-400'
    if (confidence >= 0.5) return 'text-yellow-400'
    return 'text-red-400'
  }

  const getConfidenceBgColor = (confidence: number) => {
    if (confidence >= 0.7) return 'bg-green-500/20 border-green-500/50'
    if (confidence >= 0.5) return 'bg-yellow-500/20 border-yellow-500/50'
    return 'bg-red-500/20 border-red-500/50'
  }

  if (loading && !prediction) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-8 border border-gray-700">
        <div className="flex items-center justify-center space-x-3">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
          <span className="text-white">正在生成预测...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-red-500/50">
        <div className="flex items-center space-x-3 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
        <button
          onClick={fetchPrediction}
          className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          重试
        </button>
      </div>
    )
  }

  if (!prediction) {
    return null
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-800/50 rounded-xl p-6 border border-gray-700"
    >
      {/* 标题和操作栏 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-bold text-white mb-1">
            {metricName} 预测
          </h3>
          <p className="text-sm text-gray-400">
            基于 {prediction.historical_data_points} 个月的历史数据
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={forecastMonths}
            onChange={(e) => setForecastMonths(Number(e.target.value))}
            className="bg-gray-700 border border-gray-600 text-white rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={3}>预测3个月</option>
            <option value={6}>预测6个月</option>
            <option value={9}>预测9个月</option>
            <option value={12}>预测12个月</option>
          </select>
          <button
            onClick={fetchPrediction}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            title="刷新预测"
          >
            <RefreshCw className="w-4 h-4 text-white" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              <span className="text-white text-xl">×</span>
            </button>
          )}
        </div>
      </div>

      {/* 置信度和趋势分析 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className={`${getConfidenceBgColor(prediction.confidence)} border rounded-lg p-4`}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-400">预测置信度</span>
            <span className={`text-2xl font-bold ${getConfidenceColor(prediction.confidence)}`}>
              {(prediction.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${
                prediction.confidence >= 0.7 ? 'bg-green-500' :
                prediction.confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
              }`}
              style={{ width: `${prediction.confidence * 100}%` }}
            />
          </div>
        </div>

        {prediction.trend_analysis && (
          <>
            <div className="bg-gray-700/50 border border-gray-600 rounded-lg p-4">
              <div className="text-sm text-gray-400 mb-1">趋势方向</div>
              <div className="flex items-center space-x-2">
                <TrendingUp className={`w-5 h-5 ${
                  prediction.trend_analysis.direction === '上升' ? 'text-green-400' :
                  prediction.trend_analysis.direction === '下降' ? 'text-red-400' : 'text-gray-400'
                }`} />
                <span className="text-white font-semibold">
                  {prediction.trend_analysis.direction}
                </span>
              </div>
            </div>

            <div className="bg-gray-700/50 border border-gray-600 rounded-lg p-4">
              <div className="text-sm text-gray-400 mb-1">波动性</div>
              <span className="text-white font-semibold">
                {prediction.trend_analysis.volatility}
              </span>
            </div>
          </>
        )}
      </div>

      {/* 预测理由 */}
      {prediction.reasoning && (
        <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <div className="flex items-start space-x-2">
            <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm text-blue-400 font-semibold mb-1">预测依据</div>
              <p className="text-sm text-gray-300">{prediction.reasoning}</p>
            </div>
          </div>
        </div>
      )}

      {/* 图表 */}
      <div className="h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 40 }}>
            <defs>
              <linearGradient id="historicalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="forecastGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
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
              tick={{ fill: '#8b97a8', fontSize: 10 }}
              tickLine={{ stroke: '#2d3a4f' }}
              axisLine={{ stroke: '#2d3a4f' }}
              interval="preserveStartEnd"
            />

            <YAxis
              stroke="#8b97a8"
              tick={{ fill: '#8b97a8', fontSize: 10 }}
              tickLine={{ stroke: '#2d3a4f' }}
              axisLine={{ stroke: '#2d3a4f' }}
            />

            <Tooltip content={<CustomTooltip />} />

            <Legend 
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="line"
            />

            {/* 历史数据区域 */}
            <Area
              type="monotone"
              dataKey="historical"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#historicalGradient)"
              name="历史数据"
              dot={{ r: 3, fill: '#3b82f6' }}
              activeDot={{ r: 5 }}
            />

            {/* 预测数据区域 */}
            <Area
              type="monotone"
              dataKey="forecast"
              stroke="#fbbf24"
              strokeWidth={2}
              strokeDasharray="5 5"
              fill="url(#forecastGradient)"
              name="预测数据"
              dot={{ r: 3, fill: '#fbbf24' }}
              activeDot={{ r: 5 }}
            />

            {/* 分界线 */}
            {lastHistoricalMonth && (
              <ReferenceLine
                x={lastHistoricalMonth.slice(2)}
                stroke="#ef4444"
                strokeWidth={2}
                strokeDasharray="3 3"
                label={{ value: "预测起点", position: "top", fill: "#ef4444" }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  )
}

