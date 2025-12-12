import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, TrendingUp, GitBranch, Users, AlertCircle, FileText, BarChart3, RefreshCw } from 'lucide-react'
import GroupedTimeSeriesChart from './components/GroupedTimeSeriesChart'
import IssueAnalysis from './components/IssueAnalysis'
import WaveAnalysis from './components/WaveAnalysis'
import Header from './components/Header'
import StatsCard from './components/StatsCard'
import ProjectSearch from './components/ProjectSearch'
import HomePage from './components/HomePage'
import RepoHeader from './components/RepoHeader'
import OpenDiggerAnalysis from './components/OpenDiggerAnalysis'
import type { DemoData, GroupedTimeSeriesData, IssueData, WaveData } from './types'

function App() {
  const [data, setData] = useState<DemoData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeseries' | 'issues' | 'analysis' | 'opendigger'>('timeseries')
  const [currentProject, setCurrentProject] = useState<string>('')
  const [showHomePage, setShowHomePage] = useState(true)
  const [repoInfo, setRepoInfo] = useState<any>(null)

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
      
      // 获取波动分析
      const analysisResponse = await fetch(`/api/analysis/${encodeURIComponent(repoKey)}`)
      const analysisData = await analysisResponse.json()
      
      if (analysisData.error) {
        console.warn('分析数据获取失败:', analysisData.error)
      }
      
      setData({
        repoKey: projectName,
        groupedTimeseries: timeseriesData.error ? null : timeseriesData,
        issueCategories: issuesData.categories || [],
        monthlyKeywords: issuesData.monthlyKeywords || {},
        waves: analysisData.waves || []
      })
    } catch (err) {
      setError('无法连接到后端服务，请确保后端已启动')
      console.error('Error fetching data:', err)
    } finally {
      setLoading(false)
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

  // 从分组数据中提取统计信息
  const getStats = () => {
    if (!data?.groupedTimeseries?.groups) {
      return { stars: 0, commits: 0, prs: 0, contributors: 0 }
    }
    
    const groups = data.groupedTimeseries.groups
    
    const getLatestValue = (groupKey: string, metricKey: string) => {
      const group = groups[groupKey]
      if (!group?.metrics) return 0
      
      // 找到匹配的指标
      const metric = Object.entries(group.metrics).find(([key]) => 
        key.toLowerCase().includes(metricKey.toLowerCase())
      )
      
      if (!metric?.[1]?.data) return 0
      
      // 找最后一个非空值
      const arr = metric[1].data
      for (let i = arr.length - 1; i >= 0; i--) {
        if (arr[i] !== null && arr[i] !== undefined) {
          return arr[i] as number
        }
      }
      return 0
    }
    
    return {
      stars: getLatestValue('popularity', 'star'),
      commits: getLatestValue('development', '提交'),
      prs: getLatestValue('development', 'pr接受'),
      contributors: getLatestValue('contributors', '参与者')
    }
  }

  const stats = getStats()

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
                  真实数据 · {data.groupedTimeseries.startMonth} 至 {data.groupedTimeseries.endMonth}
                  · {data.groupedTimeseries.timeAxis.length} 个月
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
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <StatsCard
            icon={<Activity className="w-6 h-6" />}
            title="Star 数"
            value={Math.round(stats.stars)}
            change=""
            color="primary"
          />
          <StatsCard
            icon={<GitBranch className="w-6 h-6" />}
            title="代码提交"
            value={Math.round(stats.commits)}
            change=""
            color="success"
          />
          <StatsCard
            icon={<TrendingUp className="w-6 h-6" />}
            title="PR 接受"
            value={Math.round(stats.prs)}
            change=""
            color="secondary"
          />
          <StatsCard
            icon={<Users className="w-6 h-6" />}
            title="参与者"
            value={Math.round(stats.contributors)}
            change=""
            color="accent"
          />
        </motion.div>

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
            icon={<AlertCircle className="w-4 h-4" />}
            label="波动归因"
            badge={data?.waves?.length || 0}
          />
          <TabButton
            active={activeTab === 'opendigger'}
            onClick={() => setActiveTab('opendigger')}
            icon={<BarChart3 className="w-4 h-4" />}
            label="OpenDigger 分析"
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
              <WaveAnalysis 
                waves={data?.waves as WaveData[]}
                onWaveClick={(wave) => {
                  setSelectedMonth(wave.month)
                  setActiveTab('issues')
                }}
              />
            </motion.div>
          )}
          
          {activeTab === 'opendigger' && (
            <motion.div
              key="opendigger"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              {currentProject && (() => {
                const [owner, repo] = currentProject.includes('/') 
                  ? currentProject.split('/') 
                  : currentProject.replace('_', '/').split('/')
                return <OpenDiggerAnalysis owner={owner} repo={repo} />
              })()}
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
