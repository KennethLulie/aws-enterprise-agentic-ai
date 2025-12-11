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
import { Bot, Loader2, Send, UserRound } from "lucide-react";
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
import { connectSSE, getSession, sendMessage, type ChatEvent } from "@/lib/api";
import { cn } from "@/lib/utils";

type ChatRole = "user" | "assistant";

interface UiMessage {
  id: string;
  role: ChatRole;
  content: string;
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
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);

  const messageListRef = useRef<HTMLDivElement | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        setConversationId((current) => current ?? event.conversationId);
      }

      switch (event.type) {
        case "open":
          setReconnectAttempt(0);
          return;
        case "message":
        case "tool_result":
          if (event.content) {
            appendAssistantChunk(event.content);
          }
          return;
        case "complete":
          finalizeAssistantMessage();
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
    [appendAssistantChunk, finalizeAssistantMessage]
  );

  const handleSseError = useCallback(
    (event: Event) => {
      console.warn("SSE connection error", event);
      eventSourceRef.current?.close();
      setIsLoading(false);
      toast.error("Connection lost. Attempting to reconnect...");
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
        <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Live
        </div>
      </div>
    ),
    []
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
            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            {message.isStreaming ? (
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
                <div className="inline-flex items-center gap-2 rounded-2xl bg-muted px-4 py-3 text-sm text-muted-foreground shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating response...
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
              className="gap-2"
              disabled={isLoading || !inputValue.trim() || !isAuthenticated}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending
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
