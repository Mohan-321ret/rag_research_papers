import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  MessageSquare,
  Search,
  GitFork,
  Quote,
  Lightbulb,
  BookMarked,
  User,
  Settings,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  HelpCircle,
  Globe,
  Upload,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/useTheme";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/upload", label: "Upload Papers", icon: Upload },
  { path: "/chat", label: "AI Research Chat", icon: MessageSquare },
  { path: "/search", label: "Paper Search", icon: Search },
  { path: "/external", label: "External Sources", icon: Globe },
  { path: "/gaps", label: "Research Gaps", icon: GitFork },
  { path: "/citations", label: "Citations", icon: Quote },
  { path: "/questions", label: "Question Generator", icon: HelpCircle },
  { path: "/collections", label: "Collections", icon: BookMarked },
];

const bottomNavItems = [
  { path: "/profile", label: "Profile", icon: User },
  { path: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 68 : 260 }}
      transition={{ duration: 0.2, ease: "easeInOut" }}
      className="fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-sidebar text-sidebar-foreground"
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-3 px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "auto" }}
              exit={{ opacity: 0, width: 0 }}
              className="overflow-hidden whitespace-nowrap"
            >
              <span className="text-base font-bold tracking-tight">ScholarAI</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <Separator />

      {/* Main nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link key={item.path} to={item.path}>
              <div
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className={cn("h-4.5 w-4.5 shrink-0", isActive && "text-primary")} />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className="overflow-hidden whitespace-nowrap"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>
            </Link>
          );
        })}
      </nav>

      <Separator />

      {/* Bottom nav */}
      <div className="space-y-1 px-2 py-3">
        {bottomNavItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link key={item.path} to={item.path}>
              <div
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-sm"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className={cn("h-4.5 w-4.5 shrink-0", isActive && "text-primary")} />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className="overflow-hidden whitespace-nowrap"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </div>
            </Link>
          );
        })}

        {/* Theme toggle */}
        <button
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground transition-all duration-150 cursor-pointer"
        >
          {resolvedTheme === "dark" ? (
            <Sun className="h-4.5 w-4.5 shrink-0" />
          ) : (
            <Moon className="h-4.5 w-4.5 shrink-0" />
          )}
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                className="overflow-hidden whitespace-nowrap"
              >
                {resolvedTheme === "dark" ? "Light Mode" : "Dark Mode"}
              </motion.span>
            )}
          </AnimatePresence>
        </button>

        {/* Collapse toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full justify-center"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>
    </motion.aside>
  );
}
