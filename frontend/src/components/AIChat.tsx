import { Bot, ExternalLink } from 'lucide-react'
import { motion } from 'framer-motion'

interface AIChatProps {
  projectName: string
  compact?: boolean
}

// MaxKB 公开对话链接 - 可在 .env 中配置 VITE_MAXKB_CHAT_URL
const MAXKB_CHAT_URL = import.meta.env.VITE_MAXKB_CHAT_URL || 'http://localhost:8080/chat/923a5da969ed8bec'

export default function AIChat({ projectName, compact = false }: AIChatProps) {
  const displayName = projectName.replace('_', '/')

  // 紧凑模式（用于嵌入其他面板）
  if (compact) {
    return (
      <div className="flex flex-col h-[500px] bg-gradient-to-br from-gray-800/80 to-gray-900/80 rounded-xl border border-purple-500/30 overflow-hidden">
        {/* 紧凑模式标题栏 */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700/50 bg-gray-800/50">
          <div className="flex items-center gap-2">
            <Bot className="w-5 h-5 text-purple-400" />
            <span className="text-sm text-gray-300">MaxKB AI 助手</span>
          </div>
          <a
            href={MAXKB_CHAT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
            title="在新窗口中打开"
          >
            <ExternalLink className="w-3 h-3" />
            <span>新窗口</span>
          </a>
        </div>
        {/* MaxKB iframe */}
        <iframe
          src={MAXKB_CHAT_URL}
          style={{ width: '100%', height: '100%' }}
          frameBorder="0"
          allow="microphone"
          title="MaxKB AI 助手"
        />
      </div>
    )
  }

  // 完整模式
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-br from-gray-800/60 to-gray-900/60 rounded-2xl border border-purple-500/30 overflow-hidden shadow-2xl"
    >
      {/* 标题栏 */}
      <div className="px-6 py-4 bg-gradient-to-r from-purple-600/20 to-indigo-600/20 border-b border-purple-500/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg">
                <Bot className="w-6 h-6 text-white" />
              </div>
              <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-gray-800 animate-pulse"></div>
            </div>
            <div>
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                AI 数据分析助手
              </h3>
              <p className="text-sm text-purple-300">
                MaxKB 知识库 · {displayName}
              </p>
            </div>
          </div>
          {/* 在新窗口中打开按钮 */}
          <a
            href={MAXKB_CHAT_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-blue-600/80 to-cyan-600/80 
                     text-white text-sm rounded-lg hover:from-blue-500 hover:to-cyan-500 
                     transition-all shadow-md hover:shadow-lg"
            title="在新窗口中打开"
          >
            <ExternalLink className="w-4 h-4" />
            <span className="hidden sm:inline">新窗口打开</span>
          </a>
        </div>
      </div>

      {/* MaxKB iframe */}
      <iframe
        src={MAXKB_CHAT_URL}
        style={{ width: '100%', height: '600px' }}
        frameBorder="0"
        allow="microphone"
        title="MaxKB AI 助手"
      />
    </motion.div>
  )
}
