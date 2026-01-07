import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, Minimize2, Maximize2, ExternalLink, Sparkles } from 'lucide-react'

interface ChatAssistantProps {
  repoKey?: string
  projectName?: string
}

// MaxKB 嵌入配置
// 格式：http://localhost:8080/chat/{application_id}
const MAXKB_EMBED_URL = 'http://localhost:8080/chat/923a5da969ed8bec'

export default function ChatAssistant({ repoKey, projectName }: ChatAssistantProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // 获取项目名称用于显示
  const getProjectDisplay = () => {
    if (projectName) return projectName.replace('_', '/')
    if (repoKey) return repoKey
    return ''
  }

  // MaxKB 嵌入 URL
  const embedUrl = MAXKB_EMBED_URL

  // 在新窗口打开
  const openInNewWindow = () => {
    window.open(embedUrl, '_blank', 'width=500,height=700')
  }

  return (
    <>
      {/* 浮动按钮 */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-br from-cyber-primary to-cyber-secondary rounded-full shadow-lg shadow-cyber-primary/30 flex items-center justify-center z-50 group"
          >
            <MessageCircle className="w-6 h-6 text-white group-hover:scale-110 transition-transform" />
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* 聊天窗口 */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ 
              opacity: 1, 
              y: 0, 
              scale: 1
            }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className={`fixed ${
              isFullscreen 
                ? 'inset-4' 
                : 'bottom-6 right-6 w-[420px]'
            } bg-cyber-card/95 backdrop-blur-xl rounded-2xl shadow-2xl shadow-cyber-primary/20 border border-cyber-border z-50 flex flex-col overflow-hidden`}
            style={{ height: isMinimized ? 'auto' : (isFullscreen ? 'auto' : '600px') }}
          >
            {/* 标题栏 */}
            <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-cyber-primary/20 to-cyber-secondary/20 border-b border-cyber-border">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyber-primary to-cyber-secondary flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className="font-display font-bold text-cyber-text text-sm">OpenVista 智能助手</h3>
                  <p className="text-xs text-cyber-muted font-chinese">
                    {getProjectDisplay() ? `当前：${getProjectDisplay()}` : 'MaxKB 智能问答'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {/* 新窗口打开 */}
                <button
                  onClick={openInNewWindow}
                  className="p-1.5 hover:bg-cyber-surface rounded-lg transition-colors"
                  title="在新窗口打开"
                >
                  <ExternalLink className="w-4 h-4 text-cyber-muted" />
                </button>
                {/* 最小化/展开 */}
                <button
                  onClick={() => setIsMinimized(!isMinimized)}
                  className="p-1.5 hover:bg-cyber-surface rounded-lg transition-colors"
                  title={isMinimized ? '展开' : '最小化'}
                >
                  <Minimize2 className="w-4 h-4 text-cyber-muted" />
                </button>
                {/* 全屏切换 */}
                <button
                  onClick={() => setIsFullscreen(!isFullscreen)}
                  className="p-1.5 hover:bg-cyber-surface rounded-lg transition-colors"
                  title={isFullscreen ? '退出全屏' : '全屏'}
                >
                  <Maximize2 className="w-4 h-4 text-cyber-muted" />
                </button>
                {/* 关闭 */}
                <button
                  onClick={() => {
                    setIsOpen(false)
                    setIsFullscreen(false)
                  }}
                  className="p-1.5 hover:bg-cyber-surface rounded-lg transition-colors"
                  title="关闭"
                >
                  <X className="w-4 h-4 text-cyber-muted" />
                </button>
              </div>
            </div>

            {/* MaxKB iframe 嵌入 */}
            {!isMinimized && (
              <div className="flex-1 bg-white">
                <iframe
                  src={embedUrl}
                  className="w-full h-full border-0"
                  style={{ minHeight: isFullscreen ? 'calc(100vh - 120px)' : '540px' }}
                  allow="microphone"
                  title="OpenVista 智能助手"
                />
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
