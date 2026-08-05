import { motion } from "framer-motion";
import {
  User,
  Mail,
  Building2,
  GraduationCap,
  Calendar,
  FileText,
  MessageSquare,
  FolderOpen,
  Edit3,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { mockUser } from "@/data/mockUser";

export default function ProfilePage() {
  const stats = [
    { label: "Papers Read", value: mockUser.papersRead, icon: FileText },
    { label: "Questions Asked", value: mockUser.questionsAsked, icon: MessageSquare },
    { label: "Collections", value: mockUser.collectionsCreated, icon: FolderOpen },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Profile Header */}
        <Card>
          <CardContent className="p-6">
            <div className="flex flex-col sm:flex-row items-start gap-6">
              <Avatar className="h-20 w-20">
                <AvatarFallback className="bg-gradient-to-br from-primary to-purple-600 text-white text-2xl font-bold">
                  SC
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-2xl font-bold">{mockUser.name}</h2>
                    <p className="text-muted-foreground">{mockUser.role}</p>
                  </div>
                  <Button variant="outline" size="sm" className="gap-1.5">
                    <Edit3 className="h-3.5 w-3.5" /> Edit Profile
                  </Button>
                </div>

                <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Mail className="h-4 w-4" /> {mockUser.email}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Building2 className="h-4 w-4" /> {mockUser.institution}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <GraduationCap className="h-4 w-4" /> {mockUser.department}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Calendar className="h-4 w-4" /> Joined {mockUser.joinedDate}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08 }}
          >
            <Card>
              <CardContent className="p-5 flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <stat.icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <p className="text-xs text-muted-foreground">{stat.label}</p>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Research Interests */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Research Interests</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {mockUser.researchInterests.map((interest) => (
                <Badge key={interest} variant="secondary" className="py-1.5 px-3">
                  {interest}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Connected Accounts */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Connected Accounts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              { name: "Google Scholar", connected: true, email: "sarah.chen@gmail.com" },
              { name: "ORCID", connected: true, email: "0000-0002-1234-5678" },
              { name: "GitHub", connected: false, email: "" },
            ].map((account) => (
              <div key={account.name} className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium">{account.name}</p>
                  {account.connected && (
                    <p className="text-xs text-muted-foreground">{account.email}</p>
                  )}
                </div>
                <Button variant={account.connected ? "outline" : "default"} size="sm">
                  {account.connected ? "Disconnect" : "Connect"}
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
