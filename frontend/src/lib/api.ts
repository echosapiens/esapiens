/** @format */
import type { WritableDraft } from 'immer';

/* ─── Types ─── */

export type MessageRole = 'user' | 'assistant' | 'system';

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: string | null;
  status?: 'running' | 'success' | 'error';
}

/* ─── Visualization Data Types ─── */

export interface ImageVisualizationData {
  type: 'image';
  image: string;
  format?: string;
  title?: string;
}

export interface PlotlyVisualizationData {
  type: 'plotly';
  html: string;
  title?: string;
}

export interface StructureVisualizationData {
  type: 'structure';
  pdb_id?: string;
  pdb_file?: string;
  contacts?: StructureContact[];
  representation?: 'cartoon' | 'ball+stick' | 'surface' | 'licorice' | 'backbone' | 'spacefill';
  title?: string;
}

export interface StructureContact {
  resi1: number;
  resi2: number;
  dist: number;
}

export type VisualizationData =
  | ImageVisualizationData
  | PlotlyVisualizationData
  | StructureVisualizationData;

/* ─── Message Types ─── */

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  skills?: string[];
  tool_calls?: ToolCall[];
  isStreaming?: boolean;
  visualization?: VisualizationData | null;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  skills?: string[];
  tool_calls?: ToolCall[];
}

export interface StreamCallbacks {
  onSkillsLoaded?: (skills: string[]) => void;
  onToolCall?: (toolCall: ToolCall) => void;
  onToolResult?: (toolCallId: string, result: string, status: 'success' | 'error') => void;
  onChunk?: (chunk: string) => void;
  onVisualization?: (visData: VisualizationData) => void;
  onDone?: (sessionId: string) => void;
  onError?: (error: string) => void;
}

/* ─── Helpers ─── */

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/* ─── API Client ─── */

const CHAT_BASE = '';

async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${CHAT_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(
      `API request failed: ${response.status} ${response.statusText}${body ? ` — ${body.slice(0, 200)}` : ''}`,
    );
  }

  return response.json() as Promise<T>;
}

export async function sendChat(
  query: string,
  sessionId?: string | null,
  abortSignal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(`${CHAT_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      session_id: sessionId || 'default',
    }),
    signal: abortSignal,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Chat request failed: ${response.status}${body ? ` — ${body.slice(0, 200)}` : ''}`);
  }

  return response.json() as Promise<ChatResponse>;
}

/**
 * Stream chat via SSE (Server-Sent Events).
 *
 * Backend (sse-starlette) sends lines like:
 *   event: skills_loaded
 *   data: {"skills": ["path1","path2"]}
 *
 * We track the current event type and call the appropriate callback.
 */
export async function streamChat(
  query: string,
  sessionId: string | null,
  callbacks: StreamCallbacks,
  abortSignal?: AbortSignal,
): Promise<string> {
  const response = await fetch(`${CHAT_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      session_id: sessionId || 'default',
    }),
    signal: abortSignal,
  });

  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Stream chat failed: ${response.status}${body ? ` — ${body.slice(0, 200)}` : ''}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('Stream response body is not readable');
  }

  const decoder = new TextDecoder();
  let buffer = '';
  let lastEventType = '';
  let finalSessionId = sessionId || '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Normalize CRLF → LF (sse-starlette sends \r\n\r\n)
      buffer = buffer.replace(/\r\n/g, '\n');

      // Split on double newline (SSE message boundary)
      const messages = buffer.split('\n\n');
      // Keep the last incomplete message in the buffer
      buffer = messages.pop() || '';

      for (const msg of messages) {
        const lines = msg.split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event: ')) {
            lastEventType = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6);
            if (dataStr === '[DONE]') {
              callbacks.onDone?.(finalSessionId);
              continue;
            }
            try {
              const data = JSON.parse(dataStr);
              handleSSEEvent(lastEventType, data, callbacks, (sid) => {
                finalSessionId = sid;
              });
            } catch {
              // Skip unparseable data lines
            }
          }
        }
      }
    }

    // Process remaining buffer (full SSE messages)
    if (buffer.trim()) {
      const remaining = buffer.replace(/\r\n/g, '\n');
      const messages = remaining.split('\n\n');
      for (const msg of messages) {
        const trimmed = msg.trim();
        if (!trimmed) continue;
        const lines = trimmed.split('\n');
        let localEventType = '';
        for (const line of lines) {
          const l = line.trim();
          if (l.startsWith('event: ')) {
            localEventType = l.slice(7).trim();
          } else if (l.startsWith('data: ')) {
            const dataStr = l.slice(6);
            if (dataStr !== '[DONE]') {
              try {
                const data = JSON.parse(dataStr);
                handleSSEEvent(localEventType, data, callbacks, (sid) => {
                  finalSessionId = sid;
                });
              } catch {
                // skip
              }
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  return finalSessionId;
}

function handleSSEEvent(
  eventType: string,
  data: Record<string, unknown>,
  callbacks: StreamCallbacks,
  setSessionId: (id: string) => void,
): void {
  switch (eventType) {
    case 'skills_loaded': {
      const skills = data.skills as string[] | undefined;
      if (skills && callbacks.onSkillsLoaded) {
        callbacks.onSkillsLoaded(skills);
      }
      break;
    }
    case 'tool_call': {
      if (callbacks.onToolCall) {
        callbacks.onToolCall({
          id: (data.id as string) || generateId(),
          name: (data.name as string) || 'unknown',
          args: (data.args as Record<string, unknown>) || {},
          status: 'running',
        });
      }
      break;
    }
    case 'tool_result': {
      if (callbacks.onToolResult) {
        callbacks.onToolResult(
          data.id as string,
          (data.result as string) || '',
          (data.status as 'success' | 'error') || 'success',
        );
      }
      break;
    }
    case 'chunk': {
      if (callbacks.onChunk) {
        callbacks.onChunk((data.content as string) || '');
      }
      break;
    }
    case 'visualization': {
      if (callbacks.onVisualization) {
        callbacks.onVisualization(data as unknown as VisualizationData);
      }
      break;
    }
    case 'done': {
      const sid = (data.session_id as string) || '';
      if (sid) setSessionId(sid);
      callbacks.onDone?.(sid);
      break;
    }
    case 'error': {
      callbacks.onError?.((data.message as string) || (data.error as string) || 'Unknown error');
      break;
    }
  }
}

/* ─── Session management ─── */

export interface RawSession {
  id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
  messages?: RawMessage[];
}

interface RawMessage {
  id?: string;
  role: MessageRole;
  content: string;
  timestamp?: number;
  skills?: string[];
  tool_calls?: ToolCall[];
  visualization?: VisualizationData | null;
}

function normalizeSession(raw: RawSession): Session {
  return {
    id: raw.id || '',
    title: raw.title || `Chat ${raw.created_at ? new Date(raw.created_at).toLocaleDateString() : ''}`,
    created_at: raw.created_at || new Date().toISOString(),
    updated_at: raw.updated_at || raw.created_at || new Date().toISOString(),
    message_count: raw.message_count || 0,
  };
}

function normalizeMessages(raw: RawMessage[]): Message[] {
  return raw.map((m) => ({
    id: m.id || generateId(),
    role: m.role,
    content: m.content,
    timestamp: m.timestamp || Date.now(),
    skills: m.skills,
    tool_calls: m.tool_calls,
    visualization: m.visualization ?? null,
  }));
}

export async function listSessions(): Promise<Session[]> {
  const raw = await apiFetch<RawSession[]>('/sessions');
  return raw.map(normalizeSession);
}

export async function getSession(sessionId: string): Promise<{ session: Session; messages: Message[] }> {
  const raw = await apiFetch<RawSession>(`/sessions/${sessionId}`);
  return {
    session: normalizeSession(raw),
    messages: normalizeMessages(raw.messages || []),
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch<void>(`/sessions/${sessionId}`, { method: 'DELETE' });
}

/* ─── Immer helpers for message state ─── */

export function addUserMessage(draft: WritableDraft<Message[]>, content: string): void {
  draft.push({
    id: generateId(),
    role: 'user',
    content,
    timestamp: Date.now(),
  });
}

export function addAssistantMessage(draft: WritableDraft<Message[]>): void {
  draft.push({
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    tool_calls: [],
    isStreaming: true,
  });
}

export function setAssistantSkills(draft: WritableDraft<Message[]>, skills: string[]): void {
  for (let i = draft.length - 1; i >= 0; i--) {
    if (draft[i].role === 'assistant') {
      draft[i].skills = skills;
      break;
    }
  }
}

export function addToolCallToAssistant(draft: WritableDraft<Message[]>, toolCall: ToolCall): void {
  for (let i = draft.length - 1; i >= 0; i--) {
    if (draft[i].role === 'assistant') {
      if (!draft[i].tool_calls) {
        draft[i].tool_calls = [];
      }
      draft[i].tool_calls!.push({
        id: toolCall.id,
        name: toolCall.name,
        args: toolCall.args,
        status: 'running',
      });
      break;
    }
  }
}

export function updateToolCallResult(
  draft: WritableDraft<Message[]>,
  toolCallId: string,
  result: string,
  status: 'success' | 'error',
): void {
  for (const msg of draft) {
    if (msg.role === 'assistant' && msg.tool_calls) {
      const tc = msg.tool_calls.find((t) => t.id === toolCallId);
      if (tc) {
        tc.result = result;
        tc.status = status;
        break;
      }
    }
  }
}

export function updateLastAssistantContent(
  draft: WritableDraft<Message[]>,
  chunk: string,
): void {
  for (let i = draft.length - 1; i >= 0; i--) {
    if (draft[i].role === 'assistant') {
      draft[i].content += chunk;
      break;
    }
  }
}

export function finalizeAssistant(draft: WritableDraft<Message[]>): void {
  for (let i = draft.length - 1; i >= 0; i--) {
    if (draft[i].role === 'assistant') {
      draft[i].isStreaming = false;
      break;
    }
  }
}
