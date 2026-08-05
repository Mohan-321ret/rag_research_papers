import { motion } from "framer-motion";
import { Card, CardContent } from "@/components/ui/card";
import { useAnimatedCounter } from "@/hooks/useAnimatedCounter";
import {
  FileText,
  Zap,
  Target,
  HelpCircle,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

const iconMap: Record<string, LucideIcon> = {
  FileText,
  Zap,
  Target,
  HelpCircle,
};

interface StatCardProps {
  label: string;
  value: string;
  numericValue: number;
  suffix: string;
  description: string;
  trend: string;
  trendPositive: boolean;
  icon: string;
  index?: number;
}

export function StatCard({
  label,
  numericValue,
  suffix,
  description,
  trend,
  trendPositive,
  icon,
  index = 0,
}: StatCardProps) {
  const animatedValue = useAnimatedCounter(numericValue, 2000);
  const IconComp = iconMap[icon] || FileText;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
    >
      <Card className="hover:shadow-md transition-shadow duration-200">
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">{label}</p>
              <div className="flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight">
                  {label === "Questions Generated" ? "3–8" : animatedValue.toLocaleString()}
                </span>
                {suffix && label !== "Questions Generated" && (
                  <span className="text-xl font-semibold text-primary">{suffix}</span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{description}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <IconComp className="h-5 w-5 text-primary" />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-1.5">
            <TrendingUp
              className={cn(
                "h-3.5 w-3.5",
                trendPositive ? "text-emerald-500" : "text-red-500"
              )}
            />
            <span
              className={cn(
                "text-xs font-medium",
                trendPositive ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
              )}
            >
              {trend}
            </span>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
