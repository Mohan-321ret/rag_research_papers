import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  MessageSquare,
  Search,
  GitFork,
  ArrowRight,
  FileText,
  MessageCircle,
  Bookmark,
  Lightbulb,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatCard } from "@/components/features/StatCard";
import { mockDashboardStats, mockUsageData } from "@/data/mockStats";
import { mockPapers } from "@/data/mockPapers";
import { mockActivities } from "@/data/mockUser";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const quickActions = [
  { title: "New Chat", description: "Ask a research question", icon: MessageSquare, path: "/chat", color: "bg-violet-500" },
  { title: "Search Papers", description: "Find relevant literature", icon: Search, path: "/search", color: "bg-blue-500" },
  { title: "Find Gaps", description: "Discover research gaps", icon: GitFork, path: "/gaps", color: "bg-emerald-500" },
];

const activityIcons = {
  chat: MessageCircle,
  search: Search,
  save: Bookmark,
  gap: Lightbulb,
  question: FileText,
};

export default function DashboardPage() {
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Welcome */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h2 className="text-2xl font-bold tracking-tight">Welcome back, Dr. Chen 👋</h2>
        <p className="text-muted-foreground mt-1">Here's what's happening with your research today.</p>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {mockDashboardStats.map((stat, i) => (
          <StatCard key={stat.id} {...stat} index={i} />
        ))}
      </div>

      {/* Quick Actions + Usage Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Quick Actions</h3>
          <div className="space-y-3">
            {quickActions.map((action, i) => (
              <motion.div
                key={action.title}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: 0.3 + i * 0.1 }}
              >
                <Link to={action.path}>
                  <Card className="group hover:shadow-md transition-all duration-200 hover:border-primary/30 cursor-pointer">
                    <CardContent className="p-4 flex items-center gap-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${action.color} text-white shrink-0`}>
                        <action.icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="text-sm font-semibold group-hover:text-primary transition-colors">{action.title}</h4>
                        <p className="text-xs text-muted-foreground">{action.description}</p>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground/50 group-hover:text-primary group-hover:translate-x-1 transition-all" />
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Usage Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
          className="lg:col-span-2"
        >
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Weekly Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={mockUsageData}>
                    <defs>
                      <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.55 0.22 264)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.55 0.22 264)" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorPapers" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="oklch(0.6 0.18 155)" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="oklch(0.6 0.18 155)" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                    <XAxis dataKey="name" className="text-xs" tick={{ fill: "oklch(0.556 0.02 264)" }} />
                    <YAxis className="text-xs" tick={{ fill: "oklch(0.556 0.02 264)" }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--popover)",
                        border: "1px solid var(--border)",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                    <Area type="monotone" dataKey="queries" stroke="oklch(0.55 0.22 264)" fillOpacity={1} fill="url(#colorQueries)" strokeWidth={2} />
                    <Area type="monotone" dataKey="papers" stroke="oklch(0.6 0.18 155)" fillOpacity={1} fill="url(#colorPapers)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Recent Activity + Recent Papers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">Recent Activity</CardTitle>
              <Badge variant="secondary" className="text-xs">{mockActivities.length} events</Badge>
            </CardHeader>
            <CardContent className="space-y-1 -mt-2">
              {mockActivities.slice(0, 5).map((activity) => {
                const Icon = activityIcons[activity.type];
                return (
                  <div key={activity.id} className="flex items-start gap-3 py-2.5 border-b last:border-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted shrink-0 mt-0.5">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium">{activity.title}</p>
                      <p className="text-xs text-muted-foreground truncate">{activity.description}</p>
                    </div>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap shrink-0">
                      <Clock className="h-3 w-3" />
                      {activity.timestamp}
                    </span>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </motion.div>

        {/* Recent Papers */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
        >
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">Recent Papers</CardTitle>
              <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                <Link to="/search">View all <ArrowRight className="ml-1 h-3 w-3" /></Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-1 -mt-2">
              {mockPapers.slice(0, 5).map((paper) => (
                <div key={paper.id} className="flex items-start gap-3 py-2.5 border-b last:border-0">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{paper.title}</p>
                    <p className="text-xs text-muted-foreground">{paper.authors[0]} et al. · {paper.year}</p>
                  </div>
                  <Badge variant="outline" className="text-xs shrink-0">
                    {(paper.similarityScore * 100).toFixed(0)}%
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
