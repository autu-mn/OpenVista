import { motion } from 'framer-motion'
import { CheckCircle2, Loader2, Database, FileText, GitBranch, Layers, Check } from 'lucide-react'

interface ProgressData {
  step: number
  stepName: string
  message: string
  progress: number
}

interface ProgressIndicatorProps {
  progress: ProgressData
}

// 与后端 /api/crawl 的步骤对齐
const stepConfig = [
  {
    id: 1,
    name: '获取指标数据',
    description: '从 OpenDigger 获取核心指标',
    icon: Database,
    progressRange: [0, 20]
  },
  {
    id: 2,
    name: '爬取描述文本',
    description: '获取 README、LICENSE 等文档',
    icon: FileText,
    progressRange: [20, 40]
  },
  {
    id: 3,
    name: '爬取时序文本',
    description: '爬取 Issue/PR/Commit/Release',
    icon: GitBranch,
    progressRange: [40, 70]
  },
  {
    id: 4,
    name: '时序对齐处理',
    description: '合并时序文本和时序指标',
    icon: Layers,
    progressRange: [70, 90]
  },
  {
    id: 5,
    name: '加载完成',
    description: '数据加载到服务中',
    icon: Check,
    progressRange: [90, 100]
  }
]

// 根据进度百分比确定当前步骤
const getStepFromProgress = (progress: number): number => {
  for (let i = stepConfig.length - 1; i >= 0; i--) {
    if (progress >= stepConfig[i].progressRange[0]) {
      return i
    }
  }
  return 0
}

export default function ProgressIndicator({ progress }: ProgressIndicatorProps) {
  const isComplete = progress.progress >= 100
  
  // 根据进度百分比计算当前步骤
  const currentStepIndex = getStepFromProgress(progress.progress)

  return (
    <div className="bg-cyber-card/50 backdrop-blur-sm rounded-2xl border border-cyber-border p-6 shadow-2xl">
      {/* 进度条头部 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {isComplete ? (
              <CheckCircle2 className="w-5 h-5 text-green-400" />
            ) : (
              <Loader2 className="w-5 h-5 text-cyber-primary animate-spin" />
            )}
            <span className="text-sm font-medium text-cyber-text font-chinese">
              {progress.stepName || stepConfig[currentStepIndex]?.name || '正在处理...'}
            </span>
          </div>
          <span className="text-sm font-mono text-cyber-primary font-bold">{progress.progress}%</span>
        </div>
        
        {/* 进度条 */}
        <div className="relative h-3 bg-cyber-bg rounded-full overflow-hidden border border-cyber-border">
          <motion.div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyber-primary to-cyber-secondary rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progress.progress}%` }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          />
          {!isComplete && (
            <motion.div 
              className="absolute inset-y-0 bg-white/20" 
              style={{ width: '30%' }}
              animate={{ x: ['-100%', '400%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
            />
          )}
        </div>
      </div>

      {/* 当前状态消息 */}
      <div className="mb-5 px-3 py-2 bg-cyber-surface/50 rounded-lg border border-cyber-border/50">
        <p className="text-cyber-text/90 font-chinese text-sm">{progress.message}</p>
      </div>

      {/* 步骤列表 */}
      <div className="space-y-1">
        {stepConfig.map((step, index) => {
          const StepIcon = step.icon
          const isPast = index < currentStepIndex
          const isCurrent = index === currentStepIndex
          const isFuture = index > currentStepIndex
          
          return (
            <motion.div 
              key={step.id}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
                isCurrent ? 'bg-cyber-primary/10 border border-cyber-primary/30' : 
                isPast ? 'bg-cyber-surface/30' : ''
              }`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              {/* 步骤状态指示器 */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                isPast ? 'bg-green-500/20 text-green-400' :
                isCurrent ? 'bg-cyber-primary/20 text-cyber-primary' :
                'bg-cyber-border/30 text-cyber-muted/50'
              }`}>
                {isPast ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : isCurrent ? (
                  <motion.div
                    animate={{ scale: [1, 1.1, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    <StepIcon className="w-4 h-4" />
                  </motion.div>
                ) : (
                  <StepIcon className="w-4 h-4" />
                )}
              </div>
              
              {/* 步骤信息 */}
              <div className="flex-1 min-w-0">
                <div className={`text-sm font-medium font-chinese ${
                  isPast ? 'text-cyber-muted line-through' :
                  isCurrent ? 'text-cyber-primary' :
                  'text-cyber-muted/50'
                }`}>
                  {step.name}
                </div>
                {isCurrent && (
                  <div className="text-xs text-cyber-muted mt-0.5 font-chinese">
                    {step.description}
                  </div>
                )}
              </div>
              
              {/* 步骤进度 */}
              {isCurrent && (
                <div className="flex-shrink-0">
                  <motion.div 
                    className="w-2 h-2 rounded-full bg-cyber-primary"
                    animate={{ opacity: [1, 0.4, 1] }}
                    transition={{ duration: 1, repeat: Infinity }}
                  />
                </div>
              )}
              {isPast && (
                <div className="flex-shrink-0 text-xs text-green-400 font-mono">
                  完成
                </div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* 完成状态 */}
      {isComplete && (
        <motion.div 
          className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle2 className="w-5 h-5" />
            <span className="font-medium font-chinese">数据加载完成！</span>
          </div>
        </motion.div>
      )}
    </div>
  )
}
