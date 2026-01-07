import { motion } from 'framer-motion'
import { Database, Github, Book } from 'lucide-react'

interface HeaderProps {
  repoName?: string
  onBackToHome?: () => void
  onOpenDocs?: () => void
}

export default function Header({ repoName, onBackToHome, onOpenDocs }: HeaderProps) {
  return (
    <header className="relative border-b border-cyber-border bg-cyber-surface/80 backdrop-blur-xl">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <motion.div 
            className="flex items-center gap-3 cursor-pointer group"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5 }}
            onClick={onBackToHome}
            title={onBackToHome ? "返回首页" : undefined}
          >
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyber-primary via-cyber-secondary to-cyber-accent flex items-center justify-center transition-transform group-hover:scale-105">
                <Database className="w-6 h-6 text-cyber-bg" />
              </div>
              <div className="absolute -top-1 -right-1 w-3 h-3 bg-cyber-success rounded-full animate-pulse" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold gradient-text group-hover:opacity-80 transition-opacity">
                OpenVista
              </h1>
              <p className="text-xs text-cyber-muted font-chinese">
                GitHub 仓库生态画像分析平台
              </p>
            </div>
          </motion.div>

          {/* 右侧：仓库信息 + 文档按钮 */}
          <motion.div
            className="flex items-center gap-4"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            {repoName && (
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyber-card border border-cyber-border">
                <Github className="w-4 h-4 text-cyber-muted" />
                <span className="text-cyber-primary font-mono text-sm">{repoName.replace('_', '/')}</span>
              </div>
            )}
            
            {/* 文档按钮 */}
            {onOpenDocs && (
              <button
                onClick={onOpenDocs}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyber-card border border-cyber-border
                         text-cyber-muted hover:text-cyber-primary hover:border-cyber-primary/50 transition-all"
                title="使用文档"
              >
                <Book className="w-4 h-4" />
                <span className="text-sm font-chinese">文档</span>
              </button>
            )}
          </motion.div>
        </div>
      </div>

      {/* 底部装饰线 */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyber-primary/50 to-transparent" />
    </header>
  )
}

