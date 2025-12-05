import { motion } from 'framer-motion'
import { Star, GitFork, Eye, Calendar, Code, Users, Tag, ExternalLink, TrendingUp } from 'lucide-react'

interface RepoInfo {
  full_name: string
  description: string
  homepage?: string
  language?: string
  stars: number
  forks: number
  watchers: number
  open_issues: number
  created_at: string
  updated_at: string
  license?: string
  topics?: string[]
  openrank?: number  // OpenRank 评分
}

interface RepoHeaderProps {
  repoInfo: RepoInfo
  openRankValue?: number  // 从时序数据中获取的最新 OpenRank 值
}

export default function RepoHeader({ repoInfo, openRankValue }: RepoHeaderProps) {
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '未知'
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return (num / 1000000).toFixed(1) + 'M'
    } else if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
  }

  const formatOpenRank = (value: number) => {
    return value.toFixed(2)
  }

  return (
    <motion.div
      className="bg-gradient-to-br from-cyber-card/50 to-cyber-card/30 backdrop-blur-xl rounded-2xl p-8 mb-8 border border-cyber-primary/20 shadow-2xl"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {/* 仓库标题和描述 */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-3">
          <motion.h1 
            className="text-3xl font-bold text-cyber-text bg-gradient-to-r from-cyber-primary to-cyber-secondary bg-clip-text text-transparent"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
          >
            {repoInfo.full_name}
          </motion.h1>
          {repoInfo.homepage && (
            <motion.a
              href={repoInfo.homepage}
              target="_blank"
              rel="noopener noreferrer"
              className="text-cyber-primary hover:text-cyber-secondary transition-colors"
              initial={{ opacity: 0, scale: 0 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 }}
            >
              <ExternalLink className="w-5 h-5" />
            </motion.a>
          )}
        </div>
        
        {repoInfo.description && (
          <motion.p 
            className="text-cyber-text-secondary text-lg leading-relaxed"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            {repoInfo.description}
          </motion.p>
        )}
      </div>

      {/* OpenRank 评分 - 如果存在则显示 */}
      {openRankValue !== undefined && openRankValue > 0 && (
        <motion.div
          className="mb-6 p-6 bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-red-500/10 rounded-xl border-2 border-amber-500/30"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl shadow-lg">
                <TrendingUp className="w-8 h-8 text-white" />
              </div>
              <div>
                <div className="text-sm text-cyber-text-secondary font-medium mb-1">OpenRank 影响力评分</div>
                <div className="text-4xl font-bold bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 bg-clip-text text-transparent">
                  {formatOpenRank(openRankValue)}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-cyber-text-secondary mb-2">全球开源项目影响力排名</div>
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-amber-500/20 rounded-full">
                <span className="w-2 h-2 bg-amber-500 rounded-full animate-pulse"></span>
                <span className="text-sm font-medium text-amber-500">活跃监测中</span>
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* 统计数据网格 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <motion.div
          className="bg-cyber-bg/30 rounded-xl p-4 border border-cyber-primary/10 hover:border-cyber-primary/30 transition-all"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Star className="w-5 h-5 text-yellow-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-cyber-text">{formatNumber(repoInfo.stars)}</div>
              <div className="text-xs text-cyber-text-secondary">Stars</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="bg-cyber-bg/30 rounded-xl p-4 border border-cyber-primary/10 hover:border-cyber-primary/30 transition-all"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.35 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <GitFork className="w-5 h-5 text-blue-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-cyber-text">{formatNumber(repoInfo.forks)}</div>
              <div className="text-xs text-cyber-text-secondary">Forks</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="bg-cyber-bg/30 rounded-xl p-4 border border-cyber-primary/10 hover:border-cyber-primary/30 transition-all"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <Eye className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-cyber-text">{formatNumber(repoInfo.watchers)}</div>
              <div className="text-xs text-cyber-text-secondary">Watchers</div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="bg-cyber-bg/30 rounded-xl p-4 border border-cyber-primary/10 hover:border-cyber-primary/30 transition-all"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.45 }}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-red-500/10 rounded-lg">
              <Users className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <div className="text-2xl font-bold text-cyber-text">{formatNumber(repoInfo.open_issues)}</div>
              <div className="text-xs text-cyber-text-secondary">Issues</div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* 详细信息 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {repoInfo.language && (
          <motion.div
            className="flex items-center gap-2 text-sm"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5 }}
          >
            <Code className="w-4 h-4 text-cyber-primary" />
            <span className="text-cyber-text-secondary">语言:</span>
            <span className="text-cyber-text font-medium">{repoInfo.language}</span>
          </motion.div>
        )}

        {repoInfo.license && (
          <motion.div
            className="flex items-center gap-2 text-sm"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.55 }}
          >
            <Tag className="w-4 h-4 text-cyber-secondary" />
            <span className="text-cyber-text-secondary">许可证:</span>
            <span className="text-cyber-text font-medium">{repoInfo.license}</span>
          </motion.div>
        )}

        <motion.div
          className="flex items-center gap-2 text-sm"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
        >
          <Calendar className="w-4 h-4 text-green-500" />
          <span className="text-cyber-text-secondary">创建于:</span>
          <span className="text-cyber-text font-medium">{formatDate(repoInfo.created_at)}</span>
        </motion.div>

        <motion.div
          className="flex items-center gap-2 text-sm"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.65 }}
        >
          <Calendar className="w-4 h-4 text-blue-500" />
          <span className="text-cyber-text-secondary">更新于:</span>
          <span className="text-cyber-text font-medium">{formatDate(repoInfo.updated_at)}</span>
        </motion.div>
      </div>

      {/* 主题标签 */}
      {repoInfo.topics && repoInfo.topics.length > 0 && (
        <motion.div
          className="mt-6 pt-6 border-t border-cyber-primary/10"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Tag className="w-4 h-4 text-cyber-primary" />
            <span className="text-sm font-medium text-cyber-text-secondary">主题标签</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {repoInfo.topics.map((topic, index) => (
              <motion.span
                key={topic}
                className="px-3 py-1 bg-cyber-primary/10 text-cyber-primary rounded-full text-xs font-medium border border-cyber-primary/20 hover:bg-cyber-primary/20 transition-colors"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.7 + index * 0.05 }}
              >
                {topic}
              </motion.span>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

