import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  confidence?: number
}

interface AIChatProps {
  projectName: string
}

export default function AIChat({ projectName }: AIChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: `你好！我是项目数据分析助手。我可以帮你了解 ${projectName.replace('_', '/')} 项目的相关信息。\n\n你可以问我：\n- 项目的基本信息\n- 统计数据\n- Issue情况\n- 时序趋势`,
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      role: 'user',
      content: input.trim()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch('/api/qa', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: userMessage.content,
          project: projectName
        })
      })

      const data = await response.json()

      if (data.error) {
        throw new Error(data.error)
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer || '抱歉，我无法回答这个问题。',
        sources: data.sources || [],
        confidence: data.confidence || 0
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        role: 'assistant',
        content: `抱歉，发生了错误：${error instanceof Error ? error.message : '未知错误'}`
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full bg-cyber-card/30 rounded-lg border border-cyber-border">
      {/* 标题栏 */}
      <div className="p-4 border-b border-cyber-border flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-cyber-primary/20 flex items-center justify-center">
          <Bot className="w-5 h-5 text-cyber-primary" />
        </div>
        <div>
          <h3 className="font-display font-bold text-cyber-text">AI 助手</h3>
          <p className="text-xs text-cyber-muted font-chinese">项目数据分析助手</p>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <AnimatePresence>
          {messages.map((message, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-cyber-primary/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-cyber-primary" />
                </div>
              )}
              
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  message.role === 'user'
                    ? 'bg-cyber-primary/20 text-cyber-text'
                    : 'bg-cyber-card border border-cyber-border text-cyber-text'
                }`}
              >
                <div className="whitespace-pre-wrap font-chinese text-sm leading-relaxed">
                  {message.content}
                </div>
                
                {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-cyber-border">
                    <div className="text-xs text-cyber-muted">
                      来源: {message.sources.join(', ')}
                      {message.confidence !== undefined && (
                        <span className="ml-2">
                          置信度: {Math.round(message.confidence * 100)}%
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-cyber-secondary/20 flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-cyber-secondary" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-cyber-primary/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-cyber-primary" />
            </div>
            <div className="bg-cyber-card border border-cyber-border rounded-lg p-3">
              <Loader2 className="w-4 h-4 text-cyber-primary animate-spin" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="p-4 border-t border-cyber-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入你的问题..."
            className="flex-1 px-4 py-2 bg-cyber-bg border border-cyber-border rounded-lg
                     text-cyber-text placeholder-cyber-muted focus:outline-none focus:border-cyber-primary
                     font-chinese"
            disabled={loading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="px-6 py-2 bg-cyber-primary/20 text-cyber-primary rounded-lg
                     hover:bg-cyber-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                     flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            <span className="font-chinese">发送</span>
          </button>
        </div>
      </div>
    </div>
  )
}
