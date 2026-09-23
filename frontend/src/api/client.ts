import type {
  Answer,
  CatalogResponse,
  DemoIdentity,
  ErrorResponse,
  FieldErrors,
  MilestoneCreate,
  MilestoneDecision,
  MilestoneResponse,
  ProposalCreate,
  ProposalDecision,
  ProposalListResponse,
  ProposalResponse,
  RatingLevel,
  TaskFields,
  TaskResponse,
  QuestionResponse,
} from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

interface ApiClientOptions {
  baseUrl?: string;
  getIdentityId?: () => string | null;
  fetchImplementation?: typeof fetch;
}

interface RequestOptions extends RequestInit {
  authenticated?: boolean;
}
export interface CatalogQuery {
  topic?: string;
  level?: RatingLevel;
}

export interface ApiClient {
  demoIdentities(): Promise<DemoIdentity[]>;
  createTask(fields: Partial<TaskFields>): Promise<TaskResponse>;
  task(taskId: string): Promise<TaskResponse>;
  updateTask(
    taskId: string,
    fields: Partial<TaskFields>,
  ): Promise<TaskResponse>;
  questions(taskId: string): Promise<QuestionResponse>;
  composeTask(taskId: string, answers: Answer[]): Promise<TaskResponse>;
  confirmTask(taskId: string): Promise<TaskResponse>;
  publishTask(taskId: string): Promise<TaskResponse>;
  catalog(query?: CatalogQuery): Promise<CatalogResponse>;
  businessTasks(): Promise<CatalogResponse>;
  createProposal(
    taskId: string,
    proposal: ProposalCreate,
  ): Promise<ProposalResponse>;
  proposals(taskId: string): Promise<ProposalListResponse>;
  decideProposal(
    proposalId: string,
    decision: ProposalDecision,
  ): Promise<ProposalResponse>;
  teamProposals(): Promise<ProposalListResponse>;
  createMilestone(
    proposalId: string,
    milestone: MilestoneCreate,
  ): Promise<MilestoneResponse>;
  reviewMilestone(
    milestoneId: string,
    decision: MilestoneDecision,
    comment: string,
  ): Promise<MilestoneResponse>;
}


export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: FieldErrors;

  constructor(status: number, payload: ErrorResponse) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.fieldErrors = payload.field_errors ?? {};
  }
}

export function createApiClient({
  baseUrl = API_BASE_URL,
  getIdentityId = () => null,
  fetchImplementation = fetch,
}: ApiClientOptions = {}): ApiClient {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { authenticated = true, ...requestInit } = options;
    const headers = new Headers(requestInit.headers);
    headers.set("Accept", "application/json");

    if (requestInit.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    if (authenticated) {
      const identityId = getIdentityId();
      if (!identityId) {
        throw new ApiError(401, {
          code: "invalid_identity",
          message: "Выберите демопользователя",
        });
      }
      headers.set("X-Demo-Identity", identityId);
    }

    const response = await fetchImplementation(`${normalizedBaseUrl}${path}`, {
      ...requestInit,
      headers,
    });
    const payload = await readJson(response);

    if (!response.ok) {
      throw new ApiError(response.status, toErrorResponse(payload));
    }

    return payload as T;
  }

  return {
    demoIdentities: () =>
      request<DemoIdentity[]>("/api/demo-identities", { authenticated: false }),

    createTask: (fields: Partial<TaskFields>) =>
      request<TaskResponse>("/api/tasks", {
        method: "POST",
        body: JSON.stringify(fields),
      }),

    task: (taskId: string) =>
      request<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}`),

    updateTask: (taskId: string, fields: Partial<TaskFields>) =>
      request<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        body: JSON.stringify(fields),
      }),

    questions: (taskId: string) =>
      request<QuestionResponse>(
        `/api/tasks/${encodeURIComponent(taskId)}/questions`,
        { method: "POST" },
      ),

    composeTask: (taskId: string, answers: Answer[]) =>
      request<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}/compose`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      }),

    confirmTask: (taskId: string) =>
      request<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}/confirm`, {
        method: "POST",
      }),

    publishTask: (taskId: string) =>
      request<TaskResponse>(`/api/tasks/${encodeURIComponent(taskId)}/publish`, {
        method: "POST",
      }),

    catalog: ({ topic, level }: CatalogQuery = {}) => {
      const query = new URLSearchParams();
      if (topic) query.set("topic", topic);
      if (level) query.set("level", level);
      const suffix = query.size > 0 ? `?${query.toString()}` : "";
      return request<CatalogResponse>(`/api/tasks${suffix}`);
    },

    businessTasks: () => request<CatalogResponse>("/api/business/tasks"),

    createProposal: (taskId: string, proposal: ProposalCreate) =>
      request<ProposalResponse>(`/api/tasks/${encodeURIComponent(taskId)}/proposals`, {
        method: "POST",
        body: JSON.stringify(proposal),
      }),

    proposals: (taskId: string) =>
      request<ProposalListResponse>(
        `/api/tasks/${encodeURIComponent(taskId)}/proposals`,
      ),

    decideProposal: (proposalId: string, decision: ProposalDecision) =>
      request<ProposalResponse>(
        `/api/proposals/${encodeURIComponent(proposalId)}/decision`,
        {
          method: "POST",
          body: JSON.stringify({ decision }),
        },
      ),

    teamProposals: () =>
      request<ProposalListResponse>("/api/team/proposals"),

    createMilestone: (proposalId: string, milestone: MilestoneCreate) =>
      request<MilestoneResponse>(
        `/api/proposals/${encodeURIComponent(proposalId)}/milestone`,
        {
          method: "POST",
          body: JSON.stringify(milestone),
        },
      ),

    reviewMilestone: (
      milestoneId: string,
      decision: MilestoneDecision,
      comment: string,
    ) =>
      request<MilestoneResponse>(
        `/api/milestones/${encodeURIComponent(milestoneId)}/review`,
        {
          method: "POST",
          body: JSON.stringify({ decision, comment }),
        },
      ),
  };
}


async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;

  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new ApiError(response.status, {
      code: "invalid_response",
      message: "Backend вернул некорректный JSON",
    });
  }
}

function toErrorResponse(payload: unknown): ErrorResponse {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "code" in payload &&
    "message" in payload &&
    typeof payload.code === "string" &&
    typeof payload.message === "string"
  ) {
    return payload as ErrorResponse;
  }

  return {
    code: "request_failed",
    message: "Не удалось выполнить запрос. Повторите попытку.",
  };
}
