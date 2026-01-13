/**
 * Frontend API client utilities for chat and health endpoints.
 *
 * Uses native fetch for POST requests and EventSource for streaming SSE.
 * Base URL is derived from NEXT_PUBLIC_API_URL with a safe localhost default.
 */
const DEFAULT_API_BASE_URL = "http://localhost:8000";

const getBaseUrl = (): string => {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  const baseUrl =
    raw && raw.trim().length > 0 ? raw.trim() : DEFAULT_API_BASE_URL;

  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
};

const buildUrl = (path: string): string => {
  const baseUrl = getBaseUrl();
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
};

type ServerEventType =
  | "open"
  | "thinking"
  | "message"
  | "tool_call"
  | "tool_used"
  | "tool_result"  // deprecated - raw results no longer sent
  | "complete"
  | "error";

export interface ServerEventPayload {
  type: ServerEventType | string;
  content?: string;
  message?: string;
  tool?: string;
  data?: unknown;
  conversationId?: string;
  conversation_id?: string;
  [key: string]: unknown;
}

export interface ChatEvent {
  type: ServerEventType | string;
  content?: string;
  message?: string;
  tool?: string;
  data?: unknown;
  conversationId?: string;
  conversation_id?: string;
  [key: string]: unknown;
}

export interface SendMessageRequest {
  message: string;
  conversation_id?: string;
}

export interface SendMessageResponse {
  conversationId: string;
  message?: string;
  [key: string]: unknown;
}

export interface HealthResponse {
  status: string;
  environment: string;
  version: string;
  api_version?: string;
  [key: string]: unknown;
}

export interface SessionResponse {
  status: string;
  subject: string;
}

export interface HealthCheckResult {
  /** Whether the server responded with a healthy status */
  healthy: boolean;
  /** Whether the response took longer than the timeout threshold (indicating cold start) */
  isColdStart: boolean;
  /** Actual response latency in milliseconds */
  latencyMs: number;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const parseServerEvent = (value: unknown): ChatEvent | null => {
  if (!isRecord(value) || typeof value.type !== "string") {
    return null;
  }

  const conversationId =
    typeof value.conversationId === "string"
      ? value.conversationId
      : typeof value.conversation_id === "string"
        ? value.conversation_id
        : undefined;

  const content =
    typeof value.content === "string"
      ? value.content
      : typeof value.message === "string"
        ? value.message
        : undefined;

  return {
    ...(value as ServerEventPayload),
    conversationId,
    content,
  };
};

export const connectSSE = (
  conversationId: string | null,
  onMessage: (event: ChatEvent) => void,
  onError: (error: string) => void
): EventSource => {
  const streamUrl = new URL(buildUrl("/api/chat"));
  if (conversationId) {
    streamUrl.searchParams.set("conversation_id", conversationId);
  }

  const eventSource = new EventSource(streamUrl.toString(), {
    withCredentials: true,
  });

  eventSource.addEventListener("open", () => {
    onMessage({
      type: "open",
      conversationId: conversationId ?? undefined,
    });
  });

  eventSource.onmessage = (event: MessageEvent<string>) => {
    try {
      const raw = JSON.parse(event.data) as unknown;
      const parsed = parseServerEvent(raw);
      if (parsed) {
        onMessage(parsed);
        return;
      }
      onError("Received unexpected SSE payload.");
    } catch {
      onError("Failed to parse SSE message.");
    }
  };

  eventSource.onerror = () => {
    onError("SSE connection lost. Attempting to reconnect...");
    // Native EventSource handles reconnection automatically.
  };

  return eventSource;
};

export const sendMessage = async (
  message: string,
  conversationId?: string | null
): Promise<SendMessageResponse> => {
  const trimmedMessage = message.trim();
  if (!trimmedMessage) {
    throw new Error("Message cannot be empty.");
  }

  const payload: SendMessageRequest = {
    message: trimmedMessage,
    conversation_id: conversationId ?? undefined,
  };

  let response: Response;
  try {
    response = await fetch(buildUrl("/api/chat"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Network error while sending message.");
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`API error (${response.status}): ${errorText}`);
  }

  const data = (await response.json()) as unknown;
  if (!isRecord(data)) {
    throw new Error("Unexpected response from chat API.");
  }

  const normalizedConversationId =
    typeof data.conversation_id === "string"
      ? data.conversation_id
      : typeof data.conversationId === "string"
        ? data.conversationId
        : undefined;

  if (!normalizedConversationId) {
    throw new Error("Missing conversation id from chat API.");
  }

  return {
    ...data,
    conversationId: normalizedConversationId,
  } as SendMessageResponse;
};

export const getHealth = async (): Promise<HealthResponse> => {
  let response: Response;
  try {
    response = await fetch(buildUrl("/health"), {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
  } catch {
    throw new Error("Network error while fetching health status.");
  }

  if (!response.ok) {
    const errorText = await response.text().catch(() => "Unknown error");
    throw new Error(`Health check failed (${response.status}): ${errorText}`);
  }

  const data = (await response.json()) as unknown;
  if (!isRecord(data) || typeof data.status !== "string") {
    throw new Error("Unexpected response from health endpoint.");
  }

  return data as HealthResponse;
};

/**
 * Performs a health check with timeout detection for cold start scenarios.
 *
 * @param timeoutMs - Threshold in milliseconds to consider as cold start (default: 3000)
 * @returns HealthCheckResult with healthy status, cold start detection, and latency
 */
export const healthCheckWithTimeout = async (
  timeoutMs: number = 3000
): Promise<HealthCheckResult> => {
  const controller = new AbortController();
  // Allow up to 30 seconds beyond the timeout threshold for the request to complete
  const absoluteTimeoutId = setTimeout(() => controller.abort(), timeoutMs + 30000);
  const startTime = Date.now();

  try {
    const response = await fetch(buildUrl("/health"), {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });
    const latencyMs = Date.now() - startTime;
    clearTimeout(absoluteTimeoutId);

    return {
      healthy: response.ok,
      isColdStart: latencyMs > timeoutMs,
      latencyMs,
    };
  } catch {
    clearTimeout(absoluteTimeoutId);
    const latencyMs = Date.now() - startTime;

    return {
      healthy: false,
      isColdStart: true,
      latencyMs,
    };
  }
};

export const getSession = async (): Promise<SessionResponse> => {
  let response: Response;
  try {
    response = await fetch(buildUrl("/api/me"), {
      method: "GET",
      credentials: "include",
      headers: {
        Accept: "application/json",
      },
    });
  } catch {
    throw new Error("Network error while validating session.");
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => null);
    throw new Error(detail || "Authentication required.");
  }

  const data = (await response.json()) as unknown;
  if (
    !isRecord(data) ||
    typeof data.status !== "string" ||
    typeof data.subject !== "string"
  ) {
    throw new Error("Unexpected response from session endpoint.");
  }

  return { status: data.status, subject: data.subject };
};

export const login = async (password: string): Promise<void> => {
  const trimmed = password.trim();
  if (!trimmed) {
    throw new Error("Password is required.");
  }

  let response: Response;
  try {
    response = await fetch(buildUrl("/api/login"), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ password: trimmed }),
    });
  } catch {
    throw new Error("Unable to sign in. Please try again.");
  }

  if (!response.ok) {
    throw new Error("Invalid password. Please try again.");
  }
};

export const logout = async (): Promise<void> => {
  try {
    const response = await fetch(buildUrl("/api/logout"), {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok && response.status !== 204) {
      throw new Error("Failed to log out.");
    }
  } catch (error) {
    throw new Error(
      error instanceof Error ? error.message : "Failed to log out."
    );
  }
};
