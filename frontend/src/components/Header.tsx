import { motion } from 'framer-motion'
import { Database, Github, Sparkles, MessageSquare } from 'lucide-react'
import { Link } from 'react-router-dom'

interface HeaderProps {
  repoName?: string
  onBackToHome?: () => void
}

export default function Header({ repoName, onBackToHome }: HeaderProps) {
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

          {/* 右侧：功能按钮 */}
          <motion.div
            className="flex items-center gap-4"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3, duration: 0.5 }}
          >
            <Link
              to="/ai"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-cyber-card border border-cyber-border
                       hover:border-cyber-primary/50 hover:bg-cyber-primary/10 transition-all
                       text-cyber-muted hover:text-cyber-primary"
              title="AI助手"
            >
              <MessageSquare className="w-5 h-5" />
              <span className="font-chinese text-sm hidden sm:inline">AI助手</span>
            </Link>
            
            {repoName && (
              <div className="hidden lg:flex items-center gap-2 px-4 py-2 rounded-lg bg-cyber-card border border-cyber-border">
                <Github className="w-4 h-4 text-cyber-muted" />
                <span className="text-cyber-primary font-mono text-sm">{repoName.replace('_', '/')}</span>
              </div>
            )}
          </motion.div>
        </div>
      </div>

      {/* 底部装饰线 */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyber-primary/50 to-transparent" />
    </header>
  )
}

function FeatureTag({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2 text-cyber-muted hover:text-cyber-primary transition-colors">
      {icon}
      <span className="text-sm font-chinese">{text}</span>
    </div>
  )
}
