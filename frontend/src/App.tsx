import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, TrendingUp, GitBranch, Users, AlertCircle, FileText, BarChart3, RefreshCw, Sparkles, ChevronDown, ChevronUp, Download, Loader2 } from 'lucide-react'
import GroupedTimeSeriesChart from './components/GroupedTimeSeriesChart'
import IssueAnalysis from './components/IssueAnalysis'
import DataAnalysisPanel from './components/DataAnalysisPanel'
import Header from './components/Header'
import StatsCard from './components/StatsCard'
import ProjectSearch from './components/ProjectSearch'
import HomePage from './components/HomePage'
import RepoHeader from './components/RepoHeader'
import type { DemoData, GroupedTimeSeriesData, IssueData } from './types'

function App() {
  const [data, setData] = useState<DemoData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeseries' | 'issues' | 'analysis'>('timeseries')
  const [currentProject, setCurrentProject] = useState<string>('')
  const [showHomePage, setShowHomePage] = useState(true)
  const [repoInfo, setRepoInfo] = useState<any>(null)
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const [needsTextCrawl, setNeedsTextCrawl] = useState(false)
  const [crawlingText, setCrawlingText] = useState(false)

  useEffect(() => {
    // 如果已经有项目且不在首页，加载数据
    if (currentProject && !showHomePage) {
      fetchData()
    }
  }, [currentProject, showHomePage])

  const handleProjectSelect = (projectName: string) => {
    setCurrentProject(projectName)
    setError(null)
    setShowHomePage(false)
  }

  const handleProjectReady = (projectName: string) => {
    console.log('项目准备完成:', projectName)
    setCurrentProject(projectName)
    setShowHomePage(false)
    // 立即加载数据
    setTimeout(() => {
      fetchDataForProject(projectName)
    }, 100)
  }

  const fetchDataForProject = async (projectName: string) => {
    setLoading(true)
    setError(null)
    
    try {
      // 先等待一下，确保数据已加载
      await new Promise(resolve => setTimeout(resolve, 500))
      
      // 使用项目名称获取数据（支持两种格式）
      const repoKey = projectName.includes('/') ? projectName : projectName.replace('_', '/')
      const response = await fetch(`/api/repo/${encodeURIComponent(repoKey)}/summary`)
      const summary = await response.json()
      
      if (summary.error) {
        setError(summary.error)
        setLoading(false)
        return
      }
      
      // 保存仓库信息用于展示
      if (summary.repoInfo) {
        setRepoInfo(summary.repoInfo)
      }

      // 获取时序数据
      const timeseriesResponse = await fetch(`/api/timeseries/grouped/${encodeURIComponent(repoKey)}`)
      const timeseriesData = await timeseriesResponse.json()
      
      if (timeseriesData.error) {
        console.warn('时序数据获取失败:', timeseriesData.error)
      }
      
      // 从时序数据中提取最新的 OpenRank 值
      let latestOpenRank: number | undefined
      if (timeseriesData.groups) {
        for (const [groupKey, groupData] of Object.entries(timeseriesData.groups)) {
          if (groupData.metrics) {
            for (const [metricKey, metricData] of Object.entries(groupData.metrics)) {
              if (metricKey.includes('OpenRank')) {
                const dataArray = (metricData as any).data
                if (dataArray && Array.isArray(dataArray)) {
                  for (let i = dataArray.length - 1; i >= 0; i--) {
                    if (dataArray[i] !== null && dataArray[i] !== undefined) {
                      latestOpenRank = dataArray[i]
                      break
                    }
                  }
                }
                break
              }
            }
          }
          if (latestOpenRank !== undefined) break
        }
      }
      
      // 将 OpenRank 值添加到 repoInfo
      if (latestOpenRank !== undefined && summary.repoInfo) {
        setRepoInfo({ ...summary.repoInfo, openrank: latestOpenRank })
      }
      
      // 获取Issue数据
      const issuesResponse = await fetch(`/api/issues/${encodeURIComponent(repoKey)}`)
      const issuesData = await issuesResponse.json()
      
      if (issuesData.error) {
        console.warn('Issue数据获取失败:', issuesData.error)
      }
      
      // 获取项目摘要（包含 AI 摘要）
      const summaryResponse = await fetch(`/api/repo/${encodeURIComponent(repoKey)}/summary`)
      const summaryData = await summaryResponse.json()
      
      setData({
        repoKey: projectName,
        groupedTimeseries: timeseriesData.error ? null : timeseriesData,
        issueCategories: issuesData.categories || [],
        monthlyKeywords: issuesData.monthlyKeywords || {},
        projectSummary: summaryData.projectSummary || null
      })
      
      // 检查是否缺少文本数据（用于 AI 助手）
      // 无论是否有 aiSummary，都检查一下是否有完整的文本数据
      const parts = projectName.includes('/') ? projectName.split('/') : projectName.split('_')
      if (parts.length >= 2) {
        try {
          const checkResp = await fetch(`/api/check_project?owner=${encodeURIComponent(parts[0])}&repo=${encodeURIComponent(parts.slice(1).join('_'))}`)
          const checkData = await checkResp.json()
          // 如果缺少文本或缺少 aiSummary，都提示补爬
          const needsCrawl = checkData.needsTextCrawl || !summaryData.projectSummary?.aiSummary
          setNeedsTextCrawl(needsCrawl)
          console.log('[检查文本数据]', { needsTextCrawl: checkData.needsTextCrawl, hasAiSummary: !!summaryData.projectSummary?.aiSummary, needsCrawl })
        } catch (e) {
          console.warn('检查文本数据失败:', e)
          setNeedsTextCrawl(!summaryData.projectSummary?.aiSummary)
        }
      } else {
        setNeedsTextCrawl(!summaryData.projectSummary?.aiSummary)
      }
    } catch (err) {
      setError('无法连接到后端服务，请确保后端已启动')
      console.error('Error fetching data:', err)
    } finally {
      setLoading(false)
    }
  }
  
  const handleCrawlText = async () => {
    if (!currentProject || crawlingText) return
    
    setCrawlingText(true)
    try {
      const response = await fetch(`/api/project/${encodeURIComponent(currentProject)}/crawl_text`, {
        method: 'POST'
      })
      const result = await response.json()
      
      if (result.success) {
        setNeedsTextCrawl(false)
        // 重新加载数据
        await fetchDataForProject(currentProject)
      } else {
        console.error('补爬失败:', result.message || result.error)
      }
    } catch (err) {
      console.error('补爬请求失败:', err)
    } finally {
      setCrawlingText(false)
    }
  }

  const fetchData = async () => {
    if (currentProject) {
      await fetchDataForProject(currentProject)
    }
  }

  const handleMonthClick = (month: string) => {
    // 确保月份格式正确 (YYYY-MM)
    const normalizedMonth = month.length === 5 ? `20${month}` : month
    setSelectedMonth(normalizedMonth)
    setActiveTab('issues')
  }

  // 从分组数据中提取统计信息（含变化率）
  const getStats = () => {
    if (!data?.groupedTimeseries?.groups) {
      return { 
        stars: { value: 0, change: '', month: '' },
        commits: { value: 0, change: '', month: '' },
        prs: { value: 0, change: '', month: '' },
        contributors: { value: 0, change: '', month: '' }
      }
    }
    
    const groups = data.groupedTimeseries.groups
    const timeAxis = data.groupedTimeseries.timeAxis || []
    
    const getLatestWithChange = (groupKey: string, metricKey: string) => {
      const group = groups[groupKey]
      if (!group?.metrics) return { value: 0, change: '', month: '' }
      
      // 找到匹配的指标
      const metric = Object.entries(group.metrics).find(([key]) => 
        key.toLowerCase().includes(metricKey.toLowerCase())
      )
      
      if (!metric?.[1]?.data) return { value: 0, change: '', month: '' }
      
      const arr = metric[1].data
      
      // 找最后一个非空值及其索引
      let latestValue = 0
      let latestIndex = -1
      for (let i = arr.length - 1; i >= 0; i--) {
        if (arr[i] !== null && arr[i] !== undefined) {
          latestValue = arr[i] as number
          latestIndex = i
          break
        }
      }
      
      // 找倒数第二个非空值计算环比
      let prevValue = 0
      for (let i = latestIndex - 1; i >= 0; i--) {
        if (arr[i] !== null && arr[i] !== undefined) {
          prevValue = arr[i] as number
          break
        }
      }
      
      // 计算环比变化率
      let change = ''
      if (prevValue > 0 && latestValue !== prevValue) {
        const changeRate = ((latestValue - prevValue) / prevValue) * 100
        if (changeRate > 0) {
          change = `+${changeRate.toFixed(1)}%`
        } else {
          change = `${changeRate.toFixed(1)}%`
        }
      }
      
      // 获取月份标签
      const month = latestIndex >= 0 && timeAxis[latestIndex] ? timeAxis[latestIndex] : ''
      
      return { value: latestValue, change, month }
    }
    
    return {
      stars: getLatestWithChange('popularity', 'star'),
      commits: getLatestWithChange('development', '提交'),
      prs: getLatestWithChange('development', 'pr接受'),
      contributors: getLatestWithChange('contributors', '参与者')
    }
  }

  const stats = getStats()
  const latestMonth = stats.stars.month || stats.commits.month || ''

  // 显示首页
  if (showHomePage) {
    return <HomePage onProjectReady={handleProjectReady} />
  }

  if (loading) {
    return <LoadingScreen />
  }

  if (error) {
    return (
      <div className="min-h-screen bg-cyber-bg bg-cyber-grid flex items-center justify-center">
        <div className="bg-cyber-card/50 rounded-xl border border-cyber-border p-8 max-w-md text-center">
          <AlertCircle className="w-16 h-16 text-cyber-accent mx-auto mb-4" />
          <h2 className="text-xl font-display font-bold text-cyber-text mb-2">数据加载失败</h2>
          <p className="text-cyber-muted font-chinese mb-4">{error}</p>
          <div className="text-sm text-cyber-muted font-chinese mb-4">
            <p>请确保：</p>
            <ul className="list-disc list-inside mt-2 text-left">
              <li>后端服务已启动 (python app.py)</li>
              <li>Data 目录下有处理后的数据</li>
            </ul>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-6 py-3 bg-cyber-primary/20 text-cyber-primary rounded-lg
                     hover:bg-cyber-primary/30 transition-colors mx-auto"
          >
            <RefreshCw className="w-4 h-4" />
            <span>重试</span>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cyber-bg bg-cyber-grid">
      {/* 背景发光效果 */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyber-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-cyber-secondary/5 rounded-full blur-3xl" />
      </div>

      <Header repoName={data?.repoKey} onBackToHome={() => setShowHomePage(true)} />

      <main className="relative z-10 container mx-auto px-4 py-8">
        {/* 项目搜索区域 - 更自然的设计 */}
        {/* 仓库信息头部 */}
        {repoInfo && <RepoHeader repoInfo={repoInfo} />}
        
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <ProjectSearch 
            onSelectProject={handleProjectSelect}
            currentProject={currentProject}
          />
        </motion.div>

        {/* 数据信息 */}
        {data?.groupedTimeseries && (
          <motion.div 
            className="mb-6 p-4 bg-cyber-card/30 rounded-lg border border-cyber-border"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-display font-bold text-cyber-primary">
                  {data.repoKey}
                </h2>
                <p className="text-sm text-cyber-muted font-chinese">
                  OpenDigger 数据 · {data.groupedTimeseries.startMonth} 至 {data.groupedTimeseries.endMonth}
                  · {data.groupedTimeseries.timeAxis.length} 个月
                </p>
                <p className="text-xs text-cyber-muted/60 font-chinese mt-1">
                  💡 OpenDigger 数据通常有 2-3 个月延迟，最新月份可能暂无数据
                </p>
              </div>
              <button
                onClick={fetchData}
                className="flex items-center gap-2 px-4 py-2 text-cyber-muted hover:text-cyber-primary transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                <span className="text-sm">刷新</span>
              </button>
            </div>
          </motion.div>
        )}

        {/* 统计卡片 */}
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* 月份说明 */}
          {latestMonth && (
            <div className="mb-4 flex items-center gap-2 text-sm text-cyber-muted font-chinese">
              <span className="inline-block w-2 h-2 rounded-full bg-cyber-primary animate-pulse" />
              <span>以下数据为 <span className="text-cyber-primary font-mono">{latestMonth}</span> 最新月指标</span>
              <span className="text-cyber-muted/50">（环比上月）</span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatsCard
            icon={<Activity className="w-6 h-6" />}
              title="Star 增量"
              value={Math.round(stats.stars.value)}
              change={stats.stars.change}
            color="primary"
          />
          <StatsCard
            icon={<GitBranch className="w-6 h-6" />}
              title="代码提交数"
              value={Math.round(stats.commits.value)}
              change={stats.commits.change}
            color="success"
          />
          <StatsCard
            icon={<TrendingUp className="w-6 h-6" />}
              title="PR 接受数"
              value={Math.round(stats.prs.value)}
              change={stats.prs.change}
            color="secondary"
          />
          <StatsCard
            icon={<Users className="w-6 h-6" />}
              title="活跃参与者"
              value={Math.round(stats.contributors.value)}
              change={stats.contributors.change}
            color="accent"
          />
          </div>
        </motion.div>

        {/* 缺少文本数据提示 - 当缺少文本数据时显示 */}
        {needsTextCrawl && (
          <motion.div
            className="mb-8 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-400" />
                <div>
                  <p className="text-yellow-200 font-chinese text-sm">
                    该项目缺少描述性文本数据，AI 助手功能可能受限
                  </p>
                  <p className="text-yellow-200/60 font-chinese text-xs mt-1">
                    点击补爬可获取 README、文档等文本数据，用于知识库问答
                  </p>
                </div>
              </div>
              <button
                onClick={handleCrawlText}
                disabled={crawlingText}
                className="flex items-center gap-2 px-4 py-2 bg-yellow-500/20 hover:bg-yellow-500/30 
                         text-yellow-200 rounded-lg transition-colors disabled:opacity-50 whitespace-nowrap"
              >
                {crawlingText ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">补爬中...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span className="text-sm">补爬文本</span>
                  </>
                )}
              </button>
            </div>
          </motion.div>
        )}

        {/* AI 项目摘要 */}
        {data?.projectSummary?.aiSummary && (
          <motion.div
            className="mb-8 bg-gradient-to-br from-cyber-card/60 to-cyber-card/30 rounded-xl border border-cyber-primary/30 overflow-hidden"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <button
              onClick={() => setSummaryExpanded(!summaryExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-cyber-primary/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 bg-cyber-primary/20 rounded-lg">
                  <Sparkles className="w-5 h-5 text-cyber-primary" />
                </div>
                <div className="text-left">
                  <h3 className="text-lg font-display font-bold text-cyber-text">
                    AI 项目摘要
                  </h3>
                  <p className="text-sm text-cyber-muted font-chinese">
                    基于 {data.projectSummary.dataRange?.months_count || 0} 个月数据生成
                    {data.projectSummary.dataRange?.start && data.projectSummary.dataRange?.end && (
                      <span> · {data.projectSummary.dataRange.start} 至 {data.projectSummary.dataRange.end}</span>
                    )}
                  </p>
                </div>
              </div>
              {summaryExpanded ? (
                <ChevronUp className="w-5 h-5 text-cyber-muted" />
              ) : (
                <ChevronDown className="w-5 h-5 text-cyber-muted" />
              )}
            </button>
            
            <AnimatePresence>
              {summaryExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden"
                >
                  <div className="px-6 pb-6">
                    <div className="p-4 bg-cyber-bg/50 rounded-lg border border-cyber-border">
                      <p className="text-cyber-text font-chinese leading-relaxed whitespace-pre-wrap">
                        {data.projectSummary.aiSummary}
                      </p>
                    </div>
                    
                    {/* Issue 统计摘要（抽样数据） */}
                    {data.projectSummary.issueStats && (
                      <div className="mt-4">
                        <p className="text-xs text-cyber-muted font-chinese mb-2 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full"></span>
                          以下为抽样统计，仅代表样本分布趋势，非实际总数
                        </p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="p-3 bg-cyber-primary/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-primary">
                            {data.projectSummary.issueStats.feature || 0}
                          </div>
                          <div className="text-xs text-cyber-muted font-chinese">功能需求</div>
                        </div>
                        <div className="p-3 bg-cyber-accent/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-accent">
                            {data.projectSummary.issueStats.bug || 0}
                          </div>
                          <div className="text-xs text-cyber-muted font-chinese">Bug 修复</div>
                        </div>
                        <div className="p-3 bg-cyber-secondary/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-secondary">
                            {data.projectSummary.issueStats.question || 0}
                          </div>
                          <div className="text-xs text-cyber-muted font-chinese">社区咨询</div>
                        </div>
                        <div className="p-3 bg-cyber-muted/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-text">
                            {data.projectSummary.issueStats.total || 0}
                          </div>
                            <div className="text-xs text-cyber-muted font-chinese">抽样总数</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}

        {/* 标签页导航 */}
        <motion.div 
          className="flex gap-4 mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <TabButton
            active={activeTab === 'timeseries'}
            onClick={() => setActiveTab('timeseries')}
            icon={<BarChart3 className="w-4 h-4" />}
            label="时序分析"
            badge={data?.groupedTimeseries?.groups ? Object.keys(data.groupedTimeseries.groups).length : 0}
          />
          <TabButton
            active={activeTab === 'issues'}
            onClick={() => setActiveTab('issues')}
            icon={<FileText className="w-4 h-4" />}
            label="Issue 分析"
          />
          <TabButton
            active={activeTab === 'analysis'}
            onClick={() => setActiveTab('analysis')}
            icon={<TrendingUp className="w-4 h-4" />}
            label="数据分析"
          />
        </motion.div>

        {/* 主内容区 */}
        <AnimatePresence mode="wait">
          {activeTab === 'timeseries' && (
            <motion.div
              key="timeseries"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <GroupedTimeSeriesChart 
                data={data?.groupedTimeseries as GroupedTimeSeriesData}
                onMonthClick={handleMonthClick}
                repoKey={data?.repoKey}
              />
            </motion.div>
          )}
          
          {activeTab === 'issues' && (
            <motion.div
              key="issues"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <IssueAnalysis 
                data={data?.issueCategories as IssueData[]}
                keywords={data?.monthlyKeywords}
                selectedMonth={selectedMonth}
                onMonthSelect={setSelectedMonth}
                repoKey={data?.repoKey || ''}
              />
            </motion.div>
          )}
          
          {activeTab === 'analysis' && (
            <motion.div
              key="analysis"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <DataAnalysisPanel 
                repoKey={data?.repoKey || ''}
                groupedData={data?.groupedTimeseries}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}

// 标签按钮组件
function TabButton({ active, onClick, icon, label, badge }: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: number
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-300
        ${active 
          ? 'bg-cyber-primary/20 text-cyber-primary border border-cyber-primary/50 glow-primary' 
          : 'bg-cyber-card text-cyber-muted border border-cyber-border hover:border-cyber-primary/30 hover:text-cyber-text'
        }
      `}
    >
      {icon}
      <span className="font-chinese">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className={`
          px-2 py-0.5 rounded-full text-xs font-mono
          ${active ? 'bg-cyber-primary/30 text-cyber-primary' : 'bg-cyber-border text-cyber-muted'}
        `}>
          {badge}
        </span>
      )}
    </button>
  )
}

// 加载屏幕
function LoadingScreen() {
  return (
    <div className="min-h-screen bg-cyber-bg flex items-center justify-center">
      <motion.div
        className="flex flex-col items-center gap-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className="relative">
          <div className="w-16 h-16 border-4 border-cyber-primary/30 rounded-full" />
          <div className="absolute inset-0 w-16 h-16 border-4 border-transparent border-t-cyber-primary rounded-full animate-spin" />
        </div>
        <p className="text-cyber-muted font-chinese">正在加载真实数据...</p>
        <p className="text-cyber-muted/50 font-chinese text-sm">请确保后端服务已启动</p>
      </motion.div>
    </div>
  )
}

export default App

                          </div>
                          <div className="text-xs text-cyber-muted font-chinese">Bug 修复</div>
                        </div>
                        <div className="p-3 bg-cyber-secondary/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-secondary">
                            {data.projectSummary.issueStats.question || 0}
                          </div>
                          <div className="text-xs text-cyber-muted font-chinese">社区咨询</div>
                        </div>
                        <div className="p-3 bg-cyber-muted/10 rounded-lg text-center">
                          <div className="text-2xl font-display font-bold text-cyber-text">
                            {data.projectSummary.issueStats.total || 0}
                          </div>
                            <div className="text-xs text-cyber-muted font-chinese">抽样总数</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}

        {/* 标签页导航 */}
        <motion.div 
          className="flex gap-4 mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <TabButton
            active={activeTab === 'timeseries'}
            onClick={() => setActiveTab('timeseries')}
            icon={<BarChart3 className="w-4 h-4" />}
            label="时序分析"
            badge={data?.groupedTimeseries?.groups ? Object.keys(data.groupedTimeseries.groups).length : 0}
          />
          <TabButton
            active={activeTab === 'issues'}
            onClick={() => setActiveTab('issues')}
            icon={<FileText className="w-4 h-4" />}
            label="Issue 分析"
          />
          <TabButton
            active={activeTab === 'analysis'}
            onClick={() => setActiveTab('analysis')}
            icon={<TrendingUp className="w-4 h-4" />}
            label="数据分析"
          />
        </motion.div>

        {/* 主内容区 */}
        <AnimatePresence mode="wait">
          {activeTab === 'timeseries' && (
            <motion.div
              key="timeseries"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <GroupedTimeSeriesChart 
                data={data?.groupedTimeseries as GroupedTimeSeriesData}
                onMonthClick={handleMonthClick}
                repoKey={data?.repoKey}
              />
            </motion.div>
          )}
          
          {activeTab === 'issues' && (
            <motion.div
              key="issues"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <IssueAnalysis 
                data={data?.issueCategories as IssueData[]}
                keywords={data?.monthlyKeywords}
                selectedMonth={selectedMonth}
                onMonthSelect={setSelectedMonth}
                repoKey={data?.repoKey || ''}
              />
            </motion.div>
          )}
          
          {activeTab === 'analysis' && (
            <motion.div
              key="analysis"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <DataAnalysisPanel 
                repoKey={data?.repoKey || ''}
                groupedData={data?.groupedTimeseries}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}

// 标签按钮组件
function TabButton({ active, onClick, icon, label, badge }: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: number
}) {
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-all duration-300
        ${active 
          ? 'bg-cyber-primary/20 text-cyber-primary border border-cyber-primary/50 glow-primary' 
          : 'bg-cyber-card text-cyber-muted border border-cyber-border hover:border-cyber-primary/30 hover:text-cyber-text'
        }
      `}
    >
      {icon}
      <span className="font-chinese">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className={`
          px-2 py-0.5 rounded-full text-xs font-mono
          ${active ? 'bg-cyber-primary/30 text-cyber-primary' : 'bg-cyber-border text-cyber-muted'}
        `}>
          {badge}
        </span>
      )}
    </button>
  )
}

// 加载屏幕
function LoadingScreen() {
  return (
    <div className="min-h-screen bg-cyber-bg flex items-center justify-center">
      <motion.div
        className="flex flex-col items-center gap-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className="relative">
          <div className="w-16 h-16 border-4 border-cyber-primary/30 rounded-full" />
          <div className="absolute inset-0 w-16 h-16 border-4 border-transparent border-t-cyber-primary rounded-full animate-spin" />
        </div>
        <p className="text-cyber-muted font-chinese">正在加载真实数据...</p>
        <p className="text-cyber-muted/50 font-chinese text-sm">请确保后端服务已启动</p>
      </motion.div>
    </div>
  )
}

export default App
