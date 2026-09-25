export interface ChatConversation {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: string;
  messageCount: number;
}

export interface WorkflowStep {
  icon: string;
  label: string;
  duration: number;
}

export const ragWorkflowSteps: WorkflowStep[] = [
  { icon: "🔍", label: "Searching papers in knowledge base...", duration: 1000 },
  { icon: "🧮", label: "Encoding query with transformer model...", duration: 800 },
  { icon: "📄", label: "Retrieving top-k relevant documents...", duration: 1200 },
  { icon: "🤖", label: "Generating AI response with citations...", duration: 1500 },
];

export const mockChatHistory: ChatConversation[] = [
  {
    id: "c1",
    title: "RAG vs Fine-tuning comparison",
    lastMessage: "RAG is generally preferred when...",
    timestamp: "2 hours ago",
    messageCount: 8,
  },
  {
    id: "c2",
    title: "Dense retrieval embeddings",
    lastMessage: "Sentence-BERT provides dense...",
    timestamp: "Yesterday",
    messageCount: 12,
  },
  {
    id: "c3",
    title: "Transformer architecture overview",
    lastMessage: "The self-attention mechanism...",
    timestamp: "2 days ago",
    messageCount: 6,
  },
  {
    id: "c4",
    title: "FAISS indexing strategies",
    lastMessage: "For large-scale datasets...",
    timestamp: "3 days ago",
    messageCount: 4,
  },
  {
    id: "c5",
    title: "Scaling laws for LLMs",
    lastMessage: "The empirical relationship between...",
    timestamp: "1 week ago",
    messageCount: 15,
  },
];

export const mockAIResponse = {
  content: `Based on the retrieved documents, here is a comprehensive analysis of **Retrieval-Augmented Generation (RAG)** and its applications in scientific research:

## Key Findings

**1. RAG Architecture Overview**
RAG combines the strengths of retrieval-based and generative approaches. The system first retrieves relevant documents from a knowledge base using dense passage retrieval, then conditions the language model's generation on the retrieved context [1][2].

**2. Advantages Over Pure LLM Approaches**
- **Reduced Hallucination**: By grounding responses in retrieved documents, RAG significantly reduces factual errors compared to pure generative models [1].
- **Up-to-date Information**: The knowledge base can be updated without retraining the model, ensuring responses reflect the latest research [6].
- **Source Attribution**: Every claim can be traced back to specific documents, enabling verifiable outputs [1][8].

**3. Performance Metrics**
Studies show that RAG-based systems achieve:
- 23% improvement in factual accuracy over GPT-4 alone [7]
- 91% precision in document retrieval using dense embeddings [2]
- 40% reduction in response latency with FAISS indexing [5]

## Methodology Comparison

| Approach | Accuracy | Latency | Updatability |
|----------|----------|---------|-------------|
| Pure LLM | 72% | Low | Requires retraining |
| RAG (Sparse) | 81% | Medium | Easy update |
| RAG (Dense) | 89% | Medium | Easy update |
| RAG (Hybrid) | 93% | Higher | Easy update |

## Recommendations
For scientific research applications, a **hybrid RAG approach** combining dense retrieval (Sentence-BERT) with sparse methods (BM25) offers the best balance of accuracy and coverage [2][8][9].`,
  sources: [
    { id: "p1", title: "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", relevance: 0.96, url: "https://arxiv.org/abs/2005.11401", source: "arxiv" },
    { id: "p2", title: "Dense Passage Retrieval for Open-Domain Question Answering", relevance: 0.93, url: "https://arxiv.org/abs/2004.04906", source: "arxiv" },
    { id: "p5", title: "FAISS: A Library for Efficient Similarity Search", relevance: 0.91, url: "https://arxiv.org/abs/1702.08734", source: "arxiv" },
    { id: "p8", title: "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks", relevance: 0.92, url: "https://arxiv.org/abs/1908.10084", source: "arxiv" },
    { id: "p14", title: "A Survey of Large Language Models for Research Assistance", relevance: 0.94, url: "https://arxiv.org/abs/2304.01852", source: "arxiv" },
  ],
};

export const sampleQuestions = [
  "What are the key differences between RAG and fine-tuning approaches?",
  "How does dense passage retrieval improve question answering?",
  "Explain the transformer architecture and self-attention mechanism",
  "What are the best practices for building a research knowledge base?",
  "Compare vector database solutions for AI applications",
  "How do scaling laws affect language model performance?",
];
