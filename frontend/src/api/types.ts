export type DemoRole = "business" | "team";

export interface DemoIdentity {
  id: string;
  name: string;
  role: DemoRole;
  team_id: string | null;
}

export interface FieldErrors {
  [field: string]: string;
}

export interface ErrorResponse {
  code: string;
  message: string;
  field_errors?: FieldErrors;
}

export interface TaskFields {
  title: string;
  topic: string;
  context: string;
  need: string;
  users: string;
  data_materials: string;
  constraints: string;
  expected_result: string;
  success_criteria: string;
  contact: string;
  consultation: string;
}

export type RatingLevel = "draft" | "working" | "ready" | "priority";

export interface RatingCategory {
  key: string;
  label: string;
  points: number;
  max_points: number;
  basis: string[];
}

export interface Rating {
  total: number;
  level: RatingLevel;
  categories: RatingCategory[];
  missing: string[];
}

export interface TaskResponse extends TaskFields {
  id: string;
  owner_id: string;
  confirmed: boolean;
  published: boolean;
  version: number;
  rating: Rating;
  published_rating: Rating | null;
  created_at: string;
  updated_at: string;
}

export interface Answer {
  question: string;
  answer: string;
}

export interface QuestionResponse {
  questions: string[];
}

export interface CatalogResponse {
  items: TaskResponse[];
}

export interface ProposalCreate {
  idea: string;
  plan: string;
  duration: string;
  prototype_url: string;
}

export type ProposalStatus = "pending" | "selected" | "rejected";

export interface ProposalResponse extends ProposalCreate {
  id: string;
  task_id: string;
  team_id: string;
  status: ProposalStatus;
  created_at: string;
}

export interface ProposalListResponse {
  items: ProposalResponse[];
}

export type ProposalDecision = "selected" | "rejected";

export interface MilestoneCreate {
  description: string;
  result_url: string;
}

export type MilestoneStatus = "submitted" | "confirmed" | "changes_requested";

export interface MilestoneResponse extends MilestoneCreate {
  id: string;
  proposal_id: string;
  status: MilestoneStatus;
  comment: string;
  points_awarded: number;
}

export type MilestoneDecision = "confirmed" | "changes_requested";
