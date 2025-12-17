// 类型定义

export interface RepoInfo {
  name: string
  description: string
  stars?: number
  language: string
}

export interface MetricData {
  name: string
  data: (number | null)[]  // 支持 null 表示缺失值
  interpolated?: number[]   // 插值数据（用于显示缺失点位置）
  missingIndices?: number[] // 缺失值的索引
  missingRatio?: number     // 缺失率百分比
  color: string
  unit?: string
}

export interface TimeSeriesData {
  timeAxis: string[]
  metrics: {
    stars: MetricData
    commits: MetricData
    prs: MetricData
    contributors: MetricData
  }
}

// 分组时序数据类型
export interface MetricGroupData {
  name: string
  description: string
  metrics: Record<string, MetricData>
}

export interface GroupedTimeSeriesData {
  timeAxis: string[]
  startMonth?: string
  endMonth?: string
  groups: Record<string, MetricGroupData>
}

export interface IssueCategories {
  '功能需求': number
  'Bug修复': number
  '社区咨询': number
  '其他': number
}

export interface IssueData {
  month: string
  total: number
  categories: IssueCategories
}

export interface KeywordData {
  word: string
  weight: number
}

export interface WaveData {
  metric: string
  metricKey?: string
  group?: string
  groupKey?: string
  month: string
  previousValue: number
  currentValue: number
  changeRate: number
  trend: '上升' | '下降'
  keywords: KeywordData[]
  explanation: string
  events?: EventData[]
}

export interface EventData {
  number?: number
  title: string
  comments?: number
  labels?: string[]
  url?: string
  state?: string
}

export interface ProjectSummary {
  aiSummary: string
  issueStats: {
    feature: number
    bug: number
    question: number
    other: number
    total: number
  }
  dataRange: {
    start: string | null
    end: string | null
    months_count: number
  }
}

export interface DemoData {
  repoKey: string
  repoInfo?: RepoInfo
  timeseries?: TimeSeriesData
  groupedTimeseries?: GroupedTimeSeriesData
  issueCategories: IssueData[]
  monthlyKeywords: Record<string, KeywordData[]>
  projectSummary?: ProjectSummary | null
  error?: string
}
