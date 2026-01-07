import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie
} from 'recharts'
import { Tag, TrendingUp, Bug, MessageCircle, ChevronRight, Search } from 'lucide-react'
import type { IssueData, KeywordData } from '../types'

interface IssueAnalysisProps {
  data: IssueData[]
  keywords: Record<string, KeywordData[]>
  selectedMonth: string | null
  onMonthSelect: (month: string | null) => void
}

const CATEGORY_COLORS = {
  '功能需求': '#00f5d4',
  'Bug修复': '#ff6b9d',
  '社区咨询': '#7b61ff',
  '其他': '#8b97a8'
}

const CATEGORY_ICONS = {
  '功能需求': TrendingUp,
  'Bug修复': Bug,
  '社区咨询': MessageCircle,
  '其他': Tag
}

export default function IssueAnalysis({ data, keywords, selectedMonth, onMonthSelect }: IssueAnalysisProps) {
  const [searchMonth, setSearchMonth] = useState('')
  const [viewMode, setViewMode] = useState<'bar' | 'pie'>('bar')

  // 过滤数据
  const filteredData = useMemo(() => {
    if (!data) return []
    if (searchMonth) {
      return data.filter(d => d.month.includes(searchMonth))
    }
    return data
  }, [data, searchMonth])

  // 选中月份的详细数据
  const selectedMonthData = useMemo(() => {
    if (!selectedMonth || !data) return null
    return data.find(d => d.month === selectedMonth)
  }, [selectedMonth, data])

  // 选中月份的关键词
  const selectedKeywords = useMemo(() => {
    if (!selectedMonth || !keywords) return []
    return keywords[selectedMonth] || []
  }, [selectedMonth, keywords])

  // 饼图数据
  const pieData = useMemo(() => {
    if (!selectedMonthData) return []
    return Object.entries(selectedMonthData.categories).map(([name, value]) => ({
      name,
      value,
      color: CATEGORY_COLORS[name as keyof typeof CATEGORY_COLORS]
    }))
  }, [selectedMonthData])

  // 用于条形图的数据（最近12个月）
  const barChartData = useMemo(() => {
    return filteredData.slice(-12).map(item => ({
      month: item.month.slice(2),
      fullMonth: item.month,
      ...item.categories,
      total: item.total
    }))
  }, [filteredData])

  const CustomBarTooltip = ({ active, payload, label }: {
    active?: boolean
    payload?: Array<{ name: string; value: number; color: string }>
    label?: string
  }) => {
    if (!active || !payload) return null

    return (
      <div className="bg-cyber-card/95 backdrop-blur-md border border-cyber-border rounded-lg p-4 shadow-2xl">
        <div className="font-mono text-cyber-text mb-2 pb-2 border-b border-cyber-border">
          20{label}
        </div>
        <div className="space-y-1">
          {payload.map((entry, index) => {
            const Icon = CATEGORY_ICONS[entry.name as keyof typeof CATEGORY_ICONS] || Tag
            return (
              <div key={index} className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2">
                  <Icon className="w-3 h-3" style={{ color: entry.color }} />
                  <span className="text-cyber-muted text-sm font-chinese">{entry.name}</span>
                </div>
                <span className="text-cyber-text font-mono">{entry.value}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 左侧：Issue 分类统计 */}
      <motion.div
        className="lg:col-span-2 bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border overflow-hidden"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
      >
        <div className="px-6 py-4 border-b border-cyber-border">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-display font-bold text-cyber-text">
                Issue 分类统计
              </h2>
              <p className="text-sm text-cyber-muted font-chinese mt-1">
                按月度统计功能需求、Bug修复、社区咨询分布
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              {/* 搜索框 */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-cyber-muted" />
                <input
                  type="text"
                  placeholder="搜索月份..."
                  value={searchMonth}
                  onChange={(e) => setSearchMonth(e.target.value)}
                  className="pl-9 pr-4 py-2 bg-cyber-bg border border-cyber-border rounded-lg text-sm 
                           text-cyber-text placeholder-cyber-muted focus:outline-none focus:border-cyber-primary
                           w-32"
                />
              </div>

              {/* 视图切换 */}
              <div className="flex bg-cyber-bg rounded-lg p-1">
                <button
                  onClick={() => setViewMode('bar')}
                  className={`px-3 py-1 rounded text-sm transition-all ${
                    viewMode === 'bar' 
                      ? 'bg-cyber-primary/20 text-cyber-primary' 
                      : 'text-cyber-muted hover:text-cyber-text'
                  }`}
                >
                  柱状图
                </button>
                <button
                  onClick={() => setViewMode('pie')}
                  className={`px-3 py-1 rounded text-sm transition-all ${
                    viewMode === 'pie' 
                      ? 'bg-cyber-primary/20 text-cyber-primary' 
                      : 'text-cyber-muted hover:text-cyber-text'
                  }`}
                >
                  饼图
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="p-6">
          <div className="h-[400px]">
            <AnimatePresence mode="wait">
              {viewMode === 'bar' ? (
                <motion.div
                  key="bar"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full"
                >
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barChartData} onClick={(e) => {
                      if (e?.activePayload?.[0]?.payload?.fullMonth) {
                        onMonthSelect(e.activePayload[0].payload.fullMonth)
                      }
                    }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(45, 58, 79, 0.5)" vertical={false} />
                      <XAxis 
                        dataKey="month" 
                        stroke="#8b97a8" 
                        tick={{ fill: '#8b97a8', fontSize: 11 }}
                      />
                      <YAxis stroke="#8b97a8" tick={{ fill: '#8b97a8', fontSize: 11 }} />
                      <Tooltip content={<CustomBarTooltip />} />
                      <Bar dataKey="功能需求" stackId="a" fill={CATEGORY_COLORS['功能需求']} radius={[0, 0, 0, 0]} />
                      <Bar dataKey="Bug修复" stackId="a" fill={CATEGORY_COLORS['Bug修复']} radius={[0, 0, 0, 0]} />
                      <Bar dataKey="社区咨询" stackId="a" fill={CATEGORY_COLORS['社区咨询']} radius={[0, 0, 0, 0]} />
                      <Bar dataKey="其他" stackId="a" fill={CATEGORY_COLORS['其他']} radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </motion.div>
              ) : (
                <motion.div
                  key="pie"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex items-center justify-center"
                >
                  {selectedMonthData ? (
                    <div className="flex items-center gap-8">
                      <ResponsiveContainer width={300} height={300}>
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={60}
                            outerRadius={100}
                            paddingAngle={5}
                            dataKey="value"
                          >
                            {pieData.map((entry, index) => (
                              <Cell key={index} fill={entry.color} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="space-y-3">
                        {pieData.map((item) => {
                          const Icon = CATEGORY_ICONS[item.name as keyof typeof CATEGORY_ICONS] || Tag
                          const percentage = ((item.value / selectedMonthData.total) * 100).toFixed(1)
                          return (
                            <div key={item.name} className="flex items-center gap-3">
                              <div 
                                className="w-4 h-4 rounded"
                                style={{ backgroundColor: item.color }}
                              />
                              <Icon className="w-4 h-4" style={{ color: item.color }} />
                              <span className="text-cyber-text font-chinese">{item.name}</span>
                              <span className="text-cyber-muted font-mono">
                                {item.value} ({percentage}%)
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ) : (
                    <p className="text-cyber-muted font-chinese">请选择一个月份查看详细分布</p>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* 分类图例 */}
          <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-cyber-border">
            {Object.entries(CATEGORY_COLORS).map(([name, color]) => {
              const Icon = CATEGORY_ICONS[name as keyof typeof CATEGORY_ICONS] || Tag
              return (
                <div key={name} className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded" style={{ backgroundColor: color }} />
                  <Icon className="w-4 h-4" style={{ color }} />
                  <span className="text-sm text-cyber-muted font-chinese">{name}</span>
                </div>
              )
            })}
          </div>
        </div>
      </motion.div>

      {/* 右侧：月度详情 */}
      <motion.div
        className="bg-cyber-card/50 backdrop-blur-sm rounded-xl border border-cyber-border overflow-hidden"
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.1 }}
      >
        <div className="px-6 py-4 border-b border-cyber-border">
          <h3 className="text-lg font-display font-bold text-cyber-text">
            {selectedMonth ? `${selectedMonth} 详情` : '月度详情'}
          </h3>
        </div>

        <div className="p-6">
          {selectedMonth && selectedMonthData ? (
            <div className="space-y-6">
              {/* 总数统计 */}
              <div className="p-4 bg-cyber-bg/50 rounded-lg border border-cyber-border">
                <div className="text-4xl font-display font-bold text-cyber-primary mb-1">
                  {selectedMonthData.total}
                </div>
                <div className="text-sm text-cyber-muted font-chinese">Issue 总数</div>
              </div>

              {/* 分类详情 */}
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-cyber-text font-chinese">分类统计</h4>
                {Object.entries(selectedMonthData.categories).map(([name, value]) => {
                  const Icon = CATEGORY_ICONS[name as keyof typeof CATEGORY_ICONS] || Tag
                  const color = CATEGORY_COLORS[name as keyof typeof CATEGORY_COLORS]
                  const percentage = (value / selectedMonthData.total) * 100
                  
                  return (
                    <div key={name} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4" style={{ color }} />
                          <span className="text-sm text-cyber-text font-chinese">{name}</span>
                        </div>
                        <span className="text-sm text-cyber-muted font-mono">{value}</span>
                      </div>
                      <div className="h-2 bg-cyber-bg rounded-full overflow-hidden">
                        <motion.div
                          className="h-full rounded-full"
                          style={{ backgroundColor: color }}
                          initial={{ width: 0 }}
                          animate={{ width: `${percentage}%` }}
                          transition={{ duration: 0.5, ease: 'easeOut' }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* 关键词云 */}
              {selectedKeywords.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-cyber-text font-chinese">高频关键词</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedKeywords.map((kw, idx) => (
                      <motion.span
                        key={idx}
                        className="px-3 py-1 bg-cyber-bg rounded-full text-sm border border-cyber-border
                                 hover:border-cyber-primary hover:text-cyber-primary transition-colors"
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        transition={{ delay: idx * 0.05 }}
                        style={{
                          fontSize: `${Math.max(12, Math.min(16, 12 + kw.weight * 8))}px`
                        }}
                      >
                        {kw.word}
                      </motion.span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-center">
              <Tag className="w-12 h-12 text-cyber-muted mb-4" />
              <p className="text-cyber-muted font-chinese">
                点击图表中的柱状或数据点
              </p>
              <p className="text-cyber-muted font-chinese text-sm mt-1">
                查看该月的详细 Issue 分析
              </p>
            </div>
          )}
        </div>

        {/* 月份快速选择 */}
        <div className="px-6 py-4 border-t border-cyber-border">
          <h4 className="text-sm font-semibold text-cyber-muted mb-3 font-chinese">快速跳转</h4>
          <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
            {data?.slice(-24).map(item => (
              <button
                key={item.month}
                onClick={() => onMonthSelect(item.month)}
                className={`
                  px-2 py-1 text-xs rounded font-mono transition-all
                  ${selectedMonth === item.month
                    ? 'bg-cyber-primary text-cyber-bg'
                    : 'bg-cyber-bg text-cyber-muted hover:text-cyber-text hover:bg-cyber-surface'
                  }
                `}
              >
                {item.month.slice(2)}
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  )
}









