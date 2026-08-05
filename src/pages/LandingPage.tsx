import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  MessageSquare,
  Search,
  GitFork,
  Quote,
  HelpCircle,
  BookMarked,
  ArrowRight,
  Sparkles,
  Zap,
  Shield,
  ChevronRight,
  Star,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAnimatedCounter } from "@/hooks/useAnimatedCounter";

const features = [
  {
    icon: MessageSquare,
    title: "AI Research Chat",
    description: "Ask complex research questions and get AI-powered answers with citations from your knowledge base.",
    color: "from-violet-500 to-purple-600",
  },
  {
    icon: Search,
    title: "Semantic Paper Search",
    description: "Find relevant papers using meaning-based search powered by transformer embeddings.",
    color: "from-blue-500 to-cyan-500",
  },
  {
    icon: GitFork,
    title: "Research Gap Discovery",
    description: "Automatically identify unexplored areas and gaps in the literature with confidence scores.",
    color: "from-emerald-500 to-teal-500",
  },
  {
    icon: Quote,
    title: "Citation Recommendations",
    description: "Get intelligent citation suggestions based on your paper's content and context.",
    color: "from-amber-500 to-orange-500",
  },
  {
    icon: HelpCircle,
    title: "Question Generator",
    description: "Generate novel research questions from any topic or abstract using AI analysis.",
    color: "from-pink-500 to-rose-500",
  },
  {
    icon: BookMarked,
    title: "Smart Collections",
    description: "Organize, tag, and manage your research papers in intelligent collections.",
    color: "from-indigo-500 to-blue-600",
  },
];

const steps = [
  {
    step: "01",
    title: "Upload & Index",
    description: "Upload research papers and documents. Our system automatically chunks, embeds, and indexes them using state-of-the-art transformer models.",
  },
  {
    step: "02",
    title: "Ask & Discover",
    description: "Ask questions in natural language. The RAG pipeline retrieves relevant passages and generates comprehensive answers with source citations.",
  },
  {
    step: "03",
    title: "Analyze & Innovate",
    description: "Discover research gaps, generate questions, and get citation recommendations to accelerate your research and find novel directions.",
  },
];

function AnimatedStat({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  const count = useAnimatedCounter(value, 2500);
  return (
    <div className="text-center">
      <div className="text-4xl font-bold tracking-tight text-white">
        {count.toLocaleString()}{suffix}
      </div>
      <div className="mt-1 text-sm text-white/70">{label}</div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="text-lg font-bold tracking-tight">ScholarAI</span>
          </Link>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/login">Sign In</Link>
            </Button>
            <Button size="sm" asChild>
              <Link to="/login">
                Get Started <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        {/* Background gradient */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-purple-500/5" />
          <div className="absolute top-20 left-1/4 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
          <div className="absolute bottom-10 right-1/4 h-96 w-96 rounded-full bg-purple-500/10 blur-3xl" />
        </div>

        <div className="mx-auto max-w-7xl px-6 py-24 md:py-32">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mx-auto max-w-4xl text-center"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="mb-6 inline-flex items-center gap-2 rounded-full border bg-muted/50 px-4 py-1.5 text-sm"
            >
              <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />
              <span>Final Year Project — RAG Research Assistant</span>
            </motion.div>

            <h1 className="text-4xl font-bold tracking-tight sm:text-6xl md:text-7xl">
              Your AI-Powered{" "}
              <span className="bg-gradient-to-r from-primary via-purple-500 to-pink-500 bg-clip-text text-transparent animate-gradient">
                Scientific Research
              </span>{" "}
              Assistant
            </h1>

            <p className="mt-6 text-lg text-muted-foreground leading-relaxed max-w-2xl mx-auto">
              Accelerate your literature review with Retrieval-Augmented Generation. Search papers semantically,
              discover research gaps, generate questions, and get AI-powered answers grounded in real citations.
            </p>

            <div className="mt-10 flex items-center justify-center gap-4">
              <Button size="xl" asChild>
                <Link to="/login">
                  Start Researching <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button size="xl" variant="outline" asChild>
                <Link to="/login">
                  <Sparkles className="mr-2 h-4 w-4" /> Watch Demo
                </Link>
              </Button>
            </div>
          </motion.div>

          {/* Floating feature cards preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.3 }}
            className="mt-16 mx-auto max-w-5xl"
          >
            <div className="rounded-2xl border bg-card/80 backdrop-blur-sm shadow-2xl shadow-primary/5 p-1">
              <div className="rounded-xl bg-gradient-to-b from-muted/50 to-background p-8 md:p-12">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
                  <div className="space-y-2">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
                      <Search className="h-6 w-6 text-primary" />
                    </div>
                    <h3 className="font-semibold">Semantic Search</h3>
                    <p className="text-sm text-muted-foreground">Find papers by meaning, not just keywords</p>
                  </div>
                  <div className="space-y-2">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10">
                      <Zap className="h-6 w-6 text-emerald-500" />
                    </div>
                    <h3 className="font-semibold">RAG Pipeline</h3>
                    <p className="text-sm text-muted-foreground">Retrieve, augment, and generate with citations</p>
                  </div>
                  <div className="space-y-2">
                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500/10">
                      <Shield className="h-6 w-6 text-amber-500" />
                    </div>
                    <h3 className="font-semibold">Grounded Answers</h3>
                    <p className="text-sm text-muted-foreground">Every claim traced to a source document</p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-24 bg-muted/30">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Everything you need for research
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
              A comprehensive suite of AI-powered tools designed to accelerate every stage of your literature review.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
              >
                <Card className="h-full hover:shadow-lg transition-all duration-300 hover:-translate-y-1 group">
                  <CardContent className="p-6">
                    <div className={`mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${feature.color} text-white shadow-sm`}>
                      <feature.icon className="h-5 w-5" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2 group-hover:text-primary transition-colors">{feature.title}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-20 bg-gradient-to-br from-primary via-purple-600 to-indigo-700 relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAxMCAwIEwgMCAwIDAgMTAiIGZpbGw9Im5vbmUiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS1vcGFjaXR5PSIwLjA1IiBzdHJva2Utd2lkdGg9IjEiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjZ3JpZCkiLz48L3N2Zz4=')] opacity-50" />
        <div className="mx-auto max-w-7xl px-6 relative">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="grid grid-cols-2 md:grid-cols-4 gap-8"
          >
            <AnimatedStat value={10000} suffix="+" label="Papers Indexed" />
            <AnimatedStat value={70} suffix="%" label="Faster Literature Review" />
            <AnimatedStat value={87} suffix="%" label="Gap Detection Accuracy" />
            <AnimatedStat value={5} suffix=" avg" label="Questions Generated" />
          </motion.div>
        </div>
      </section>

      {/* How it Works */}
      <section className="py-24">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">How it works</h2>
            <p className="mt-4 text-lg text-muted-foreground">Three simple steps to accelerate your research</p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((step, i) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.15 }}
                className="relative"
              >
                <div className="text-7xl font-black text-primary/10 mb-4">{step.step}</div>
                <h3 className="text-xl font-semibold mb-3">{step.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{step.description}</p>
                {i < steps.length - 1 && (
                  <ChevronRight className="hidden md:block absolute top-12 -right-4 h-6 w-6 text-muted-foreground/30" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 bg-muted/30">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl mb-4">
              Ready to transform your research?
            </h2>
            <p className="text-lg text-muted-foreground mb-8">
              Join researchers who use ScholarAI to discover insights faster and produce better science.
            </p>
            <Button size="xl" asChild>
              <Link to="/login">
                Get Started Free <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8">
        <div className="mx-auto max-w-7xl px-6 flex items-center justify-between text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>ScholarAI — Final Year Project</span>
          </div>
          <span>Scientific Research Assistant using RAG</span>
        </div>
      </footer>
    </div>
  );
}
