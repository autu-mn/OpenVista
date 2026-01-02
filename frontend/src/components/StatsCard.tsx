import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface StatsCardProps {
  icon: React.ReactNode
  title: string
  value: number
  change: string
  color: 'primary' | 'secondary' | 'accent' | 'success'
}

// 格式化大数字
const formatValue = (value: number): string => {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`
  }
  if (value >= 10000) {
    return `${(value / 1000).toFixed(1)}K`
  }
  return value.toLocaleString()
}

export default function StatsCard({ icon, title, value, change, color }: StatsCardProps) {
  const colorClasses = {
    primary: {
      bg: 'bg-cyber-primary/10',
      border: 'border-cyber-primary/30',
      icon: 'text-cyber-primary',
      glow: 'hover:shadow-[0_0_30px_rgba(0,245,212,0.2)]',
      accent: 'text-cyber-primary'
    },
    secondary: {
      bg: 'bg-cyber-secondary/10',
      border: 'border-cyber-secondary/30',
      icon: 'text-cyber-secondary',
      glow: 'hover:shadow-[0_0_30px_rgba(123,97,255,0.2)]',
      accent: 'text-cyber-secondary'
    },
    accent: {
      bg: 'bg-cyber-accent/10',
      border: 'border-cyber-accent/30',
      icon: 'text-cyber-accent',
      glow: 'hover:shadow-[0_0_30px_rgba(255,107,157,0.2)]',
      accent: 'text-cyber-accent'
    },
    success: {
      bg: 'bg-cyber-success/10',
      border: 'border-cyber-success/30',
      icon: 'text-cyber-success',
      glow: 'hover:shadow-[0_0_30px_rgba(0,255,136,0.2)]',
      accent: 'text-cyber-success'
    }
  }

  const classes = colorClasses[color]
  const isPositive = change.startsWith('+')
  const isNegative = change.startsWith('-')
  const hasChange = change && change !== ''

  return (
    <motion.div
      className={clsx(
        'relative p-5 rounded-xl border transition-all duration-300',
        'bg-cyber-card/50 backdrop-blur-sm',
        classes.border,
        classes.glow
      )}
      whileHover={{ scale: 1.02, y: -2 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      {/* 背景装饰 */}
      <div className={clsx('absolute top-0 right-0 w-20 h-20 rounded-full blur-3xl opacity-15', classes.bg)} />
      
      <div className="relative z-10">
        {/* 顶部：图标 + 变化率 */}
        <div className="flex items-start justify-between mb-3">
          <div className={clsx('p-2.5 rounded-lg', classes.bg)}>
            <span className={classes.icon}>{icon}</span>
          </div>
          
          {/* 变化率标签 */}
          {hasChange ? (
            <div className={clsx(
              'flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-full',
              isPositive ? 'text-cyber-success bg-cyber-success/15' : 
              isNegative ? 'text-cyber-accent bg-cyber-accent/15' : 
              'text-cyber-muted bg-cyber-muted/10'
            )}>
              {isPositive ? <TrendingUp className="w-3 h-3" /> : 
               isNegative ? <TrendingDown className="w-3 h-3" /> : 
               <Minus className="w-3 h-3" />}
              <span>{change}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-xs text-cyber-muted/50 px-2 py-1">
              <Minus className="w-3 h-3" />
              <span>--</span>
            </div>
          )}
        </div>

        {/* 数值（突出显示） */}
        <div className="mb-1">
          <p className={clsx('text-2xl font-display font-bold', classes.accent)}>
            {formatValue(value)}
          </p>
        </div>

        {/* 标题（指标名称） */}
        <h3 className="text-cyber-muted text-xs font-chinese tracking-wide">{title}</h3>
      </div>

      {/* 底部装饰线 */}
      <div className={clsx(
        'absolute bottom-0 left-4 right-4 h-0.5 rounded-full opacity-50',
        classes.bg
      )} />
    </motion.div>
  )
}

