import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Sparkles, AlertTriangle, AlertCircle, Info, Clock, 
  TrendingUp, TrendingDown, Loader2, RefreshCw, 
  ChevronDown, ChevronUp, Lightbulb, Target
} from 'lucide-react'

interface KeyEvent {
  date: string
  event: string
  impact: 'positive' | 'negative' | 'neutral'
}

interface RiskAlert {
  level: 'warning' | 'critical' | 'info'
  message: string
}

interface ExplanationData {
  summary: string
  key_events: KeyEvent[]
  risk_alerts: RiskAlert[]
  driving_factors: string[]
  recommendations: string[]
}

interface PredictionExplanationProps {
  repoKey: string
  metricName: string
  forecastMonths?: number
  onExplanationLoaded?: (explanation: ExplanationData) => void
}

export default function PredictionExplanation({
  repoKey,
  metricName,
  forecastMonths = 6,
  onExplanationLoaded
}: PredictionExplanationProps) {
  const [explanation, setExplanation] = useState<ExplanationData | null>(null)
  const [prediction, setPrediction] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(true)

  const fetchExplanation = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/predict/${encodeURIComponent(repoKey)}/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric_name: metricName,
          forecast_months: forecastMonths
        })
      })

      const data = await response.json()
      if (data.error) {
        setError(data.error)
      } else {
        setExplanation(data.explanation)
        setPrediction(data.prediction)
        if (onExplanationLoaded) {
          onExplanationLoaded(data.explanation)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (repoKey && metricName) {
      fetchExplanation()
    }
  }, [repoKey, metricName, forecastMonths])

  const getImpactIcon = (impact: string) => {
    switch (impact) {
      case 'positive':
        return <TrendingUp className="w-4 h-4 text-green-400" />
      case 'negative':
        return <TrendingDown className="w-4 h-4 text-red-400" />
      default:
        return <div className="w-4 h-4 rounded-full bg-gray-500" />
    }
  }

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'positive':
        return 'border-green-500/50 bg-green-500/10'
      case 'negative':
        return 'border-red-500/50 bg-red-500/10'
      default:
        return 'border-gray-500/50 bg-gray-500/10'
    }
  }

  const getRiskIcon = (level: string) => {
    switch (level) {
      case 'critical':
        return <AlertCircle className="w-4 h-4 text-red-400" />
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />
      default:
        return <Info className="w-4 h-4 text-blue-400" />
    }
  }

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical':
        return 'border-red-500/50 bg-red-500/10 text-red-300'
      case 'warning':
        return 'border-yellow-500/50 bg-yellow-500/10 text-yellow-300'
      default:
        return 'border-blue-500/50 bg-blue-500/10 text-blue-300'
    }
  }

  if (loading) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700">
        <div className="flex items-center justify-center space-x-3">
          <Loader2 className="w-5 h-5 animate-spin text-purple-400" />
          <span className="text-gray-300">AI 正在分析预测依据...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-gray-800/50 rounded-xl p-4 border border-red-500/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3 text-red-400">
            <AlertCircle className="w-5 h-5" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchExplanation}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>
    )
  }

  if (!explanation) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-purple-900/30 to-blue-900/30 rounded-xl border border-purple-500/30 overflow-hidden"
    >
      {/* 标题栏 */}
      <div 
        className="p-4 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-500/30 to-pink-500/30 rounded-lg">
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h4 className="text-lg font-semibold text-white">AI 归因解释</h4>
            <p className="text-xs text-gray-400">{metricName} 预测依据分析</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation()
              fetchExplanation()
            }}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-4 pt-0 space-y-5">
              {/* 摘要 */}
              <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
                <p className="text-gray-200 leading-relaxed">{explanation.summary}</p>
              </div>

              {/* 关键事件时间线 */}
              {explanation.key_events && explanation.key_events.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-blue-400" />
                    关键事件时间线
                  </h5>
                  <div className="space-y-2">
                    {explanation.key_events.map((event, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className={`p-3 rounded-lg border ${getImpactColor(event.impact)} flex items-start gap-3`}
                      >
                        <div className="flex-shrink-0 mt-0.5">
                          {getImpactIcon(event.impact)}
                        </div>
                        <div>
                          <span className="text-xs font-mono text-gray-400 mr-2">
                            {event.date}
                          </span>
                          <span className="text-sm text-gray-200">{event.event}</span>
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {/* 风险提示 */}
              {explanation.risk_alerts && explanation.risk_alerts.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    风险提示
                  </h5>
                  <div className="space-y-2">
                    {explanation.risk_alerts.map((alert, index) => (
                      <div
                        key={index}
                        className={`p-3 rounded-lg border ${getRiskColor(alert.level)} flex items-start gap-3`}
                      >
                        <div className="flex-shrink-0 mt-0.5">
                          {getRiskIcon(alert.level)}
                        </div>
                        <span className="text-sm">{alert.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 驱动因素 */}
              {explanation.driving_factors && explanation.driving_factors.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
                    <Target className="w-4 h-4 text-green-400" />
                    驱动因素
                  </h5>
                  <div className="flex flex-wrap gap-2">
                    {explanation.driving_factors.map((factor, index) => (
                      <span
                        key={index}
                        className="px-3 py-1.5 bg-green-500/10 border border-green-500/30 rounded-full text-sm text-green-300"
                      >
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* 建议 */}
              {explanation.recommendations && explanation.recommendations.length > 0 && (
                <div>
                  <h5 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-amber-400" />
                    建议措施
                  </h5>
                  <ul className="space-y-2">
                    {explanation.recommendations.map((rec, index) => (
                      <li
                        key={index}
                        className="flex items-start gap-2 text-sm text-gray-300"
                      >
                        <span className="text-amber-400 mt-1">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}














