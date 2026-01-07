import { motion } from 'framer-motion'
import { clsx } from 'clsx'

interface StatsCardProps {
  icon: React.ReactNode
  title: string
  value: number
  change: string
  color: 'primary' | 'secondary' | 'accent' | 'success'
}

export default function StatsCard({ icon, title, value, change, color }: StatsCardProps) {
  const colorClasses = {
    primary: {
      bg: 'bg-cyber-primary/10',
      border: 'border-cyber-primary/30',
      icon: 'text-cyber-primary',
      glow: 'hover:shadow-[0_0_30px_rgba(0,245,212,0.2)]'
    },
    secondary: {
      bg: 'bg-cyber-secondary/10',
      border: 'border-cyber-secondary/30',
      icon: 'text-cyber-secondary',
      glow: 'hover:shadow-[0_0_30px_rgba(123,97,255,0.2)]'
    },
    accent: {
      bg: 'bg-cyber-accent/10',
      border: 'border-cyber-accent/30',
      icon: 'text-cyber-accent',
      glow: 'hover:shadow-[0_0_30px_rgba(255,107,157,0.2)]'
    },
    success: {
      bg: 'bg-cyber-success/10',
      border: 'border-cyber-success/30',
      icon: 'text-cyber-success',
      glow: 'hover:shadow-[0_0_30px_rgba(0,255,136,0.2)]'
    }
  }

  const classes = colorClasses[color]
  const isPositive = change.startsWith('+')

  return (
    <motion.div
      className={clsx(
        'relative p-6 rounded-xl border transition-all duration-300',
        'bg-cyber-card/50 backdrop-blur-sm',
        classes.border,
        classes.glow
      )}
      whileHover={{ scale: 1.02 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      {/* 背景装饰 */}
      <div className={clsx('absolute top-0 right-0 w-24 h-24 rounded-full blur-3xl opacity-20', classes.bg)} />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className={clsx('p-3 rounded-lg', classes.bg)}>
            <span className={classes.icon}>{icon}</span>
          </div>
          {change && (
            <span className={clsx(
              'text-sm font-medium px-2 py-1 rounded',
              isPositive ? 'text-cyber-success bg-cyber-success/10' : 'text-cyber-accent bg-cyber-accent/10'
            )}>
              {change}
            </span>
          )}
        </div>

        <h3 className="text-cyber-muted text-sm font-chinese mb-1">{title}</h3>
        <p className="text-3xl font-display font-bold text-cyber-text">
          {value.toLocaleString()}
        </p>
      </div>

      {/* 底部装饰线 */}
      <div className={clsx(
        'absolute bottom-0 left-4 right-4 h-0.5 rounded-full',
        classes.bg
      )} />
    </motion.div>
  )
}

