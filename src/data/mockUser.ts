export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar: string;
  institution: string;
  department: string;
  role: string;
  researchInterests: string[];
  joinedDate: string;
  papersRead: number;
  questionsAsked: number;
  collectionsCreated: number;
}

export const mockUser: UserProfile = {
  id: "u1",
  name: "Dr. Sarah Chen",
  email: "sarah.chen@stanford.edu",
  avatar: "",
  institution: "Stanford University",
  department: "Computer Science",
  role: "Research Scholar",
  researchInterests: [
    "Natural Language Processing",
    "Information Retrieval",
    "Machine Learning",
    "Knowledge Graphs",
    "Scientific Discovery",
  ],
  joinedDate: "January 2024",
  papersRead: 342,
  questionsAsked: 156,
  collectionsCreated: 12,
};

export interface Activity {
  id: string;
  type: "search" | "chat" | "save" | "gap" | "question";
  title: string;
  description: string;
  timestamp: string;
}

export const mockActivities: Activity[] = [
  {
    id: "a1",
    type: "chat",
    title: "AI Research Chat",
    description: "Asked about RAG vs fine-tuning approaches",
    timestamp: "2 hours ago",
  },
  {
    id: "a2",
    type: "search",
    title: "Paper Search",
    description: "Searched for 'dense passage retrieval embeddings'",
    timestamp: "3 hours ago",
  },
  {
    id: "a3",
    type: "save",
    title: "Saved Paper",
    description: "Added 'Attention Is All You Need' to Transformers collection",
    timestamp: "5 hours ago",
  },
  {
    id: "a4",
    type: "gap",
    title: "Research Gap Found",
    description: "Identified gap in multimodal RAG for scientific images",
    timestamp: "Yesterday",
  },
  {
    id: "a5",
    type: "question",
    title: "Generated Questions",
    description: "Generated 5 research questions for knowledge grounding",
    timestamp: "Yesterday",
  },
  {
    id: "a6",
    type: "search",
    title: "Paper Search",
    description: "Searched for 'vector database comparison benchmarks'",
    timestamp: "2 days ago",
  },
  {
    id: "a7",
    type: "chat",
    title: "AI Research Chat",
    description: "Discussed transformer scaling laws with AI assistant",
    timestamp: "3 days ago",
  },
];
