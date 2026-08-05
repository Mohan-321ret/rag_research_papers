export interface ResearchGap {
  id: string;
  title: string;
  description: string;
  confidence: number;
  domain: string;
  evidence: string[];
  futureDirections: string[];
  relatedPaperCount: number;
  severity: "high" | "medium" | "low";
}

export const mockResearchGaps: ResearchGap[] = [
  {
    id: "g1",
    title: "Multimodal RAG for Scientific Figures and Diagrams",
    description: "Current RAG systems primarily handle textual data. There is a significant gap in retrieving and reasoning over scientific figures, charts, and diagrams embedded in research papers.",
    confidence: 92,
    domain: "Multimodal AI",
    evidence: [
      "Only 3 out of 127 surveyed RAG papers address image-based retrieval",
      "Scientific papers contain 40% information in non-textual formats",
      "No benchmark exists for multimodal scientific document retrieval",
    ],
    futureDirections: [
      "Develop vision-language models for scientific figure understanding",
      "Create benchmark datasets for multimodal scientific retrieval",
      "Integrate OCR and diagram parsing into RAG pipelines",
    ],
    relatedPaperCount: 23,
    severity: "high",
  },
  {
    id: "g2",
    title: "Cross-lingual Knowledge Retrieval in Academic Literature",
    description: "Existing RAG systems are predominantly English-centric, ignoring the vast body of scientific literature published in other languages, particularly Chinese, German, and Japanese.",
    confidence: 87,
    domain: "Multilingual NLP",
    evidence: [
      "35% of scientific publications are in non-English languages",
      "Cross-lingual retrieval accuracy drops by 42% vs monolingual",
      "Translation-based approaches lose domain-specific nuances",
    ],
    futureDirections: [
      "Train multilingual dense retrievers on scientific corpora",
      "Build parallel scientific document datasets for training",
      "Develop language-agnostic embedding spaces for academic text",
    ],
    relatedPaperCount: 45,
    severity: "high",
  },
  {
    id: "g3",
    title: "Temporal Awareness in Research Knowledge Bases",
    description: "Current systems treat all papers equally regardless of publication date, failing to account for evolving scientific consensus, retracted papers, or superseded findings.",
    confidence: 78,
    domain: "Knowledge Management",
    evidence: [
      "12% of retrieved citations reference superseded findings",
      "No RAG system incorporates temporal decay factors",
      "Retraction-aware retrieval is unexplored in literature",
    ],
    futureDirections: [
      "Implement temporal weighting in retrieval scoring",
      "Build retraction and correction tracking databases",
      "Develop citation freshness metrics for ranking",
    ],
    relatedPaperCount: 18,
    severity: "medium",
  },
  {
    id: "g4",
    title: "Evaluation Metrics for Scientific RAG Systems",
    description: "There is a lack of standardized evaluation metrics specifically designed for assessing RAG systems in scientific domains, beyond generic NLG metrics like BLEU and ROUGE.",
    confidence: 84,
    domain: "Evaluation & Benchmarking",
    evidence: [
      "Current metrics don't measure scientific accuracy of generated text",
      "No standard benchmark for research-focused RAG evaluation",
      "Human evaluation remains the only reliable quality measure",
    ],
    futureDirections: [
      "Design domain-specific evaluation metrics for scientific RAG",
      "Create automated fact-checking against scientific knowledge graphs",
      "Build expert-annotated evaluation datasets",
    ],
    relatedPaperCount: 31,
    severity: "medium",
  },
  {
    id: "g5",
    title: "Privacy-Preserving RAG for Sensitive Research Data",
    description: "RAG systems operating on proprietary or pre-publication research data lack mechanisms for privacy preservation, risking intellectual property leakage through generated responses.",
    confidence: 71,
    domain: "Privacy & Security",
    evidence: [
      "No existing RAG framework implements differential privacy",
      "67% of researchers express concern about IP leakage",
      "Federated RAG approaches remain purely theoretical",
    ],
    futureDirections: [
      "Apply differential privacy to retrieval and generation",
      "Develop federated RAG architectures for multi-institution collaboration",
      "Create access control mechanisms for knowledge base segments",
    ],
    relatedPaperCount: 14,
    severity: "low",
  },
];

export interface HeatmapCell {
  topic: string;
  subtopic: string;
  coverage: number;
}

export const mockHeatmapData: HeatmapCell[] = [
  { topic: "Retrieval", subtopic: "Dense", coverage: 85 },
  { topic: "Retrieval", subtopic: "Sparse", coverage: 92 },
  { topic: "Retrieval", subtopic: "Hybrid", coverage: 45 },
  { topic: "Retrieval", subtopic: "Multimodal", coverage: 15 },
  { topic: "Generation", subtopic: "Grounded", coverage: 72 },
  { topic: "Generation", subtopic: "Multi-hop", coverage: 38 },
  { topic: "Generation", subtopic: "Long-form", coverage: 55 },
  { topic: "Generation", subtopic: "Multilingual", coverage: 22 },
  { topic: "Evaluation", subtopic: "Automated", coverage: 68 },
  { topic: "Evaluation", subtopic: "Human", coverage: 78 },
  { topic: "Evaluation", subtopic: "Domain-specific", coverage: 25 },
  { topic: "Evaluation", subtopic: "Benchmark", coverage: 42 },
  { topic: "Applications", subtopic: "Academic", coverage: 75 },
  { topic: "Applications", subtopic: "Medical", coverage: 60 },
  { topic: "Applications", subtopic: "Legal", coverage: 48 },
  { topic: "Applications", subtopic: "Code", coverage: 82 },
];

export const topicNetworkNodes = [
  { id: "rag", label: "RAG", x: 50, y: 50, size: 40, group: "core" },
  { id: "retrieval", label: "Retrieval", x: 25, y: 30, size: 32, group: "core" },
  { id: "generation", label: "Generation", x: 75, y: 30, size: 32, group: "core" },
  { id: "dense", label: "Dense Retrieval", x: 15, y: 15, size: 24, group: "retrieval" },
  { id: "sparse", label: "Sparse Retrieval", x: 35, y: 12, size: 20, group: "retrieval" },
  { id: "embeddings", label: "Embeddings", x: 10, y: 45, size: 26, group: "retrieval" },
  { id: "llm", label: "LLM", x: 85, y: 15, size: 28, group: "generation" },
  { id: "grounding", label: "Grounding", x: 65, y: 12, size: 22, group: "generation" },
  { id: "eval", label: "Evaluation", x: 50, y: 80, size: 26, group: "eval" },
  { id: "benchmark", label: "Benchmarks", x: 35, y: 85, size: 18, group: "eval" },
  { id: "multimodal", label: "Multimodal", x: 80, y: 65, size: 20, group: "gap" },
  { id: "privacy", label: "Privacy", x: 20, y: 72, size: 16, group: "gap" },
  { id: "temporal", label: "Temporal", x: 65, y: 78, size: 18, group: "gap" },
];

export const topicNetworkEdges = [
  { from: "rag", to: "retrieval" },
  { from: "rag", to: "generation" },
  { from: "rag", to: "eval" },
  { from: "retrieval", to: "dense" },
  { from: "retrieval", to: "sparse" },
  { from: "retrieval", to: "embeddings" },
  { from: "generation", to: "llm" },
  { from: "generation", to: "grounding" },
  { from: "eval", to: "benchmark" },
  { from: "rag", to: "multimodal" },
  { from: "rag", to: "privacy" },
  { from: "rag", to: "temporal" },
];
