'use client';

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { Bot, ChevronDown, ChevronRight, Loader2, Send, Sparkles, UserRound } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toaster } from "@/components/ui/sonner";
import { WarmingIndicator } from "@/components/ui/warming-indicator";
import { connectSSE, getHealth, getSession, sendMessage, type ChatEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

// App version - increment when deploying to verify App Runner has latest code
const APP_VERSION = "1.0.7";

type ChatRole = "user" | "assistant";

interface UiMessage {
  id: string;
  role: ChatRole;
  content: string;
  thinking?: string;  // Chain-of-thought reasoning from the model
  isStreaming?: boolean;
}

const createMessageId = (prefix: ChatRole): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}`;
};

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [inputValue, setInputValue] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  // Persist conversationId in localStorage so memory survives browser sessions
  const [conversationId, setConversationId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("conversationId");
    }
    return null;
  });
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set());
  const [isWarmingUp, setIsWarmingUp] = useState<boolean>(false);
  const [healthCheckComplete, setHealthCheckComplete] = useState<boolean>(false);

  const messageListRef = useRef<HTMLDivElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track if the last stream completed normally (to suppress "connection lost" errors)
  const streamCompletedRef = useRef<boolean>(false);

  // Configuration for cold start detection
  const WARMUP_TIMEOUT_MS = 3000;  // 3 seconds before showing warming message
  const MAX_WARMUP_TIME_MS = 60000;  // 60 seconds before giving up

  useEffect(() => {
    const verifySession = async () => {
      try {
        await getSession();
        setIsAuthenticated(true);
      } catch {
        router.replace("/login");
      }
    };
    void verifySession();
  }, [router]);

  // Persist conversationId to localStorage so memory survives browser sessions
  useEffect(() => {
    if (conversationId) {
      localStorage.setItem("conversationId", conversationId);
    }
  }, [conversationId]);

  // Health check with cold start detection
  useEffect(() => {
    if (!isAuthenticated || healthCheckComplete) {
      return;
    }

    let isCancelled = false;
    const startTime = Date.now();

    const performHealthCheck = async (): Promise<boolean> => {
      try {
        await getHealth();
        return true;
      } catch {
        return false;
      }
    };

    const timeoutPromise = (ms: number): Promise<"timeout"> =>
      new Promise((resolve) => setTimeout(() => resolve("timeout"), ms));

    const checkHealth = async () => {
      // First, race with a short timeout to detect cold start
      const initialResult = await Promise.race([
        performHealthCheck(),
        timeoutPromise(WARMUP_TIMEOUT_MS),
      ]);

      if (isCancelled) return;

      if (initialResult === true) {
        // Health check succeeded quickly - no cold start
        setHealthCheckComplete(true);
        setIsWarmingUp(false);
        return;
      }

      // Timeout won or health check failed - show warming indicator
      setIsWarmingUp(true);

      // Keep polling until health check succeeds or max time exceeded
      const pollInterval = 2000; // Poll every 2 seconds
      const poll = async () => {
        if (isCancelled) return;

        const elapsed = Date.now() - startTime;
        if (elapsed >= MAX_WARMUP_TIME_MS) {
          setIsWarmingUp(false);
          toast.error("Server is taking too long to respond. Please refresh the page.");
          return;
        }

        const success = await performHealthCheck();
        if (isCancelled) return;

        if (success) {
          setHealthCheckComplete(true);
          setIsWarmingUp(false);
        } else {
          // Schedule next poll
          setTimeout(poll, pollInterval);
        }
      };

      // Start polling
      void poll();
    };

    void checkHealth();

    return () => {
      isCancelled = true;
    };
  }, [isAuthenticated, healthCheckComplete]);

  const appendAssistantChunk = useCallback((chunk: string) => {
    setMessages((prev) => {
      if (prev.length > 0) {
        const last = prev[prev.length - 1];
        if (last.role === "assistant") {
          const updated: UiMessage = {
            ...last,
            content: `${last.content}${chunk}`,
            isStreaming: true,
          };
          return [...prev.slice(0, -1), updated];
        }
      }

      return [
        ...prev,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          content: chunk,
          isStreaming: true,
        },
      ];
    });
  }, []);

  const appendThinkingContent = useCallback((thinking: string) => {
    setMessages((prev) => {
      if (prev.length > 0) {
        const last = prev[prev.length - 1];
        if (last.role === "assistant") {
          const updated: UiMessage = {
            ...last,
            thinking: last.thinking ? `${last.thinking}\n${thinking}` : thinking,
            isStreaming: true,
          };
          return [...prev.slice(0, -1), updated];
        }
      }

      // Create new assistant message with thinking content
      return [
        ...prev,
        {
          id: createMessageId("assistant"),
          role: "assistant",
          content: "",
          thinking: thinking,
          isStreaming: true,
        },
      ];
    });
  }, []);

  const toggleThinking = useCallback((messageId: string) => {
    setExpandedThinking((prev) => {
      const next = new Set(prev);
      if (next.has(messageId)) {
        next.delete(messageId);
      } else {
        next.add(messageId);
      }
      return next;
    });
  }, []);

  const finalizeAssistantMessage = useCallback(() => {
    setMessages((prev) => {
      if (prev.length === 0) {
        return prev;
      }

      const last = prev[prev.length - 1];
      if (last.role !== "assistant" || !last.isStreaming) {
        return prev;
      }

      const updated: UiMessage = { ...last, isStreaming: false };
      return [...prev.slice(0, -1), updated];
    });
    setIsLoading(false);
  }, []);

  const handleChatEvent = useCallback(
    (event: ChatEvent) => {
      if (event.conversationId) {
        setConversationId((current) => current ?? event.conversationId ?? null);
      }

      switch (event.type) {
        case "open":
          setReconnectAttempt(0);
          return;
        case "thinking":
          // Chain-of-thought reasoning from the model
          if (event.content) {
            appendThinkingContent(event.content);
          }
          return;
        case "tool_used":
          // Tool was used - could show a subtle indicator, but don't show raw results
          console.log(`Tool used: ${event.tool}`);
          return;
        case "message":
          if (event.content) {
            appendAssistantChunk(event.content);
          }
          return;
        case "complete":
          // Mark that this stream completed normally (suppress connection error toast)
          streamCompletedRef.current = true;
          finalizeAssistantMessage();
          // Close the EventSource gracefully to prevent error handler from firing
          eventSourceRef.current?.close();
          // Silently trigger reconnection for the next message after a brief delay
          setTimeout(() => {
            setReconnectAttempt((attempt) => attempt + 1);
          }, 500);
          return;
        case "error":
          setIsLoading(false);
          toast.error(
            event.content ?? "Something went wrong. Please try again."
          );
          return;
        default:
          return;
      }
    },
    [appendAssistantChunk, appendThinkingContent, finalizeAssistantMessage]
  );

  const handleSseError = useCallback(
    (errorMessage: string) => {
      // If the stream just completed normally, this is an expected closure - don't show error
      if (streamCompletedRef.current) {
        console.debug("SSE connection closed after stream completion (normal)");
        streamCompletedRef.current = false;
        return;
      }

      console.warn("SSE connection error:", errorMessage);
      eventSourceRef.current?.close();
      setIsLoading(false);
      toast.error(errorMessage);
      setReconnectAttempt((attempt) => attempt + 1);
    },
    []
  );

  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    const backoffMs =
      reconnectAttempt === 0
        ? 0
        : Math.min(16000, 1000 * 2 ** reconnectAttempt);

    reconnectTimeoutRef.current = setTimeout(() => {
      eventSourceRef.current?.close();
      const source = connectSSE(conversationId, handleChatEvent, handleSseError);
      eventSourceRef.current = source;
    }, backoffMs);

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      eventSourceRef.current?.close();
    };
  }, [
    conversationId,
    handleChatEvent,
    handleSseError,
    isAuthenticated,
    reconnectAttempt,
  ]);

  useEffect(() => {
    if (!messageListRef.current) {
      return;
    }
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [messages]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = inputValue.trim();

    if (!trimmed) {
      return;
    }

    const userMessage: UiMessage = {
      id: createMessageId("user"),
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);
    // Reset completion flag for new message
    streamCompletedRef.current = false;

    try {
      const result = await sendMessage(trimmed, conversationId);
      if (result.conversationId) {
        setConversationId((current) => current ?? result.conversationId ?? null);
      }
    } catch (error) {
      setIsLoading(false);
      const detail =
        error instanceof Error
          ? error.message
          : "Unable to send message. Please try again.";
      toast.error(detail);
    }
  };

  // Start a new conversation (clears memory)
  const handleNewConversation = useCallback(() => {
    localStorage.removeItem("conversationId");
    setConversationId(null);
    setMessages([]);
    // Close existing SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const chatHeader = useMemo(
    () => (
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-primary" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-foreground">
              Enterprise Agentic AI
            </p>
            <p className="text-xs text-muted-foreground">
              Streaming responses with tool awareness
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleNewConversation}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            title="Start a new conversation"
          >
            New Chat
          </button>
          <span className="text-xs text-muted-foreground font-mono">
            v{APP_VERSION}
          </span>
          <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            Live
          </div>
        </div>
      </div>
    ),
    [handleNewConversation]
  );

  const renderMessage = (message: UiMessage) => {
    const isUser = message.role === "user";
    const bubbleClasses = cn(
      "rounded-2xl px-4 py-3 text-sm shadow-sm",
      isUser
        ? "bg-gradient-to-r from-primary to-primary/90 text-primary-foreground"
        : "bg-muted text-foreground"
    );

    const iconWrapperClasses = cn(
      "flex h-8 w-8 items-center justify-center rounded-full shadow-sm",
      isUser ? "bg-primary text-primary-foreground" : "bg-slate-200 text-slate-800"
    );

    const hasThinking = !isUser && message.thinking;
    const isThinkingExpanded = expandedThinking.has(message.id);

    return (
      <div
        key={message.id}
        className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
      >
        <div className="flex max-w-[80%] items-start gap-3">
          {!isUser && (
            <div className={iconWrapperClasses} aria-hidden>
              <Bot className="h-4 w-4" />
            </div>
          )}
          <div className={bubbleClasses}>
            {!isUser && (
              <p className="mb-1 text-xs font-semibold text-muted-foreground">
                Assistant
              </p>
            )}

            {/* Thinking section (collapsible) */}
            {hasThinking && (
              <div className="mb-3">
                <button
                  type="button"
                  onClick={() => toggleThinking(message.id)}
                  className="flex items-center gap-1.5 text-xs text-violet-600 hover:text-violet-700 transition-colors"
                >
                  {isThinkingExpanded ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                  <Sparkles className="h-3 w-3" />
                  <span className="font-medium">
                    {isThinkingExpanded ? "Hide reasoning" : "Show reasoning"}
                  </span>
                </button>
                {isThinkingExpanded && (
                  <div className="mt-2 rounded-lg bg-violet-50 border border-violet-100 p-3 text-xs text-violet-800 dark:bg-violet-950/30 dark:border-violet-900 dark:text-violet-200">
                    <p className="whitespace-pre-wrap leading-relaxed">{message.thinking}</p>
                  </div>
                )}
              </div>
            )}

            {/* Main message content */}
            {message.content && (
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            )}

            {/* Show thinking indicator while streaming if we only have thinking content */}
            {message.isStreaming && !message.content && hasThinking && (
              <span className="inline-flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Thinking...
              </span>
            )}

            {/* Streaming indicator */}
            {message.isStreaming && message.content ? (
              <span className="mt-2 inline-flex items-center gap-2 text-[11px] uppercase tracking-wide text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                Streaming
              </span>
            ) : null}
          </div>
          {isUser && (
            <div className={iconWrapperClasses} aria-hidden>
              <UserRound className="h-4 w-4" />
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-8">
      <Card className="flex h-[85vh] w-full max-w-5xl flex-col border-slate-200 shadow-lg dark:border-zinc-800">
        <CardHeader className="border-b border-slate-200 bg-white/70 backdrop-blur dark:border-zinc-800 dark:bg-black/20">
          <CardTitle>{chatHeader}</CardTitle>
        </CardHeader>

        <CardContent className="flex flex-1 flex-col gap-4 overflow-hidden p-0">
          {/* Cold start warming up banner */}
          <WarmingIndicator
            isVisible={isWarmingUp}
            estimatedTime={30}
            showElapsed
          />

          <div
            ref={messageListRef}
            className="flex-1 space-y-4 overflow-y-auto px-6 py-6"
          >
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-slate-200 bg-white/70 p-6 text-center text-sm text-muted-foreground dark:border-zinc-800 dark:bg-black/30">
                <Bot className="h-8 w-8 text-primary" aria-hidden />
                <p className="font-medium text-foreground">
                  Start a conversation
                </p>
                <p className="max-w-md text-sm text-muted-foreground">
                  Ask anything about the agent, its tools, or try a market data
                  query. Responses stream in real time.
                </p>
              </div>
            ) : (
              messages.map(renderMessage)
            )}

            {isLoading && (
              <div className="flex justify-start">
                <div className={cn(
                  "inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm shadow-sm",
                  isWarmingUp
                    ? "bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300"
                    : "bg-muted text-muted-foreground"
                )}>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {isWarmingUp
                    ? "Warming up the server... This may take up to 30 seconds"
                    : "Generating response..."}
                </div>
              </div>
            )}
          </div>
        </CardContent>

        <CardFooter className="border-t border-slate-200 bg-white/80 p-4 backdrop-blur dark:border-zinc-800 dark:bg-black/30">
          <form
            onSubmit={handleSubmit}
            className="flex w-full items-center gap-3"
          >
            <Input
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Ask about the agent's capabilities..."
              className="flex-1"
              aria-label="Message input"
              disabled={!isAuthenticated}
            />
            <Button
              type="submit"
              className={cn(
                "gap-2",
                isWarmingUp && !isLoading && "bg-amber-600 hover:bg-amber-700"
              )}
              disabled={isLoading || !inputValue.trim() || !isAuthenticated}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {isWarmingUp ? "Warming up..." : "Sending"}
                </>
              ) : isWarmingUp ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Send
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Send
                </>
              )}
            </Button>
          </form>
        </CardFooter>
      </Card>

      <Toaster richColors closeButton />
    </div>
  );
}
