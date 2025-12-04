import { motion } from 'framer-motion'
import { CheckCircle2, Loader2 } from 'lucide-react'

interface ProgressData {
  step: number
  stepName: string
  message: string
  progress: number
}

interface ProgressIndicatorProps {
  progress: ProgressData
}

const stepNames = [
  '获取 OpenDigger 基础指标',
  '获取仓库核心信息',
  '获取 README',
  '获取 Issues',
  '获取 Pull Requests',
  '获取标签',
  '获取提交历史',
  '获取贡献者',
  '获取发布版本',
  '计算备用指标',
  '保存数据',
  '处理数据',
  '完成'
]

export default function ProgressIndicator({ progress }: ProgressIndicatorProps) {
  const isComplete = progress.progress >= 100
  const currentStepIndex = Math.min(progress.step, stepNames.length - 1)

  return (
    <div className="bg-cyber-card/50 backdrop-blur-sm rounded-2xl border border-cyber-border p-6 shadow-2xl">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-cyber-text font-chinese">{progress.stepName}</span>
          <span className="text-sm font-mono text-cyber-muted">{progress.progress}%</span>
        </div>
        
        <div className="relative h-3 bg-cyber-bg rounded-full overflow-hidden border border-cyber-border">
          <motion.div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-cyber-primary to-cyber-secondary rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progress.progress}%` }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          />
          {!isComplete && (
            <motion.div className="absolute inset-y-0 bg-cyber-primary/30" style={{ width: '30%' }}
              animate={{ x: ['-100%', '400%'] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
            />
          )}
        </div>
      </div>

      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 mt-1">
          {isComplete ? (
            <CheckCircle2 className="w-6 h-6 text-green-400" />
          ) : (
            <Loader2 className="w-6 h-6 text-cyber-primary animate-spin" />
          )}
        </div>
        
        <div className="flex-1">
          <p className="text-cyber-text font-chinese mb-2">{progress.message}</p>
          
          <div className="mt-4 space-y-2">
            {stepNames.slice(0, currentStepIndex + 1).map((stepName, index) => (
              <motion.div key={index} className="flex items-center gap-2 text-sm"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}>
                <div className={`w-2 h-2 rounded-full ${
                  index < currentStepIndex ? 'bg-green-400' : 
                  index === currentStepIndex ? 'bg-cyber-primary animate-pulse' : 
                  'bg-cyber-border'
                }`} />
                <span className={`font-chinese ${
                  index < currentStepIndex ? 'text-cyber-muted line-through' : 
                  index === currentStepIndex ? 'text-cyber-primary font-medium' : 
                  'text-cyber-muted/50'
                }`}>
                  {stepName}
                </span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
