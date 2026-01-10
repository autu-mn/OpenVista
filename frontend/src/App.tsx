import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Activity, TrendingUp, GitBranch, Users, AlertCircle, FileText, BarChart3, RefreshCw, Sparkles, ChevronDown, ChevronUp, Loader2, CheckCircle2, Zap, Award } from 'lucide-react'
import GroupedTimeSeriesChart from './components/GroupedTimeSeriesChart'
import IssueAnalysis from './components/IssueAnalysis'
import IssueAIAnalysis from './components/IssueAIAnalysis'
import ForecastChart from './components/ForecastChart'
import Header from './components/Header'
import StatsCard from './components/StatsCard'
// ProjectSearch 组件已移除
import HomePage from './components/HomePage'
import RepoHeader from './components/RepoHeader'
import CHAOSSEvaluation from './components/CHAOSSEvaluation'
import ChatAssistant from './components/ChatAssistant'
import DocumentationPage from './components/DocumentationPage'
import type { DemoData, GroupedTimeSeriesData, IssueData } from './types'

// 爬取进度类型
interface CrawlProgress {
  step: number
  stepName: string
  message: string
  progress: number
}

// 渲染内联 Markdown（加粗、斜体等）
function renderMarkdownInline(text: string): React.ReactNode {
  // 处理 **加粗**
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <span key={i} className="text-cyber-primary font-medium bg-cyber-primary/10 px-1 rounded">
          {part.slice(2, -2)}
        </span>
      )
    }
    return part
  })
}

function App() {
  // 判断是否显示首页：
  // - 首次访问（新标签页）：显示首页，不恢复项目
  // - 刷新页面：恢复项目状态，不显示首页
  const [showHomePage, setShowHomePage] = useState<boolean>(() => {
    // 使用 Performance API 检测页面加载类型
    let isReload = false
    try {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
      isReload = navigation?.type === 'reload'
    } catch (e) {
      // 兼容性处理：如果 Performance API 不可用，使用 sessionStorage
      const hasVisited = sessionStorage.getItem('hasVisited')
      if (!hasVisited) {
        sessionStorage.setItem('hasVisited', 'true')
        return true // 首次访问
      }
      // 刷新页面，如果有保存的项目就不显示首页
      return !localStorage.getItem('currentProject')
    }
    
    const hasVisited = sessionStorage.getItem('hasVisited')
    
    // 如果是刷新页面且之前访问过，恢复项目状态
    if (isReload && hasVisited) {
      const savedProject = localStorage.getItem('currentProject')
      if (savedProject) {
        return false // 刷新页面且有项目，不显示首页
      }
    }
    
    // 首次访问或没有保存的项目，显示首页
    if (!hasVisited) {
      sessionStorage.setItem('hasVisited', 'true')
    }
    return true
  })
  // 初始化时：如果是刷新页面且有保存的项目，恢复项目；否则不恢复
  const [currentProject, setCurrentProject] = useState<string>(() => {
    let isReload = false
    try {
      const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
      isReload = navigation?.type === 'reload'
    } catch (e) {
      // 兼容性处理
      const hasVisited = sessionStorage.getItem('hasVisited')
      if (hasVisited) {
        const saved = localStorage.getItem('currentProject')
        return saved || ''
      }
      return ''
    }
    
    const hasVisited = sessionStorage.getItem('hasVisited')
    
    // 只有刷新页面且之前访问过时才恢复项目
    if (isReload && hasVisited) {
      const saved = localStorage.getItem('currentProject')
      return saved || ''
    }
    // 首次访问，不恢复项目
    return ''
  })
  
  const [data, setData] = useState<DemoData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string | null>(() => {
    const saved = localStorage.getItem('selectedMonth')
    return saved || null
  })
  const [activeTab, setActiveTab] = useState<'timeseries' | 'forecast' | 'issues' | 'chaoss' | 'analysis'>(() => {
    const saved = localStorage.getItem('activeTab') as 'timeseries' | 'forecast' | 'issues' | 'chaoss' | 'analysis' | null
    return saved || 'timeseries'
  })
  const [repoInfo, setRepoInfo] = useState<any>(null)
  const [summaryExpanded, setSummaryExpanded] = useState(false)
  const [needsTextCrawl, setNeedsTextCrawl] = useState(false)
  const [crawlingText, setCrawlingText] = useState(false)
  const [isInitialized, setIsInitialized] = useState(false)
  
  // 爬取进度状态（用于在主界面显示）
  const [crawlProgress, setCrawlProgress] = useState<CrawlProgress | null>(null)
  const [isCrawling, setIsCrawling] = useState(false)
  
  // 文档页面状态
  const [showDocs, setShowDocs] = useState(false)
  
  // GitHub API 实时统计数据（当 OpenDigger 数据延迟时使用）
  const [liveStats, setLiveStats] = useState<{
    stars: number
    commits: number
    prs: number
    contributors: number
    month: string
    source: string
  } | null>(null)
  
  // 相似仓库推荐状态
  interface SimilarRepo {
    repo: string
    full_name: string
    description: string
    language: string
    topics: string[]
    stars: number
    openrank: number
    similarity: number
    reasons: string[]
    source?: 'local' | 'github'  // 数据来源
    primary_reason?: string
  }
  const [similarRepos, setSimilarRepos] = useState<SimilarRepo[]>([])
  const [similarReposMessage, setSimilarReposMessage] = useState<string | null>(null)
  const [loadingSimilar, setLoadingSimilar] = useState(false)
  

  // 页面加载时，如果有保存的项目，恢复并加载数据
  useEffect(() => {
    if (!isInitialized) {
      // 使用 Performance API 检测页面加载类型
      let isReload = false
      try {
        const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming
        isReload = navigation?.type === 'reload'
      } catch (e) {
        // 兼容性处理：如果 Performance API 不可用，使用 sessionStorage
        console.warn('Performance API 不可用，使用 sessionStorage 判断')
        const hasVisited = sessionStorage.getItem('hasVisited')
        if (hasVisited) {
          isReload = true // 假设之前访问过就是刷新
        }
      }
      
      const hasVisited = sessionStorage.getItem('hasVisited')
      const savedProject = localStorage.getItem('currentProject')
      
      // 恢复标签页和月份
      const savedTab = localStorage.getItem('activeTab') as 'timeseries' | 'forecast' | 'issues' | 'analysis' | null
      const savedMonth = localStorage.getItem('selectedMonth')
      if (savedTab) {
        setActiveTab(savedTab)
      }
      if (savedMonth) {
        setSelectedMonth(savedMonth)
      }
      
      // 如果是刷新页面且之前访问过且有保存的项目，恢复项目状态
      if (isReload && hasVisited && savedProject) {
        console.log('[页面恢复] 刷新页面，恢复项目:', savedProject)
        setCurrentProject(savedProject)
        setShowHomePage(false)
        setIsInitialized(true)
        // 延迟加载数据，确保组件已完全初始化
        setTimeout(() => {
          fetchDataForProject(savedProject)
        }, 100)
      } else {
        // 首次访问（新标签页），显示首页，确保清空项目数据
        console.log('[页面初始化] 首次访问，显示首页查询界面', {
          isReload,
          hasVisited,
          savedProject,
          showHomePage
        })
        // 确保首次访问时清空项目数据
        setCurrentProject('')
        setData(null)
        setRepoInfo(null)
        setIsInitialized(true)
      }
    }
  }, [isInitialized])

  // 保存当前项目到 localStorage
  useEffect(() => {
    if (currentProject) {
      localStorage.setItem('currentProject', currentProject)
    } else {
      localStorage.removeItem('currentProject')
    }
  }, [currentProject])

  // 保存当前标签页到 localStorage
  useEffect(() => {
    localStorage.setItem('activeTab', activeTab)
  }, [activeTab])

  // 保存选中的月份到 localStorage
  useEffect(() => {
    if (selectedMonth) {
      localStorage.setItem('selectedMonth', selectedMonth)
    } else {
      localStorage.removeItem('selectedMonth')
    }
  }, [selectedMonth])

  useEffect(() => {
    // 如果已经有项目且不在首页，加载数据（用于手动切换项目时）
    if (currentProject && !showHomePage && isInitialized) {
      fetchData()
    }
  }, [currentProject, showHomePage, isInitialized])

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
      
      // 调试日志
      console.log('[fetchData] summaryData:', summaryData)
      console.log('[fetchData] projectSummary:', summaryData.projectSummary)
      console.log('[fetchData] aiSummary exists:', !!summaryData.projectSummary?.aiSummary)
      
      setData({
        repoKey: projectName,
        groupedTimeseries: timeseriesData.error ? null : timeseriesData,
        issueCategories: issuesData.categories || [],
        monthlyKeywords: issuesData.monthlyKeywords || {},
        projectSummary: summaryData.projectSummary || null
      })
      
      // 获取相似仓库推荐
      fetchSimilarRepos(repoKey)
    } catch (err) {
      setError('无法连接到后端服务，请确保后端已启动')
      console.error('Error fetching data:', err)
    } finally {
      setLoading(false)
    }
  }
  
  // 获取相似仓库推荐
  const fetchSimilarRepos = async (repoKey: string) => {
    setLoadingSimilar(true)
    setSimilarReposMessage(null)
    try {
      const response = await fetch(`/api/similar/${encodeURIComponent(repoKey)}`)
      const result = await response.json()
      
      if (result.similar && result.similar.length > 0) {
        setSimilarRepos(result.similar)
        setSimilarReposMessage(null)
      } else {
        setSimilarRepos([])
        // 使用后端返回的详细消息
        setSimilarReposMessage(result.message || '暂无相似项目推荐')
      }
      // 调试信息
      if (result.diagnostics) {
        console.log('相似仓库诊断信息:', result.diagnostics)
      }
    } catch (err) {
      console.warn('获取相似仓库失败:', err)
      setSimilarRepos([])
      setSimilarReposMessage('获取相似仓库失败，请检查网络连接')
    } finally {
      setLoadingSimilar(false)
    }
  }
  
  // 点击相似仓库，跳转到首页执行搜索逻辑（触发爬取流程）
  const handleSimilarRepoClick = (repoFullName: string) => {
    // 解析 owner 和 repo
    const parts = repoFullName.split('/')
    if (parts.length === 2) {
      const [owner, repo] = parts
      // 保存到状态，传递给 HomePage
      setPendingSearch({ owner, repo })
      // 显示首页，让 HomePage 处理爬取逻辑
      setShowHomePage(true)
    }
  }
  
  // 待搜索的仓库（点击相似仓库时设置）
  const [pendingSearch, setPendingSearch] = useState<{ owner: string; repo: string } | null>(null)
  
  const handleCrawlText = async () => {
    if (!currentProject || crawlingText) return
    
    // 先检查是否正在爬取
    try {
      const statusResp = await fetch(`/api/check_crawling_status?project_name=${encodeURIComponent(currentProject)}`)
      const statusData = await statusResp.json()
      
      if (statusData.is_crawling) {
        console.log('[补爬] 项目正在爬取中，跳过')
        setCrawlingText(true)
        return
      }
    } catch (e) {
      console.warn('检查爬取状态失败:', e)
    }
    
    setCrawlingText(true)
    try {
      const response = await fetch(`/api/project/${encodeURIComponent(currentProject)}/crawl_text`, {
        method: 'POST'
      })
      
      if (response.status === 409) {
        // 409 Conflict - 正在爬取中
        const result = await response.json()
        console.log('[补爬]', result.error || '项目正在爬取中')
        setCrawlingText(true)
        return
      }
      
      const result = await response.json()
      
      if (result.success) {
        // 补爬成功后，重新检查文本数据状态
        const parts = currentProject.includes('/') ? currentProject.split('/') : currentProject.split('_')
        if (parts.length >= 2) {
          try {
            const checkResp = await fetch(`/api/check_project?owner=${encodeURIComponent(parts[0])}&repo=${encodeURIComponent(parts.slice(1).join('_'))}`)
            const checkData = await checkResp.json()
            setNeedsTextCrawl(checkData.needsTextCrawl || false)
            console.log('[补爬完成] 重新检查文本数据状态:', { needsTextCrawl: checkData.needsTextCrawl, hasText: checkData.hasText })
          } catch (e) {
            console.warn('补爬后检查文本数据失败:', e)
            setNeedsTextCrawl(false)  // 如果检查失败，假设已成功
          }
        } else {
          setNeedsTextCrawl(false)
        }
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

  // 从分组数据中提取统计信息
  const getStats = () => {
    if (!data?.groupedTimeseries?.groups) {
      // 如果没有 OpenDigger 数据，使用 GitHub API 实时数据
      if (liveStats) {
        return {
          stars: liveStats.stars,
          commits: liveStats.commits,
          prs: liveStats.prs,
          contributors: liveStats.contributors,
          source: 'github_api'
        }
      }
      return { stars: 0, commits: 0, prs: 0, contributors: 0, source: 'none' }
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
    
    const opendiggerStats = {
      stars: getLatestValue('popularity', 'star'),
      commits: getLatestValue('development', '提交'),
      prs: getLatestValue('development', 'pr接受'),
      contributors: getLatestValue('contributors', '参与者'),
      source: 'opendigger'
    }
    
    // 如果 OpenDigger 数据全为 0，使用 GitHub API 实时数据
    const allZero = opendiggerStats.stars === 0 && opendiggerStats.commits === 0 && 
                    opendiggerStats.prs === 0 && opendiggerStats.contributors === 0
    
    if (allZero && liveStats) {
      return {
        stars: liveStats.stars,
        commits: liveStats.commits,
        prs: liveStats.prs,
        contributors: liveStats.contributors,
        source: 'github_api'
      }
    }
    
    return opendiggerStats
  }

  const stats = getStats()
  
  // 当数据加载完成但统计为空时，获取 GitHub API 实时数据
  useEffect(() => {
    const fetchLiveStats = async () => {
      if (!currentProject || !data) return
      
      // 检查是否需要获取实时数据
      const groups = data?.groupedTimeseries?.groups
      if (!groups) return
      
      const getLatestValue = (groupKey: string, metricKey: string) => {
        const group = groups[groupKey]
        if (!group?.metrics) return 0
        const metric = Object.entries(group.metrics).find(([key]) => 
          key.toLowerCase().includes(metricKey.toLowerCase())
        )
        if (!metric?.[1]?.data) return 0
        const arr = metric[1].data
        for (let i = arr.length - 1; i >= 0; i--) {
          if (arr[i] !== null && arr[i] !== undefined) return arr[i] as number
        }
        return 0
      }
      
      const currentStats = {
        stars: getLatestValue('popularity', 'star'),
        commits: getLatestValue('development', '提交'),
        prs: getLatestValue('development', 'pr接受'),
        contributors: getLatestValue('contributors', '参与者')
      }
      
      // 如果所有统计都为 0，获取实时数据
      if (currentStats.stars === 0 && currentStats.commits === 0 && 
          currentStats.prs === 0 && currentStats.contributors === 0) {
        try {
          console.log('[Live Stats] OpenDigger 数据为空，正在获取 GitHub API 实时数据...')
          const response = await fetch(`/api/repo/${encodeURIComponent(currentProject)}/live-stats`)
          const result = await response.json()
          if (result.success && result.stats) {
            console.log('[Live Stats] 获取成功:', result.stats)
            setLiveStats(result.stats)
          }
        } catch (error) {
          console.error('[Live Stats] 获取失败:', error)
        }
      }
    }
    
    fetchLiveStats()
  }, [currentProject, data])

  // 显示首页（优先检查，如果显示首页就直接返回）
  if (showHomePage && isInitialized) {
    return <HomePage 
      onProjectReady={(projectName) => {
        // 清除待搜索状态
        setPendingSearch(null)
        handleProjectReady(projectName)
      }} 
      onProgressUpdate={(progress) => {
        setCrawlProgress(progress)
        setIsCrawling(progress.progress < 100)
      }}
      initialOwner={pendingSearch?.owner || ''}
      initialRepo={pendingSearch?.repo || ''}
    />
  }
  
  // 如果正在初始化且有项目，显示加载状态
  if (!isInitialized && currentProject) {
    return <LoadingScreen />
  }
  
  // 如果正在初始化且有项目，显示加载状态
  if (!isInitialized && currentProject) {
    return <LoadingScreen />
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

      <Header repoName={data?.repoKey} onBackToHome={() => setShowHomePage(true)} onOpenDocs={() => setShowDocs(true)} />
      
      {/* 底部进度条 - 显示后台爬取进度 */}
      <AnimatePresence>
        {isCrawling && crawlProgress && crawlProgress.progress < 100 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-0 left-0 right-0 z-50"
          >
            <div className="bg-cyber-card/95 backdrop-blur-xl border-t border-cyber-primary/30">
              {/* 进度条 */}
              <div className="h-1 bg-cyber-bg">
                <motion.div 
                  className="h-full bg-gradient-to-r from-cyber-primary to-cyber-secondary"
                  initial={{ width: 0 }}
                  animate={{ width: `${crawlProgress.progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              
              {/* 步骤信息 */}
              <div className="container mx-auto px-4 py-2 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-4 h-4 text-cyber-primary animate-spin" />
                  <span className="text-sm text-cyber-text font-chinese">{crawlProgress.message}</span>
                </div>
                
                {/* 步骤标签 - 与后端实际进度一致 */}
                <div className="flex items-center gap-2 text-xs">
                  {[
                    { name: '指标数据', startAt: 5, endAt: 20 },
                    { name: '描述文本', startAt: 20, endAt: 50 },
                    { name: 'Issue/PR', startAt: 50, endAt: 80 },
                    { name: '数据对齐', startAt: 80, endAt: 95 },
                    { name: '完成', startAt: 95, endAt: 100 },
                  ].map((step, i) => {
                    const isComplete = crawlProgress.progress >= step.endAt
                    const isActive = crawlProgress.progress >= step.startAt && crawlProgress.progress < step.endAt
                    return (
                      <span 
                        key={i}
                        className={`px-2 py-0.5 rounded-full transition-colors ${
                          isComplete 
                            ? 'bg-cyber-success/20 text-cyber-success' 
                            : isActive
                            ? 'bg-cyber-primary/20 text-cyber-primary animate-pulse'
                            : 'bg-cyber-border/30 text-cyber-muted/50'
                        }`}
                      >
                        {isComplete ? '✓' : isActive ? '⋯' : i + 1}. {step.name}
                      </span>
                    )
                  })}
                  <span className="ml-2 font-mono text-cyber-primary">{crawlProgress.progress}%</span>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 爬取完成提示 - 更简洁 */}
      <AnimatePresence>
        {crawlProgress && crawlProgress.progress >= 100 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-4 right-4 z-50"
            onAnimationComplete={() => {
              setTimeout(() => {
                setIsCrawling(false)
                setCrawlProgress(null)
                fetchData()
              }, 2000)
            }}
          >
            <div className="bg-cyber-success/20 backdrop-blur-xl rounded-lg border border-cyber-success/50 px-4 py-2 shadow-lg flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-cyber-success" />
              <span className="text-sm text-cyber-success font-chinese">数据爬取完成</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="relative z-10 container mx-auto px-4 py-8">
        {/* 项目搜索区域 - 更自然的设计 */}
        {/* 仓库信息头部 */}
        {repoInfo && <RepoHeader repoInfo={repoInfo} />}
        

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
                  <span className="ml-2 text-xs text-cyber-muted/60" title="OpenDigger 数据源通常有 1-2 个月的处理延迟">
                    (数据源延迟约1-2月)
                  </span>
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

        {/* 统计卡片 - 当月数据 */}
        <motion.div 
          className="mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* 当月数据提示 */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full animate-pulse ${stats.source === 'github_api' ? 'bg-green-400' : 'bg-cyber-primary'}`} />
              <span className="text-sm text-cyber-muted font-chinese">
                最新月度数据（{liveStats?.month || data?.groupedTimeseries?.endMonth || '加载中'}）
                {stats.source === 'github_api' && (
                  <span className="ml-2 text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full">
                    实时 · GitHub API
                  </span>
                )}
              </span>
            </div>
            <span className="text-xs text-cyber-muted/70 font-chinese">
              {stats.source === 'github_api' 
                ? 'OpenDigger 数据延迟，已切换为 GitHub API 实时数据' 
                : '以下为当月指标数值，点击图表查看完整趋势'}
            </span>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
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
          </div>
        </motion.div>

        {/* AI 项目摘要 - 改进排版 */}
        {data?.projectSummary?.aiSummary && (
          <motion.div
            className="mb-8 bg-gradient-to-br from-cyber-card/80 to-cyber-card/40 rounded-xl border border-cyber-primary/20 overflow-hidden shadow-lg"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <button
              onClick={() => setSummaryExpanded(!summaryExpanded)}
              className="w-full px-6 py-4 flex items-center justify-between hover:bg-cyber-primary/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-cyber-primary/30 to-cyber-secondary/30 rounded-lg">
                  <Sparkles className="w-5 h-5 text-cyber-primary" />
                </div>
                <div className="text-left">
                  <h3 className="text-lg font-display font-bold text-cyber-text flex items-center gap-2">
                    AI 智能摘要
                    <span className="text-xs font-normal text-cyber-primary bg-cyber-primary/10 px-2 py-0.5 rounded-full">
                      DeepSeek
                    </span>
                  </h3>
                  <p className="text-sm text-cyber-muted font-chinese">
                    {data.projectSummary.dataRange?.start && data.projectSummary.dataRange?.end ? (
                      <>{data.projectSummary.dataRange.start} 至 {data.projectSummary.dataRange.end} · {data.projectSummary.total_months || data.projectSummary.dataRange?.months_count || 0} 个月数据</>
                    ) : (
                      <>基于项目完整数据生成</>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-cyber-muted font-chinese">{summaryExpanded ? '收起' : '展开'}</span>
                {summaryExpanded ? (
                  <ChevronUp className="w-5 h-5 text-cyber-muted" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-cyber-muted" />
                )}
              </div>
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
                    {/* 摘要内容 - 完整 Markdown 渲染 */}
                    <div className="prose prose-invert max-w-none">
                      {data.projectSummary.aiSummary.split('\n').map((line: string, idx: number) => {
                        // 处理 ### 三级标题
                        if (line.startsWith('### ')) {
                          return (
                            <h5 key={idx} className="text-base font-display font-bold text-cyber-primary mt-3 mb-2 flex items-center gap-2">
                              <span className="w-1 h-4 bg-cyber-primary rounded-full"></span>
                              {line.replace('### ', '')}
                            </h5>
                          )
                        }
                        // 处理 ## 二级标题
                        if (line.startsWith('## ')) {
                          return (
                            <h4 key={idx} className="text-lg font-display font-bold text-cyber-secondary mt-4 mb-2 flex items-center gap-2">
                              <span className="w-1 h-5 bg-cyber-secondary rounded-full"></span>
                              {line.replace('## ', '')}
                            </h4>
                          )
                        }
                        // 处理 # 一级标题
                        if (line.startsWith('# ') && !line.startsWith('## ') && !line.startsWith('### ')) {
                          return (
                            <h3 key={idx} className="text-xl font-display font-bold text-cyber-text mt-4 mb-3">
                              {line.replace('# ', '')}
                            </h3>
                          )
                        }
                        // 处理数字列表 (1. 2. 3.)
                        const numListMatch = line.match(/^(\d+)\.\s+(.+)$/)
                        if (numListMatch) {
                          return (
                            <div key={idx} className="flex items-start gap-2 text-sm text-cyber-text/90 font-chinese ml-2 mb-1">
                              <span className="text-cyber-secondary font-mono min-w-[1.5rem]">{numListMatch[1]}.</span>
                              <span>{renderMarkdownInline(numListMatch[2])}</span>
                            </div>
                          )
                        }
                        // 处理列表项
                        if (line.startsWith('- ') || line.startsWith('* ')) {
                          return (
                            <div key={idx} className="flex items-start gap-2 text-sm text-cyber-text/80 font-chinese ml-2 mb-1">
                              <span className="text-cyber-primary mt-1">•</span>
                              <span>{renderMarkdownInline(line.slice(2))}</span>
                            </div>
                          )
                        }
                        // 普通段落（处理内联 Markdown）
                        if (line.trim()) {
                          return (
                            <p key={idx} className="text-cyber-text/90 font-chinese leading-relaxed mb-2 text-sm">
                              {renderMarkdownInline(line)}
                            </p>
                          )
                        }
                        return null
                      })}
                    </div>
                    
                    {/* 相似仓库推荐 */}
                    <div className="mt-6 pt-4 border-t border-cyber-border/30">
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-4 h-4 text-cyber-secondary" />
                        <h4 className="text-sm font-display font-bold text-cyber-text">相似项目推荐</h4>
                        {loadingSimilar && (
                          <Loader2 className="w-3 h-3 text-cyber-muted animate-spin" />
                        )}
                      </div>
                      
                      {similarRepos.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {similarRepos.slice(0, 5).map((repo, idx) => (
                            <motion.button
                              key={repo.repo}
                              onClick={() => handleSimilarRepoClick(repo.full_name)}
                              className="text-left p-3 bg-cyber-bg/40 hover:bg-cyber-primary/10 rounded-lg border border-cyber-border/30 hover:border-cyber-primary/50 transition-all group"
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: idx * 0.1 }}
                            >
                              <div className="flex items-start justify-between mb-1">
                                <span className="text-sm font-medium text-cyber-primary group-hover:text-cyber-secondary transition-colors">
                                  {repo.full_name}
                                </span>
                                <div className="flex items-center gap-1">
                                  {repo.source === 'github' && (
                                    <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">
                                      GitHub
                                    </span>
                                  )}
                                  {repo.openrank > 0 && (
                                    <span className="text-xs bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded">
                                      OR: {repo.openrank.toFixed(2)}
                                    </span>
                                  )}
                                </div>
                              </div>
                              
                              {repo.description && (
                                <p className="text-xs text-cyber-muted mb-2 line-clamp-2">
                                  {repo.description}
                                </p>
                              )}
                              
                              <div className="flex flex-wrap gap-1 mb-2">
                                {repo.language && (
                                  <span className="text-xs bg-cyber-secondary/20 text-cyber-secondary px-1.5 py-0.5 rounded">
                                    {repo.language}
                                  </span>
                                )}
                                {repo.topics.slice(0, 2).map(topic => (
                                  <span key={topic} className="text-xs bg-cyber-primary/10 text-cyber-primary/70 px-1.5 py-0.5 rounded">
                                    {topic}
                                  </span>
                                ))}
                              </div>
                              
                              {repo.reasons.length > 0 && (
                                <p className="text-xs text-cyber-muted/70 italic">
                                  {repo.reasons[0]}
                                </p>
                              )}
                              
                              <div className="mt-2 text-xs text-cyber-primary/50 flex items-center gap-1 group-hover:text-cyber-primary transition-colors">
                                <span>点击查看分析</span>
                                <span className="group-hover:translate-x-1 transition-transform">→</span>
                              </div>
                            </motion.button>
                          ))}
                        </div>
                      ) : !loadingSimilar ? (
                        <p className="text-xs text-cyber-muted/70 font-chinese">
                          {similarReposMessage || '暂无相似项目推荐。需要更多已分析的项目才能进行匹配。'}
                        </p>
                      ) : null}
                    </div>
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
            active={activeTab === 'forecast'}
            onClick={() => setActiveTab('forecast')}
            icon={<Zap className="w-4 h-4" />}
            label="智能预测"
          />
          <TabButton
            active={activeTab === 'issues'}
            onClick={() => setActiveTab('issues')}
            icon={<FileText className="w-4 h-4" />}
            label="Issue 分析"
          />
          <TabButton
            active={activeTab === 'chaoss'}
            onClick={() => setActiveTab('chaoss')}
            icon={<Award className="w-4 h-4" />}
            label="CHAOSS 评价"
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
          
          {activeTab === 'forecast' && data?.repoKey && (
            <motion.div
              key="forecast"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <ForecastChart 
                repoKey={data.repoKey}
                historicalData={data.groupedTimeseries?.groups ? 
                  Object.values(data.groupedTimeseries.groups).reduce((acc, group) => ({
                    ...acc,
                    ...group.metrics
                  }), {}) : undefined
                }
                timeAxis={data.groupedTimeseries?.timeAxis}
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
              className="space-y-6"
            >
              {/* AI Issue 分析 */}
              {data?.repoKey && (
                <IssueAIAnalysis repoKey={data.repoKey} />
              )}
              
              {/* Issue 统计图表 */}
              <IssueAnalysis 
                data={data?.issueCategories as IssueData[]}
                keywords={data?.monthlyKeywords}
                selectedMonth={selectedMonth}
                onMonthSelect={setSelectedMonth}
              />
            </motion.div>
          )}

          {activeTab === 'chaoss' && data?.repoKey && (
            <motion.div
              key="chaoss"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.3 }}
            >
              <CHAOSSEvaluation repoKey={data.repoKey} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* OpenVista 智能助手浮窗 */}
      <ChatAssistant 
        repoKey={data?.repoKey} 
        projectName={currentProject}
      />
      
      {/* 文档页面 */}
      <DocumentationPage 
        isOpen={showDocs}
        onClose={() => setShowDocs(false)}
      />
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
