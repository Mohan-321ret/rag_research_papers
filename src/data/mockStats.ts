export interface DashboardStat {
  id: string;
  label: string;
  value: string;
  numericValue: number;
  suffix: string;
  description: string;
  trend: string;
  trendPositive: boolean;
  icon: string;
}

export const mockDashboardStats: DashboardStat[] = [
  {
    id: "s1",
    label: "Papers Indexed",
    value: "10,000",
    numericValue: 10000,
    suffix: "+",
    description: "Scientific papers in knowledge base",
    trend: "+1,200 this month",
    trendPositive: true,
    icon: "FileText",
  },
  {
    id: "s2",
    label: "Faster Literature Review",
    value: "70",
    numericValue: 70,
    suffix: "%",
    description: "Speed improvement over manual review",
    trend: "+5% from last quarter",
    trendPositive: true,
    icon: "Zap",
  },
  {
    id: "s3",
    label: "Gap Detection Accuracy",
    value: "87",
    numericValue: 87,
    suffix: "%",
    description: "Research gap identification precision",
    trend: "+3% improvement",
    trendPositive: true,
    icon: "Target",
  },
  {
    id: "s4",
    label: "Questions Generated",
    value: "3–8",
    numericValue: 5,
    suffix: "",
    description: "Research questions per analysis session",
    trend: "Avg. 5.2 per session",
    trendPositive: true,
    icon: "HelpCircle",
  },
];

export const mockUsageData = [
  { name: "Mon", queries: 45, papers: 12, gaps: 3 },
  { name: "Tue", queries: 52, papers: 18, gaps: 5 },
  { name: "Wed", queries: 38, papers: 8, gaps: 2 },
  { name: "Thu", queries: 65, papers: 22, gaps: 7 },
  { name: "Fri", queries: 71, papers: 25, gaps: 4 },
  { name: "Sat", queries: 28, papers: 6, gaps: 1 },
  { name: "Sun", queries: 33, papers: 10, gaps: 3 },
];
