import { useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart3, TrendingUp, Activity, Zap, Info, Layers, Sliders, Sparkles, Bot } from 'lucide-react'
import PredictionChart from './PredictionChart'
import TrendAnalysisPanel from './TrendAnalysisPanel'
import ComparisonAnalysisPanel from './ComparisonAnalysisPanel'
import MultiMetricPrediction from './MultiMetricPrediction'
import PredictionExplanation from './PredictionExplanation'
import ScenarioSimulator from './ScenarioSimulator'
import AIChat from './AIChat'

interface DataAnalysisPanelProps {
  repoKey: string
  groupedData?: any
  onClose?: () => void
}

type AnalysisMode = 'single' | 'multi' | 'scenario'

export default function DataAnalysisPanel({ 
  repoKey, 
  groupedData,
  onClose 
}: DataAnalysisPanelProps) {
  const [selectedMetric, setSelectedMetric] = useState<{
    groupKey: string
    metricKey: string
    metricName: string
  } | null>(null)

  const [analysisType, setAnalysisType] = useState<'prediction' | 'trend' | 'comparison' | 'ai'>('prediction')
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>('single')
  const [showExplanation, setShowExplanation] = useState(true)

  // GitPulse 支持的16个指标（硬编码，与后端保持一致）
  const GITPULSE_SUPPORTED_METRICS = new Set([
    'OpenRank',
    '活跃度',
    'Star数',
    'Fork数',
    '关注度',
    '参与者数',
    '新增贡献者',
    '贡献者',
    '不活跃贡献者',
    '总线因子',
    '新增Issue',
    '关闭Issue',
    'Issue评论',
    '变更请求',
    'PR接受数',
    'PR审查'
  ])

  // 获取所有可预测的指标（只返回 GitPulse 支持的指标）
  const getAvailableMetrics = () => {
    if (!groupedData || !groupedData.groups) return []
    
    const metrics: Array<{groupKey: string, metricKey: string, metricName: string, groupName: string}> = []
    
    Object.entries(groupedData.groups).forEach(([groupKey, group]: [string, any]) => {
      if (group.metrics) {
        Object.entries(group.metrics).forEach(([metricKey, metric]: [string, any]) => {
          const metricName = metric.name || metricKey.replace('opendigger_', '')
          // 只添加 GitPulse 支持的指标
          if (GITPULSE_SUPPORTED_METRICS.has(metricName)) {
            metrics.push({
              groupKey,
              metricKey,
              metricName,
              groupName: group.name || groupKey
            })
          }
        })
      }
    })
    
    return metrics
  }

  const availableMetrics = getAvailableMetrics()
  const availableMetricNames = availableMetrics.map(m => m.metricName)

  // 获取历史数据
  const getHistoricalData = (groupKey: string, metricKey: string): Record<string, number> => {
    if (!groupedData || !groupedData.groups || !groupedData.timeAxis) return {}
    
    const group = groupedData.groups[groupKey]
    if (!group || !group.metrics || !group.metrics[metricKey]) return {}
    
    const metric = group.metrics[metricKey]
    const historicalData: Record<string, number> = {}
    
    groupedData.timeAxis.forEach((month: string, index: number) => {
      if (metric.data && index < metric.data.length && metric.data[index] !== null) {
        historicalData[month] = metric.data[index]
      }
    })
    
    return historicalData
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gray-800/50 rounded-xl p-6 border border-gray-700"
    >
      {/* 标题栏 */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg">
            <BarChart3 className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">数据分析</h2>
            <p className="text-sm text-gray-400">GitPulse 多模态时序预测</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
          >
            <span className="text-white text-xl">×</span>
          </button>
        )}
      </div>

      {/* 分析类型选择 */}
      <div className="flex space-x-2 mb-6">
        <button
          onClick={() => setAnalysisType('prediction')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            analysisType === 'prediction'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-4 h-4" />
            <span>预测分析</span>
          </div>
        </button>
        <button
          onClick={() => setAnalysisType('trend')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            analysisType === 'trend'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4" />
            <span>趋势分析</span>
          </div>
        </button>
        <button
          onClick={() => setAnalysisType('comparison')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            analysisType === 'comparison'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4" />
            <span>对比分析</span>
          </div>
        </button>
        <button
          onClick={() => setAnalysisType('ai')}
          className={`px-4 py-2 rounded-lg transition-colors ${
            analysisType === 'ai'
              ? 'bg-gradient-to-r from-purple-600 to-indigo-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          <div className="flex items-center space-x-2">
            <Bot className="w-4 h-4" />
            <span>AI 助手</span>
            <Sparkles className="w-3 h-3 text-yellow-400" />
          </div>
        </button>
      </div>

      {/* 预测分析 */}
      {analysisType === 'prediction' && (
        <div className="space-y-6">
          {/* 分析模式选择 */}
          <div className="flex items-center gap-2 p-1 bg-gray-700/50 rounded-lg w-fit">
            <button
              onClick={() => {
                setAnalysisMode('single')
                setSelectedMetric(null)
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                analysisMode === 'single'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <TrendingUp className="w-4 h-4" />
              <span>单指标预测</span>
            </button>
            <button
              onClick={() => {
                setAnalysisMode('multi')
                setSelectedMetric(null)
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                analysisMode === 'multi'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>多指标对比</span>
            </button>
            <button
              onClick={() => {
                setAnalysisMode('scenario')
                if (!selectedMetric && availableMetrics.length > 0) {
                  setSelectedMetric(availableMetrics[0])
                }
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                analysisMode === 'scenario'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Sliders className="w-4 h-4" />
              <span>场景模拟</span>
            </button>
          </div>

          {/* 单指标预测模式 */}
          {analysisMode === 'single' && (
            <div>
              {!selectedMetric ? (
                <div>
                  <h3 className="text-lg font-semibold text-white mb-4">选择要预测的指标</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {availableMetrics.map((metric) => (
                      <button
                        key={`${metric.groupKey}-${metric.metricKey}`}
                        onClick={() => setSelectedMetric(metric)}
                        className="p-4 bg-gray-700/50 hover:bg-gray-700 border border-gray-600 rounded-lg transition-colors text-left"
                      >
                        <div className="text-sm text-gray-400 mb-1">{metric.groupName}</div>
                        <div className="text-white font-semibold">{metric.metricName}</div>
                      </button>
                    ))}
                  </div>
                  
                  {availableMetrics.length === 0 && (
                    <div className="text-center py-8 text-gray-400">
                      <Info className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p>暂无可用指标数据</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <button
                        onClick={() => setSelectedMetric(null)}
                        className="text-blue-400 hover:text-blue-300 text-sm"
                      >
                        ← 返回指标选择
                      </button>
                      <h3 className="text-lg font-semibold text-white mt-2">
                        {selectedMetric.metricName} 预测
                      </h3>
                    </div>
                    <div className="flex items-center gap-2">
                      <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={showExplanation}
                          onChange={(e) => setShowExplanation(e.target.checked)}
                          className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-600 focus:ring-blue-500"
                        />
                        <Sparkles className="w-4 h-4" />
                        显示AI归因解释
                      </label>
                    </div>
                  </div>
                  
                  {/* 预测图表 */}
                  <PredictionChart
                    repoKey={repoKey}
                    metricName={selectedMetric.metricName}
                    historicalData={getHistoricalData(selectedMetric.groupKey, selectedMetric.metricKey)}
                    onClose={() => setSelectedMetric(null)}
                  />

                  {/* AI归因解释 */}
                  {showExplanation && (
                    <PredictionExplanation
                      repoKey={repoKey}
                      metricName={selectedMetric.metricName}
                      forecastMonths={6}
                    />
                  )}
                </div>
              )}
            </div>
          )}

          {/* 多指标对比模式 */}
          {analysisMode === 'multi' && (
            <MultiMetricPrediction
              repoKey={repoKey}
              availableMetrics={availableMetricNames}
            />
          )}

          {/* 场景模拟模式 */}
          {analysisMode === 'scenario' && (
            <div className="space-y-4">
              {/* 指标选择 */}
              <div>
                <label className="text-sm text-gray-400 mb-2 block">选择预测指标</label>
                <div className="flex flex-wrap gap-2">
                  {availableMetrics.map((metric) => (
                    <button
                      key={`${metric.groupKey}-${metric.metricKey}`}
                      onClick={() => setSelectedMetric(metric)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                        selectedMetric?.metricKey === metric.metricKey
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                      }`}
                    >
                      {metric.metricName}
                    </button>
                  ))}
                </div>
              </div>

              {/* 场景模拟器 */}
              {selectedMetric && (
                <ScenarioSimulator
                  repoKey={repoKey}
                  metricName={selectedMetric.metricName}
                  historicalData={getHistoricalData(selectedMetric.groupKey, selectedMetric.metricKey)}
                  forecastMonths={6}
                />
              )}

              {!selectedMetric && availableMetrics.length > 0 && (
                <div className="text-center py-8 text-gray-400">
                  <Sliders className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>请先选择一个指标进行场景模拟</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 趋势分析 */}
      {analysisType === 'trend' && (
        <TrendAnalysisPanel repoKey={repoKey} />
      )}

      {/* 对比分析 */}
      {analysisType === 'comparison' && (
        <ComparisonAnalysisPanel repoKey={repoKey} />
      )}

      {/* AI 助手 */}
      {analysisType === 'ai' && (
        <AIChat projectName={repoKey} />
      )}

      {/* GitPulse 模型信息 */}
      <div className="mt-6 p-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/30 rounded-lg">
        <div className="flex items-start space-x-2">
          <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-gray-300">
            <div className="font-semibold text-blue-400 mb-1">GitPulse 模型</div>
            <p>使用条件 GRU + 文本融合的多模态时序预测模型</p>
            <p className="mt-1 text-xs text-gray-400">
              性能指标: MSE=0.0886, R²=0.70, DA=67.28%, TA@0.2=81.41%
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

