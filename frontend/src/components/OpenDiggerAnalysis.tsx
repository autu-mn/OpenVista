import { useState } from 'react'
import { TrendingUp, BarChart3, GitCompare, Zap, Loader2 } from 'lucide-react'

interface OpenDiggerAnalysisProps {
  owner: string
  repo: string
}

export default function OpenDiggerAnalysis({ owner, repo }: OpenDiggerAnalysisProps) {
  const [loading, setLoading] = useState(false)
  const [metricData, setMetricData] = useState<any>(null)
  const [comparisonData, setComparisonData] = useState<any>(null)
  const [trendData, setTrendData] = useState<any>(null)
  const [selectedMetric, setSelectedMetric] = useState('openrank')

  const metrics = [
    { value: 'openrank', label: 'OpenRank (影响力)' },
    { value: 'stars', label: 'Stars' },
    { value: 'forks', label: 'Forks' },
    { value: 'contributors', label: 'Contributors' },
    { value: 'activity', label: 'Activity (活跃度)' },
  ]

  const fetchMetric = async (metric: string) => {
    setLoading(true)
    try {
      const response = await fetch(
        `/api/opendigger/metric?owner=${owner}&repo=${repo}&metric=${metric}`
      )
      const data = await response.json()
      setMetricData(data)
    } catch (error) {
      console.error('获取指标失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTrends = async (metric: string) => {
    setLoading(true)
    try {
      const response = await fetch(
        `/api/opendigger/trends?owner=${owner}&repo=${repo}&metric=${metric}`
      )
      const data = await response.json()
      setTrendData(data)
    } catch (error) {
      console.error('获取趋势失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchEcosystem = async () => {
    setLoading(true)
    try {
      const response = await fetch(
        `/api/opendigger/ecosystem?owner=${owner}&repo=${repo}`
      )
      const data = await response.json()
      setComparisonData(data)
    } catch (error) {
      console.error('获取生态系统洞察失败:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-cyber-card/50 rounded-xl border border-cyber-border p-6">
        <h3 className="text-lg font-display font-bold text-cyber-primary mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          OpenDigger 指标分析
        </h3>

        {/* 指标选择 */}
        <div className="mb-4">
          <label className="block text-sm text-cyber-muted mb-2">选择指标</label>
          <select
            value={selectedMetric}
            onChange={(e) => setSelectedMetric(e.target.value)}
            className="w-full px-4 py-2 bg-cyber-card border border-cyber-border rounded-lg text-cyber-text focus:outline-none focus:border-cyber-primary"
          >
            {metrics.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3 mb-4">
          <button
            onClick={() => fetchMetric(selectedMetric)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-primary/20 text-cyber-primary rounded-lg hover:bg-cyber-primary/30 transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
            获取指标
          </button>
          <button
            onClick={() => fetchTrends(selectedMetric)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-secondary/20 text-cyber-secondary rounded-lg hover:bg-cyber-secondary/30 transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
            趋势分析
          </button>
          <button
            onClick={fetchEcosystem}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-cyber-accent/20 text-cyber-accent rounded-lg hover:bg-cyber-accent/30 transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            生态系统洞察
          </button>
        </div>

        {/* 结果显示 */}
        {metricData && (
          <div className="mt-4 p-4 bg-cyber-card/30 rounded-lg border border-cyber-border">
            <h4 className="font-bold text-cyber-primary mb-2">指标数据</h4>
            <pre className="text-xs text-cyber-muted overflow-auto max-h-40">
              {JSON.stringify(metricData, null, 2)}
            </pre>
          </div>
        )}

        {trendData && (
          <div className="mt-4 p-4 bg-cyber-card/30 rounded-lg border border-cyber-border">
            <h4 className="font-bold text-cyber-primary mb-2">趋势分析</h4>
            <div className="text-sm text-cyber-text">
              <p>趋势: <span className="text-cyber-accent">{trendData.trend}</span></p>
              <p>增长率: <span className="text-cyber-accent">{trendData.growth_rate}%</span></p>
            </div>
          </div>
        )}

        {comparisonData && (
          <div className="mt-4 p-4 bg-cyber-card/30 rounded-lg border border-cyber-border">
            <h4 className="font-bold text-cyber-primary mb-2">生态系统洞察</h4>
            <div className="text-sm text-cyber-text">
              <p>已分析指标数: <span className="text-cyber-accent">{comparisonData.metrics_analyzed}</span></p>
              <pre className="text-xs text-cyber-muted overflow-auto max-h-40 mt-2">
                {JSON.stringify(comparisonData.insights, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

