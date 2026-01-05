import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Github, Sparkles, TrendingUp, Database, FolderOpen, Clock, ArrowRight } from 'lucide-react'
import ProgressIndicator from './ProgressIndicator'

interface HomePageProps {
  onProjectReady: (projectName: string) => void
}

interface ProjectInfo {
  name: string
  repo: string
  full_name?: string
  description?: string
  language?: string
  stars?: number
  documents_count?: number
  metrics_count?: number
}

export default function HomePage({ onProjectReady }: HomePageProps) {
  const [owner, setOwner] = useState('')
  const [repo, setRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [existingProjects, setExistingProjects] = useState<ProjectInfo[]>([])
  const [loadingProjects, setLoadingProjects] = useState(true)

  // 加载已有项目列表
  useEffect(() => {
    loadExistingProjects()
  }, [])

  const loadExistingProjects = async () => {
    setLoadingProjects(true)
    try {
      const response = await fetch('/api/projects')
      const data = await response.json()
      if (data.projects && Array.isArray(data.projects)) {
        setExistingProjects(data.projects)
      }
    } catch (err) {
      console.error('加载项目列表失败:', err)
    } finally {
      setLoadingProjects(false)
    }
  }

  const handleSelectProject = (projectName: string) => {
    onProjectReady(projectName)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!owner.trim() || !repo.trim()) {
      setError('请输入仓库所有者用户名和仓库名')
      return
    }

    setLoading(true)
    setError(null)
    setProgress(null)

    try {
      // 先检查数据是否已存在
      const checkResponse = await fetch(
        `/api/check_project?owner=${encodeURIComponent(owner.trim())}&repo=${encodeURIComponent(repo.trim())}`
      )
      const checkData = await checkResponse.json()
      
      if (checkData.exists) {
        // 数据已存在，直接使用
        setLoading(false)
        onProjectReady(checkData.projectName || `${owner.trim()}_${repo.trim()}`)
        return
      }

      // 数据不存在，开始爬取
      const eventSource = new EventSource(
        `/api/crawl?owner=${encodeURIComponent(owner.trim())}&repo=${encodeURIComponent(repo.trim())}`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'start') {
            setProgress({ step: 0, stepName: '开始', message: data.message, progress: 0 })
          } else if (data.type === 'exists') {
            // 数据已存在，直接使用
            setProgress({ step: 0, stepName: '数据已存在', message: data.message, progress: 100 })
            setLoading(false)
            eventSource.close()
            setTimeout(() => {
              onProjectReady(data.projectName || `${owner.trim()}_${repo.trim()}`)
            }, 500)
          } else if (data.type === 'metrics_ready') {
            setProgress({ step: data.step || 1, stepName: '指标数据就绪', message: data.message, progress: data.progress || 20 })
            setTimeout(() => {
              onProjectReady(data.projectName)
            }, 500)
          } else if (data.type === 'progress') {
            setProgress({ step: data.step, stepName: data.stepName, message: data.message, progress: data.progress })
          } else if (data.type === 'complete') {
            setProgress({ step: 9, stepName: '完成', message: data.message, progress: 100 })
            setLoading(false)
            eventSource.close()
            if (data.projectName) {
              setTimeout(() => onProjectReady(data.projectName), 500)
            } else {
              const projectName = `${owner.trim()}_${repo.trim()}`
              setTimeout(() => onProjectReady(projectName), 500)
            }
          } else if (data.type === 'error') {
            setError(data.message)
            setLoading(false)
            eventSource.close()
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
  }

  return (
    <div className="min-h-screen bg-cyber-bg bg-cyber-grid flex items-center justify-center px-4 py-8">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyber-primary/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-cyber-secondary/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 w-full max-w-5xl">
        <motion.div
          className="text-center mb-10"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="flex items-center justify-center gap-3 mb-4"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
          >
            <Sparkles className="w-10 h-10 text-cyber-primary" />
            <h1 className="text-5xl font-display font-bold bg-gradient-to-r from-cyber-primary via-cyber-secondary to-cyber-accent bg-clip-text text-transparent">
              OpenVista
            </h1>
          </motion.div>
          
          <p className="text-xl text-cyber-muted font-chinese mb-6">
            智能分析 GitHub 仓库生态数据
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-4"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <Database className="w-7 h-7 text-cyber-primary mb-2 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-1">数据采集</h3>
              <p className="text-xs text-cyber-muted font-chinese">自动爬取仓库数据</p>
            </motion.div>

            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-4"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
              <TrendingUp className="w-7 h-7 text-cyber-secondary mb-2 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-1">GitPulse 预测</h3>
              <p className="text-xs text-cyber-muted font-chinese">多模态时序预测模型</p>
            </motion.div>

            <motion.div className="bg-cyber-card/30 backdrop-blur-sm rounded-xl border border-cyber-border p-4"
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
              <Github className="w-7 h-7 text-cyber-accent mb-2 mx-auto" />
              <h3 className="text-sm font-display text-cyber-text mb-1">MaxKB 知识库</h3>
              <p className="text-xs text-cyber-muted font-chinese">智能问答分析</p>
            </motion.div>
          </div>
        </motion.div>

        {/* 已有项目快速访问 */}
        {existingProjects.length > 0 && (
          <motion.div
            className="mb-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div className="flex items-center gap-2 mb-4">
              <FolderOpen className="w-5 h-5 text-cyber-primary" />
              <h2 className="text-lg font-display font-semibold text-cyber-text">已加载的项目</h2>
              <span className="text-xs text-cyber-muted font-chinese">点击直接查看</span>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {existingProjects.slice(0, 6).map((project, index) => (
                <motion.button
                  key={project.name}
                  onClick={() => handleSelectProject(project.name)}
                  className="group p-4 bg-cyber-card/40 hover:bg-cyber-card/60 backdrop-blur-sm rounded-xl border border-cyber-border hover:border-cyber-primary/50 transition-all text-left"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.6 + index * 0.1 }}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Github className="w-4 h-4 text-cyber-muted flex-shrink-0" />
                        <span className="text-sm font-display font-semibold text-cyber-text truncate">
                          {project.full_name || project.name.replace('_', '/')}
                        </span>
                      </div>
                      {project.description && (
                        <p className="text-xs text-cyber-muted font-chinese line-clamp-2 mb-2">
                          {project.description}
                        </p>
                      )}
                      <div className="flex items-center gap-3 text-xs text-cyber-muted">
                        {project.language && (
                          <span className="flex items-center gap-1">
                            <span className="w-2 h-2 rounded-full bg-cyber-primary"></span>
                            {project.language}
                          </span>
                        )}
                        {project.stars !== undefined && (
                          <span>⭐ {project.stars}</span>
                        )}
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-cyber-muted group-hover:text-cyber-primary transition-colors flex-shrink-0 mt-1" />
                  </div>
                </motion.button>
              ))}
            </div>

            {existingProjects.length > 6 && (
              <p className="text-center text-xs text-cyber-muted mt-3 font-chinese">
                还有 {existingProjects.length - 6} 个项目...
              </p>
            )}
          </motion.div>
        )}

        {/* 新建项目表单 */}
        <motion.form onSubmit={handleSubmit} className="mb-6"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }}>
          <div className="bg-cyber-card/50 backdrop-blur-sm rounded-2xl border border-cyber-border p-6 shadow-2xl">
            <div className="flex items-center gap-2 mb-4">
              <Search className="w-5 h-5 text-cyber-secondary" />
              <h2 className="text-lg font-display font-semibold text-cyber-text">分析新仓库</h2>
            </div>

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

        {/* 加载中提示 */}
        {loadingProjects && existingProjects.length === 0 && (
          <motion.div
            className="text-center py-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Clock className="w-8 h-8 text-cyber-muted mx-auto mb-2 animate-pulse" />
            <p className="text-sm text-cyber-muted font-chinese">正在加载项目列表...</p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
