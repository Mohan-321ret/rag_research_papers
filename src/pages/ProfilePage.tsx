import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  User,
  Mail,
  Calendar,
  FileText,
  MessageSquare,
  Database,
  Loader2,
  AlertCircle,
  Edit3,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { fetchProfile, fetchDashboard, type UserProfile, type DashboardStats } from "@/lib/api";

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchProfile().catch(() => null),
      fetchDashboard().catch(() => null),
    ]).then(([prof, dash]) => {
      setProfile(prof);
      setStats(dash?.stats ?? null);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, []);

  const initials = profile?.full_name
    ? profile.full_name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2)
    : profile?.email?.slice(0, 2).toUpperCase() ?? "?";

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}><CardContent className="p-6 animate-pulse"><div className="h-20 bg-muted rounded" /></CardContent></Card>
          ))}
        </div>
      ) : (
        <>
          {/* Profile Header */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardContent className="p-6">
                <div className="flex flex-col sm:flex-row items-start gap-6">
                  <Avatar className="h-20 w-20">
                    <AvatarFallback className="bg-gradient-to-br from-primary to-purple-600 text-white text-2xl font-bold">
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 space-y-3">
                    <div className="flex items-start justify-between">
                      <div>
                        <h2 className="text-2xl font-bold">{profile?.full_name ?? "Researcher"}</h2>
                        <p className="text-muted-foreground capitalize">{profile?.role ?? "user"}</p>
                      </div>
                      <Button variant="outline" size="sm" className="gap-1.5">
                        <Edit3 className="h-3.5 w-3.5" /> Edit Profile
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <Mail className="h-4 w-4" /> {profile?.email ?? "—"}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <User className="h-4 w-4" /> {profile?.id?.slice(0, 8) ?? "—"}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Calendar className="h-4 w-4" />
                        Joined {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : "—"}
                      </span>
                    </div>
                    <div>
                      <Badge variant={profile?.is_active ? "outline" : "secondary"} className={profile?.is_active ? "border-emerald-300 text-emerald-600" : ""}>
                        {profile?.is_active ? "Active account" : "Inactive"}
                      </Badge>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Stats from backend */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { label: "Documents Ingested", value: stats?.total_documents ?? 0, icon: FileText },
              { label: "Research Queries", value: stats?.total_queries ?? 0, icon: MessageSquare },
              { label: "Chunks Indexed", value: stats?.total_chunks ?? 0, icon: Database },
            ].map((stat, i) => (
              <motion.div key={stat.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.08 }}>
                <Card>
                  <CardContent className="p-5 flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                      <stat.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{stat.value.toLocaleString()}</p>
                      <p className="text-xs text-muted-foreground">{stat.label}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>

          {/* System Status */}
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <Card>
              <CardHeader><CardTitle className="text-base">System Status</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="rounded-lg border p-3 space-y-1">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">LLM Provider</p>
                    <p className="text-sm font-medium">Groq · qwen/qwen3.8-27b</p>
                    <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-300 border">Active</Badge>
                  </div>
                  <div className="rounded-lg border p-3 space-y-1">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Answer Quality</p>
                    <p className="text-sm font-medium">
                      Avg confidence: {stats?.avg_confidence != null ? `${(stats.avg_confidence * 100).toFixed(0)}%` : "—"}
                    </p>
                    {stats?.hallucination_rate != null && (
                      <p className="text-xs text-muted-foreground">
                        Hallucination rate: {(stats.hallucination_rate * 100).toFixed(1)}%
                      </p>
                    )}
                  </div>
                  <div className="rounded-lg border p-3 space-y-1">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Knowledge Drift</p>
                    <p className="text-sm font-medium">{stats?.drift_events ?? 0} drift events detected</p>
                  </div>
                  <div className="rounded-lg border p-3 space-y-1">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Conflicts</p>
                    <p className="text-sm font-medium">{stats?.conflict_count ?? 0} conflicts resolved</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
    </div>
  );
}
