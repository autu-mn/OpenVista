import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Github, Sparkles, TrendingUp, Database } from 'lucide-react'
import ProgressIndicator from './ProgressIndicator'

interface HomePageProps {
  onProjectReady: (projectName: string) => void
}

export default function HomePage({ onProjectReady }: HomePageProps) {
  const [owner, setOwner] = useState('')
  const [repo, setRepo] = useState('')
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

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
      const eventSource = new EventSource(
        `/api/crawl?owner=${encodeURIComponent(owner.trim())}&repo=${encodeURIComponent(repo.trim())}&max_issues=100&max_prs=100&max_commits=100`
      )

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          if (data.type === 'start') {
            setProgress({ step: 0, stepName: '开始', message: data.message, progress: 0 })
          } else if (data.type === 'progress') {
            setProgress({ step: data.step, stepName: data.stepName, message: data.message, progress: data.progress })
          } else if (data.type === 'complete') {
            setProgress({ step: 12, stepName: '完成', message: data.message, progress: 100 })
            setLoading(false)
            eventSource.close()
            setTimeout(() => onProjectReady(data.projectName), 1500)
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
              DataPulse
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
      </div>
    </div>
  )
}
