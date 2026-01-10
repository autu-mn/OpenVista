import { useState, useEffect } from 'react'
import { Github, Loader2, Check } from 'lucide-react'
import { motion } from 'framer-motion'

interface Project {
  name: string
  repo?: string
  documents_count?: number
  metrics_count?: number
  exists: boolean
}

interface ProjectSearchProps {
  onSelectProject: (projectName: string) => void
  currentProject?: string
  onNavigateToHome?: (owner: string, repo: string) => void  // 新增：跳转到首页的回调
}

export default function ProjectSearch({ onSelectProject, currentProject, onNavigateToHome }: ProjectSearchProps) {
  const [owner, setOwner] = useState('')
  const [repo, setRepo] = useState('')
  const [suggestions, setSuggestions] = useState<Project[]>([])
  const [loading, setLoading] = useState(false)
  const [defaultProject, setDefaultProject] = useState<string>('')
  const [showSuggestions, setShowSuggestions] = useState(false)

  useEffect(() => {
    // 加载项目列表和默认项目
    fetchProjects()
  }, [])

  useEffect(() => {
    // 如果有默认项目且当前没有选择，自动选择默认项目
    if (defaultProject && !currentProject) {
      onSelectProject(defaultProject)
      // 解析默认项目名称
      const parts = defaultProject.split('_')
      if (parts.length >= 2) {
        setOwner(parts[0])
        setRepo(parts.slice(1).join('_'))
      }
    } else if (currentProject) {
      // 解析当前项目名称
      const parts = currentProject.split('_')
      if (parts.length >= 2) {
        setOwner(parts[0])
        setRepo(parts.slice(1).join('_'))
      }
    }
  }, [defaultProject, currentProject])

  const fetchProjects = async () => {
    setLoading(true)
    try {
      const response = await fetch('/api/projects')
      const data = await response.json()
      setSuggestions(data.projects || [])
      if (data.default) {
        setDefaultProject(data.default)
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleOwnerChange = (value: string) => {
    setOwner(value)
    if (value && repo) {
      searchProject(value, repo)
    } else {
      setShowSuggestions(false)
    }
  }

  const handleRepoChange = (value: string) => {
    setRepo(value)
    if (owner && value) {
      searchProject(owner, value)
    } else {
      setShowSuggestions(false)
    }
  }

  const searchProject = async (ownerName: string, repoName: string) => {
    const query = `${ownerName}_${repoName}`
    setLoading(true)
    try {
      const response = await fetch(`/api/projects/search?q=${encodeURIComponent(query)}`)
      const data = await response.json()
      setSuggestions(data.projects || [])
      setShowSuggestions(true)
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelect = (project: Project) => {
    onSelectProject(project.name)
    // 解析项目名称
    const parts = project.name.split('_')
    if (parts.length >= 2) {
      setOwner(parts[0])
      setRepo(parts.slice(1).join('_'))
    }
    setShowSuggestions(false)
  }

  const handleSubmit = async () => {
    if (owner && repo) {
      const projectName = `${owner}_${repo}`
      // 检查是否在建议列表中
      const found = suggestions.find(p => p.name === projectName)
      if (found && found.exists) {
        // 项目存在，直接选择
        handleSelect(found)
      } else {
        // 项目不在建议列表中，检查项目是否存在
        setLoading(true)
        try {
          const checkResponse = await fetch(
            `/api/check_project?owner=${encodeURIComponent(owner.trim())}&repo=${encodeURIComponent(repo.trim())}`
          )
          const checkData = await checkResponse.json()
          
          if (checkData.exists) {
            // 项目存在，选择它
            onSelectProject(checkData.projectName || projectName)
            setShowSuggestions(false)
          } else {
            // 项目不存在，跳转到首页进行爬取
            if (onNavigateToHome) {
              onNavigateToHome(owner.trim(), repo.trim())
            } else {
              // 如果没有提供回调，尝试直接选择（向后兼容）
              onSelectProject(projectName)
            }
            setShowSuggestions(false)
          }
        } catch (error) {
          console.error('检查项目失败:', error)
          // 出错时，如果有回调就跳转首页，否则尝试直接选择
          if (onNavigateToHome) {
            onNavigateToHome(owner.trim(), repo.trim())
          } else {
            onSelectProject(projectName)
          }
          setShowSuggestions(false)
        } finally {
          setLoading(false)
        }
      }
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent, field: 'owner' | 'repo') => {
    if (e.key === 'Enter') {
      if (field === 'owner') {
        // 焦点移到repo输入框
        const repoInput = document.getElementById('repo-input')
        repoInput?.focus()
      } else {
        handleSubmit()
      }
    }
  }

  // 过滤建议列表
  const filteredSuggestions = suggestions.filter(p => {
    if (!owner && !repo) return false
    const parts = p.name.split('_')
    if (parts.length < 2) return false
    
    const pOwner = parts[0].toLowerCase()
    const pRepo = parts.slice(1).join('_').toLowerCase()
    
    const ownerMatch = !owner || pOwner.includes(owner.toLowerCase())
    const repoMatch = !repo || pRepo.includes(repo.toLowerCase())
    
    return ownerMatch && repoMatch
  })

  return (
    <div className="relative w-full max-w-2xl">
      <motion.div
        className="flex items-center gap-2 p-3 bg-cyber-card/50 border border-cyber-border rounded-lg
                   hover:border-cyber-primary/50 transition-all"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Github className="w-5 h-5 text-cyber-muted flex-shrink-0" />
        
        <div className="flex-1 flex items-center gap-2">
          <input
            type="text"
            value={owner}
            onChange={(e) => handleOwnerChange(e.target.value)}
            onKeyPress={(e) => handleKeyPress(e, 'owner')}
            onFocus={() => {
              if (owner && repo) {
                setShowSuggestions(true)
              }
            }}
            placeholder="用户名"
            className="flex-1 px-3 py-2 bg-cyber-bg border border-cyber-border rounded
                     text-cyber-text placeholder-cyber-muted focus:outline-none focus:border-cyber-primary
                     font-chinese text-sm"
          />
          
          <span className="text-cyber-muted font-mono">/</span>
          
          <input
            id="repo-input"
            type="text"
            value={repo}
            onChange={(e) => handleRepoChange(e.target.value)}
            onKeyPress={(e) => handleKeyPress(e, 'repo')}
            onFocus={() => {
              if (owner && repo) {
                setShowSuggestions(true)
              }
            }}
            placeholder="仓库名"
            className="flex-1 px-3 py-2 bg-cyber-bg border border-cyber-border rounded
                     text-cyber-text placeholder-cyber-muted focus:outline-none focus:border-cyber-primary
                     font-chinese text-sm"
          />
          
          <button
            onClick={handleSubmit}
            disabled={!owner || !repo || loading}
            className="px-4 py-2 bg-cyber-primary/20 text-cyber-primary rounded
                     hover:bg-cyber-primary/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                     flex items-center gap-2 font-chinese text-sm"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            <span>确认</span>
          </button>
        </div>
      </motion.div>

      {/* 建议列表 */}
      {showSuggestions && filteredSuggestions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="absolute top-full left-0 right-0 mt-2 bg-cyber-card border border-cyber-border rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto"
        >
          <div className="p-2">
            {filteredSuggestions.map((project) => {
              const parts = project.name.split('_')
              const pOwner = parts[0]
              const pRepo = parts.slice(1).join('_')
              
              return (
                <button
                  key={project.name}
                  onClick={() => handleSelect(project)}
                  className={`w-full text-left p-3 rounded-lg transition-all mb-1
                    ${currentProject === project.name
                      ? 'bg-cyber-primary/20 border border-cyber-primary'
                      : 'hover:bg-cyber-card/50 border border-transparent hover:border-cyber-border'
                    }`}
                >
                  <div className="flex items-center gap-2">
                    <Github className="w-4 h-4 text-cyber-muted flex-shrink-0" />
                    <div className="flex-1">
                      <div className="font-medium text-cyber-text">
                        <span className="text-cyber-primary">{pOwner}</span>
                        <span className="text-cyber-muted"> / </span>
                        <span>{pRepo}</span>
                      </div>
                      {project.documents_count !== undefined && (
                        <div className="text-xs text-cyber-muted mt-1">
                          {project.documents_count} 个文档 · {project.metrics_count || 0} 个指标
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </motion.div>
      )}
    </div>
  )
}
