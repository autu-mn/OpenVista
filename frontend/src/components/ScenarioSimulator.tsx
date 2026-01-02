import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Area, ComposedChart
} from 'recharts'
import { 
  Sliders, Play, RotateCcw, TrendingUp, TrendingDown, 
  Users, GitPullRequest, Bug, Rocket, Megaphone, Loader2, Info
} from 'lucide-react'

interface ScenarioParams {
  new_contributors: number
  pr_merge_rate: number
  issue_close_rate: number
  major_release: boolean
  marketing_campaign: boolean
}

interface ParameterEffect {
  param: string
  value: string | number
  effect: string
  magnitude: number
}

interface ScenarioResult {
  adjusted_forecast: Record<string, number>
  baseline_forecast: Record<string, number>
  impact_multiplier: number
  impact_summary: string
  parameter_effects: ParameterEffect[]
  total_effect_percentage: number
}

interface ScenarioSimulatorProps {
  repoKey: string
  metricName: string
  historicalData: Record<string, number>
  forecastMonths?: number
}

export default function ScenarioSimulator({
  repoKey,
  metricName,
  historicalData,
  forecastMonths = 6
}: ScenarioSimulatorProps) {
  const [params, setParams] = useState<ScenarioParams>({
    new_contributors: 0,
    pr_merge_rate: 0.5,
    issue_close_rate: 0.5,
    major_release: false,
    marketing_campaign: false
  })
  
  const [result, setResult] = useState<ScenarioResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasChanges, setHasChanges] = useState(false)

  // 检测参数变化
  useEffect(() => {
    const defaultParams: ScenarioParams = {
      new_contributors: 0,
      pr_merge_rate: 0.5,
      issue_close_rate: 0.5,
      major_release: false,
      marketing_campaign: false
    }
    
    const changed = Object.keys(params).some(
      key => params[key as keyof ScenarioParams] !== defaultParams[key as keyof ScenarioParams]
    )
    setHasChanges(changed)
  }, [params])

  const runSimulation = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`/api/predict/${encodeURIComponent(repoKey)}/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          metric_name: metricName,
          forecast_months: forecastMonths,
          scenario_params: params
        })
      })

      const data = await response.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResult(data.scenario)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '模拟失败')
    } finally {
      setLoading(false)
    }
  }

  const resetParams = () => {
    setParams({
      new_contributors: 0,
      pr_merge_rate: 0.5,
      issue_close_rate: 0.5,
      major_release: false,
      marketing_campaign: false
    })
    setResult(null)
  }

  // 构建图表数据
  const chartData = useMemo(() => {
    if (!result) return []

    const allMonths = new Set<string>()
    
    // 历史数据
    Object.keys(historicalData).forEach(m => allMonths.add(m))
    
    // 预测数据
    Object.keys(result.baseline_forecast).forEach(m => allMonths.add(m))
    Object.keys(result.adjusted_forecast).forEach(m => allMonths.add(m))

    const sortedMonths = Array.from(allMonths).sort()
    const lastHistMonth = Object.keys(historicalData).sort().pop() || ''

    return sortedMonths.map(month => ({
      month,
      displayMonth: month.slice(2),
      historical: historicalData[month] ?? null,
      baseline: result.baseline_forecast[month] ?? null,
      adjusted: result.adjusted_forecast[month] ?? null,
      isForecast: month > lastHistMonth
    }))
  }, [historicalData, result])

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null

    return (
      <div className="bg-gray-900/95 border border-gray-700 rounded-lg p-4 shadow-xl backdrop-blur-sm">
        <p className="text-white font-semibold mb-3 border-b border-gray-700 pb-2">
          20{label}
        </p>
        <div className="space-y-2">
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <div 
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-gray-300 text-sm">{entry.name}</span>
              </div>
              <span className="text-white font-mono text-sm">
                {entry.value?.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-indigo-900/30 to-purple-900/30 rounded-xl border border-indigo-500/30 overflow-hidden"
    >
      {/* 标题 */}
      <div className="p-4 border-b border-indigo-500/20">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-indigo-500/30 to-purple-500/30 rounded-lg">
            <Sliders className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h4 className="text-lg font-semibold text-white">场景模拟</h4>
            <p className="text-xs text-gray-400">
              调整假设参数，实时查看对 {metricName} 预测的影响
            </p>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* 参数调整区域 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 新增贡献者 */}
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <Users className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-white">新增核心贡献者</span>
            </div>
            <input
              type="range"
              min="0"
              max="20"
              value={params.new_contributors}
              onChange={(e) => setParams({ ...params, new_contributors: Number(e.target.value) })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between mt-2">
              <span className="text-xs text-gray-500">0</span>
              <span className="text-sm font-bold text-blue-400">{params.new_contributors} 人</span>
              <span className="text-xs text-gray-500">20</span>
            </div>
          </div>

          {/* PR合并率 */}
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <GitPullRequest className="w-4 h-4 text-green-400" />
              <span className="text-sm font-medium text-white">PR 合并率</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={params.pr_merge_rate * 100}
              onChange={(e) => setParams({ ...params, pr_merge_rate: Number(e.target.value) / 100 })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-green-500"
            />
            <div className="flex justify-between mt-2">
              <span className="text-xs text-gray-500">0%</span>
              <span className="text-sm font-bold text-green-400">{(params.pr_merge_rate * 100).toFixed(0)}%</span>
              <span className="text-xs text-gray-500">100%</span>
            </div>
          </div>

          {/* Issue解决率 */}
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <Bug className="w-4 h-4 text-orange-400" />
              <span className="text-sm font-medium text-white">Issue 解决率</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={params.issue_close_rate * 100}
              onChange={(e) => setParams({ ...params, issue_close_rate: Number(e.target.value) / 100 })}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
            />
            <div className="flex justify-between mt-2">
              <span className="text-xs text-gray-500">0%</span>
              <span className="text-sm font-bold text-orange-400">{(params.issue_close_rate * 100).toFixed(0)}%</span>
              <span className="text-xs text-gray-500">100%</span>
            </div>
          </div>

          {/* 开关选项 */}
          <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Rocket className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-white">大版本发布</span>
              </div>
              <button
                onClick={() => setParams({ ...params, major_release: !params.major_release })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  params.major_release ? 'bg-purple-500' : 'bg-gray-600'
                }`}
              >
                <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  params.major_release ? 'translate-x-7' : 'translate-x-1'
                }`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Megaphone className="w-4 h-4 text-pink-400" />
                <span className="text-sm font-medium text-white">营销推广</span>
              </div>
              <button
                onClick={() => setParams({ ...params, marketing_campaign: !params.marketing_campaign })}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  params.marketing_campaign ? 'bg-pink-500' : 'bg-gray-600'
                }`}
              >
                <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  params.marketing_campaign ? 'translate-x-7' : 'translate-x-1'
                }`} />
              </button>
            </div>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="flex items-center gap-3">
          <button
            onClick={runSimulation}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-lg transition-all"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            运行模拟
          </button>
          
          <button
            onClick={resetParams}
            disabled={!hasChanges && !result}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            重置
          </button>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg text-red-300">
            {error}
          </div>
        )}

        {/* 模拟结果 */}
        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-4"
            >
              {/* 影响摘要 */}
              <div className={`p-4 rounded-lg border ${
                result.total_effect_percentage > 0 
                  ? 'bg-green-500/10 border-green-500/30' 
                  : result.total_effect_percentage < 0 
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-gray-500/10 border-gray-500/30'
              }`}>
                <div className="flex items-center gap-3 mb-2">
                  {result.total_effect_percentage > 0 ? (
                    <TrendingUp className="w-5 h-5 text-green-400" />
                  ) : result.total_effect_percentage < 0 ? (
                    <TrendingDown className="w-5 h-5 text-red-400" />
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-gray-500" />
                  )}
                  <span className={`text-lg font-bold ${
                    result.total_effect_percentage > 0 
                      ? 'text-green-400' 
                      : result.total_effect_percentage < 0 
                        ? 'text-red-400'
                        : 'text-gray-400'
                  }`}>
                    {result.total_effect_percentage > 0 ? '+' : ''}{result.total_effect_percentage.toFixed(1)}%
                  </span>
                </div>
                <p className="text-sm text-gray-300">{result.impact_summary}</p>
              </div>

              {/* 参数影响详情 */}
              {result.parameter_effects && result.parameter_effects.length > 0 && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {result.parameter_effects.map((effect, index) => (
                    <div
                      key={index}
                      className={`p-3 rounded-lg border ${
                        effect.magnitude > 0 
                          ? 'bg-green-500/10 border-green-500/30'
                          : effect.magnitude < 0
                            ? 'bg-red-500/10 border-red-500/30'
                            : 'bg-gray-500/10 border-gray-500/30'
                      }`}
                    >
                      <div className="text-xs text-gray-400 mb-1">{effect.param}</div>
                      <div className="text-sm font-medium text-white mb-1">{effect.value}</div>
                      <div className={`text-xs ${
                        effect.magnitude > 0 ? 'text-green-400' : effect.magnitude < 0 ? 'text-red-400' : 'text-gray-400'
                      }`}>
                        {effect.effect}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 对比图表 */}
              <div className="h-[350px]">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 40 }}>
                    <defs>
                      <linearGradient id="histGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
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
                      interval="preserveStartEnd"
                    />

                    <YAxis
                      stroke="#8b97a8"
                      tick={{ fill: '#8b97a8', fontSize: 10 }}
                    />

                    <Tooltip content={<CustomTooltip />} />

                    <Legend wrapperStyle={{ paddingTop: '20px' }} />

                    {/* 历史数据 */}
                    <Area
                      type="monotone"
                      dataKey="historical"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fill="url(#histGradient)"
                      name="历史数据"
                      dot={{ r: 2 }}
                      connectNulls
                    />

                    {/* 基线预测 */}
                    <Line
                      type="monotone"
                      dataKey="baseline"
                      stroke="#94a3b8"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      name="基线预测"
                      dot={{ r: 2 }}
                      connectNulls
                    />

                    {/* 场景预测 */}
                    <Line
                      type="monotone"
                      dataKey="adjusted"
                      stroke="#22c55e"
                      strokeWidth={3}
                      name="场景预测"
                      dot={{ r: 3, fill: '#22c55e', strokeWidth: 2, stroke: '#1f2937' }}
                      connectNulls
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* 图例说明 */}
              <div className="p-3 bg-gray-700/30 rounded-lg">
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Info className="w-4 h-4" />
                  <span>紫色区域为历史数据，灰色虚线为基线预测，绿色实线为场景预测结果。</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}













