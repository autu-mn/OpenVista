import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Github, Sparkles, TrendingUp, Database, FolderOpen } from 'lucide-react'
import ProgressIndicator from './ProgressIndicator'

interface CrawlProgress {
  step: number
  stepName: string
  message: string
  progress: number
}

interface LocalProject {
  name: string
  full_name: string
  folder: string
  has_timeseries: boolean
  has_text: boolean
  time_range?: { start: string; end: string; months: number }
}

interface HomePageProps {
  onProjectReady: (projectName: string) => void
  onProgressUpdate?: (progress: CrawlProgress) => void
  initialOwner?: string  // 新增：初始的owner值
  initialRepo?: string   // 新增：初始的repo值
}

export default function HomePage({ onProjectReady, onProgressUpdate, initialOwner = '', initialRepo = '' }: HomePageProps) {
  const [owner, setOwner] = useState(initialOwner)
  const [repo, setRepo] = useState(initialRepo)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [localProjects, setLocalProjects] = useState<LocalProject[]>([])
  const [showLocalProjects, setShowLocalProjects] = useState(false)
  
  // 用于跟踪是否已经自动提交过（避免重复触发）
  // 使用一个 key 来跟踪当前的初始值组合，当组合变化时重置标记
  const lastInitialKey = useRef<string>('')
  const hasAutoSubmitted = useRef(false)
  
  // 当初始值变化时，更新输入框的值
  useEffect(() => {
    console.log('[初始值更新] useEffect 触发:', { initialOwner, initialRepo })
    if (initialOwner) {
      setOwner(initialOwner)
    }
    if (initialRepo) {
      setRepo(initialRepo)
    }
    
    // 当初始值组合变化时，重置自动提交标记
    const currentKey = `${initialOwner}_${initialRepo}`
    if (currentKey !== lastInitialKey.current && initialOwner && initialRepo) {
      console.log('[初始值更新] 检测到新的初始值组合，重置自动提交标记')
      lastInitialKey.current = currentKey
      hasAutoSubmitted.current = false
    }
  }, [initialOwner, initialRepo])
  
  // 获取本地已有项目列表
  useEffect(() => {
    const fetchLocalProjects = async () => {
      try {
        const response = await fetch('/api/projects')
        const data = await response.json()
        if (data.projects && data.projects.length > 0) {
          setLocalProjects(data.projects)
        }
      } catch (err) {
        console.error('获取本地项目列表失败:', err)
      }
    }
    fetchLocalProjects()
  }, [])

  // 提取分析逻辑到独立函数，便于自动调用（使用useCallback确保引用稳定）
  const startAnalysis = useCallback(async (ownerName: string, repoName: string) => {
    if (!ownerName || !repoName) {
      setError('请输入仓库所有者用户名和仓库名')
      return
    }

    setLoading(true)
    setError(null)
    setProgress(null)

    try {
      // 先检查数据是否已存在
      const checkResponse = await fetch(
        `/api/check_project?owner=${encodeURIComponent(ownerName)}&repo=${encodeURIComponent(repoName)}`
      )
      const checkData = await checkResponse.json()
      
      if (checkData.exists) {
        // 数据已存在，直接使用
        setLoading(false)
        onProjectReady(checkData.projectName || `${ownerName}_${repoName}`)
        return
      }

      // 数据不存在，开始爬取
      const eventSource = new EventSource(
        `/api/crawl?owner=${encodeURIComponent(ownerName)}&repo=${encodeURIComponent(repoName)}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'start') {
            const progressData = { step: 0, stepName: '开始', message: data.message, progress: 0 }
            setProgress(progressData)
            onProgressUpdate?.(progressData)
          } else if (data.type === 'exists') {
            // 数据已存在，直接使用
            const progressData = { step: 0, stepName: '数据已存在', message: data.message, progress: 100 }
            setProgress(progressData)
            onProgressUpdate?.(progressData)
            setLoading(false)
            eventSource.close()
            setTimeout(() => {
              onProjectReady(data.projectName || `${ownerName}_${repoName}`)
            }, 500)
          } else if (data.type === 'metrics_ready') {
            // 指标数据已就绪，立即切换到项目页面展示
            const progressData = { step: data.step || 1, stepName: '指标数据就绪', message: data.message, progress: data.progress || 20 }
            setProgress(progressData)
            onProgressUpdate?.(progressData)
            // 不关闭SSE连接，继续监听后续进度
            // 立即切换到项目页面，让前端可以展示指标数据
            setTimeout(() => {
              onProjectReady(data.projectName)
              // 注意：不设置 setLoading(false)，让进度条继续显示后台爬取进度
            }, 500)
          } else if (data.type === 'progress') {
            const progressData = { step: data.step, stepName: data.stepName, message: data.message, progress: data.progress }
            setProgress(progressData)
            onProgressUpdate?.(progressData)
          } else if (data.type === 'complete') {
            const progressData = { step: 9, stepName: '完成', message: data.message, progress: 100 }
            setProgress(progressData)
            onProgressUpdate?.(progressData)
            setLoading(false)
            eventSource.close()
            // 如果之前已经切换到项目页面，这里可以刷新数据
            // 如果还没切换，则切换
            if (!data.projectName) {
              const projectName = `${ownerName}_${repoName}`
              setTimeout(() => onProjectReady(projectName), 500)
            }
          } else if (data.type === 'error') {
            setError(data.message)
            setLoading(false)
            eventSource.close()
            onProgressUpdate?.({ step: -1, stepName: '错误', message: data.message, progress: 0 })
          }
        } catch (err) {
          console.error('解析进度数据失败:', err)
        }
      }

      eventSource.onerror = (err) => {
        console.error('SSE连接错误:', err)
        setError('连接中断，请重试')
        eventSource.close()
        setLoading(false)
      }
    } catch (err) {
      setError('请求失败，请检查后端服务是否启动')
      setLoading(false)
    }
  }, [onProjectReady, onProgressUpdate])
  
  // 当有初始值且未自动提交过时，自动开始分析
  useEffect(() => {
    console.log('[自动分析] useEffect 触发:', {
      initialOwner,
      initialRepo,
      hasAutoSubmitted: hasAutoSubmitted.current,
      lastInitialKey: lastInitialKey.current
    })
    
    // 只有当 initialOwner 和 initialRepo 都有值，且还没有自动提交过时，才自动开始分析
    if (initialOwner && initialRepo && !hasAutoSubmitted.current) {
      console.log('[自动分析] 条件满足，准备自动开始分析:', initialOwner, initialRepo)
      // 标记为已自动提交，避免重复触发
      hasAutoSubmitted.current = true
      // 使用 setTimeout 确保在下一个事件循环中执行，避免与状态更新冲突
      setTimeout(() => {
        console.log('[自动分析] 开始调用 startAnalysis')
        startAnalysis(initialOwner.trim(), initialRepo.trim())
      }, 100)
    } else {
      console.log('[自动分析] 条件不满足，跳过自动分析', {
        hasInitialOwner: !!initialOwner,
        hasInitialRepo: !!initialRepo,
        hasAutoSubmitted: hasAutoSubmitted.current
      })
    }
  }, [initialOwner, initialRepo, startAnalysis])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // 重置自动提交标记，允许手动提交
    hasAutoSubmitted.current = false
    startAnalysis(owner.trim(), repo.trim())
  }

  return (
    <div className="min-h-screen bg-cyber-bg bg-cyber-grid flex items-center justify-center px-4">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyber-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-cyber-secondary/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-4xl">
        <motion.div
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="flex items-center justify-center gap-3 mb-6"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
          >
            <Sparkles className="w-10 h-10 text-cyber-primary" />
            <h1 className="text-5xl font-display font-bold bg-gradient-to-r from-cyber-primary via-cyber-secondary to-cyber-accent bg-clip-text text-transparent">
              OpenVista
            </h1>
          </motion.div>
          
          <p className="text-xl text-cyber-muted font-chinese mb-8">
            智能分析 GitHub 仓库生态数据
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-6"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <Database className="w-8 h-8 text-cyber-primary mb-3 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-2">数据采集</h3>
              <p className="text-xs text-cyber-muted font-chinese">自动爬取仓库数据</p>
            </motion.div>

            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-6"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
              <TrendingUp className="w-8 h-8 text-cyber-secondary mb-3 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-2">智能分析</h3>
              <p className="text-xs text-cyber-muted font-chinese">深度挖掘数据洞察</p>
            </motion.div>

            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-6"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
              <Github className="w-8 h-8 text-cyber-accent mb-3 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-2">知识库</h3>
              <p className="text-xs text-cyber-muted font-chinese">自动上传到MaxKB</p>
            </motion.div>
          </div>
        </motion.div>

        <motion.form onSubmit={handleSubmit} className="mb-8"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}>
          <div className="bg-cyber-card/50 backdrop-blur-sm rounded-2xl border border-cyber-border p-6 shadow-2xl">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <label className="block text-sm font-medium text-cyber-muted mb-2 font-chinese">仓库所有者</label>
                <input type="text" value={owner} onChange={(e) => setOwner(e.target.value)}
                  placeholder="例如: microsoft" disabled={loading}
                  className="w-full px-4 py-3 bg-cyber-bg border border-cyber-border rounded-lg text-cyber-text placeholder-cyber-muted/50 focus:outline-none focus:border-cyber-primary focus:ring-2 focus:ring-cyber-primary/20 transition-all" />
              </div>

              <div className="flex-1">
                <label className="block text-sm font-medium text-cyber-muted mb-2 font-chinese">仓库名</label>
                <input type="text" value={repo} onChange={(e) => setRepo(e.target.value)}
                  placeholder="例如: vscode" disabled={loading}
                  className="w-full px-4 py-3 bg-cyber-bg border border-cyber-border rounded-lg text-cyber-text placeholder-cyber-muted/50 focus:outline-none focus:border-cyber-primary focus:ring-2 focus:ring-cyber-primary/20 transition-all" />
              </div>

              <div className="flex items-end">
                <button type="submit" disabled={loading || !owner.trim() || !repo.trim()}
                  className="w-full md:w-auto px-8 py-3 bg-gradient-to-r from-cyber-primary to-cyber-secondary text-white rounded-lg font-medium hover:from-cyber-primary/90 hover:to-cyber-secondary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-2 justify-center">
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>处理中...</span>
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      <span>开始分析</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {error && (
              <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm font-chinese">
                {error}
              </motion.div>
            )}
          </div>
        </motion.form>

        <AnimatePresence>
          {progress && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <ProgressIndicator progress={progress} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* 本地项目选择 */}
        {localProjects.length > 0 && (
          <motion.div
            className="mt-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 }}
          >
            <button
              onClick={() => setShowLocalProjects(!showLocalProjects)}
              className="w-full flex items-center justify-center gap-2 py-3 text-cyber-muted hover:text-cyber-primary transition-colors"
            >
              <FolderOpen className="w-4 h-4" />
              <span className="text-sm font-chinese">
                {showLocalProjects ? '收起' : '查看'} 本地已有数据 ({localProjects.length} 个项目)
              </span>
            </button>

            <AnimatePresence>
              {showLocalProjects && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="mt-4 bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-4 max-h-64 overflow-y-auto">
                    <div className="grid gap-2">
                      {localProjects.map((project, idx) => (
                        <button
                          key={idx}
                          onClick={() => onProjectReady(project.name)}
                          className="w-full flex items-center justify-between p-3 bg-cyber-bg/50 hover:bg-cyber-primary/10 rounded-lg border border-cyber-border/50 hover:border-cyber-primary/50 transition-all group"
                        >
                          <div className="flex items-center gap-3">
                            <Github className="w-5 h-5 text-cyber-muted group-hover:text-cyber-primary" />
                            <div className="text-left">
                              <div className="text-sm font-medium text-cyber-text group-hover:text-cyber-primary">
                                {project.full_name || project.name.replace('_', '/')}
                              </div>
                              {project.time_range && (
                                <div className="text-xs text-cyber-muted">
                                  {project.time_range.start} ~ {project.time_range.end} · {project.time_range.months} 个月
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {project.has_timeseries && (
                              <span className="text-xs bg-cyber-success/20 text-cyber-success px-2 py-0.5 rounded">指标</span>
                            )}
                            {project.has_text && (
                              <span className="text-xs bg-cyber-secondary/20 text-cyber-secondary px-2 py-0.5 rounded">文本</span>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </div>
    </div>
  )
}
