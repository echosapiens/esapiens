import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Group,
  TextInput,
  Button,
  ScrollArea,
  Stack,
} from '@mantine/core';
import { IconSend } from '@tabler/icons-react';
import { MessageBubble } from './MessageBubble';
import { ComputationExperience } from './ComputationExperience';
import type { Message } from '../../lib/api';

interface ChatProps {
  messages: Message[];
  onSend: (query: string) => Promise<void>;
  onStop: () => void;
  isLoading: boolean;
  sessionCount: number;
  onNewChat: () => void;
  sessionId: string;
}

export function Chat({ messages, onSend, onStop, isLoading }: ChatProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleSend = useCallback(async () => {
    if (input.trim()) {
      await onSend(input.trim());
      setInput('');
    }
  }, [input, onSend]);

  // Scroll to top when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [messages, isLoading]);

  // Newest messages first
  const reversed = [...messages].reverse();

  // Get tool calls from the last assistant message (for ComputationExperience)
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
  const activeToolCalls = lastAssistant?.tool_calls ?? [];
  const hasRunningTools = activeToolCalls.some((tc) => tc.status === 'running');

  // Show ComputationExperience overlay:
  // 1. When loading with no content yet (initial processing phase), OR
  // 2. When loading and there are running tool calls (multi-step computation)
  // This ensures the overlay persists across multi-step tool executions,
  // even when intermediate text chunks have already started streaming in.
  const showComputationOverlay =
    isLoading &&
    !!lastAssistant &&
    (!lastAssistant.content || hasRunningTools);

  return (
    <>
      {/* Input at the top — floating card */}
      <div style={{
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        padding: '8px 12px',
        flexShrink: 0,
      }}>
        <Group gap="sm">
          <TextInput
            flex={1}
            placeholder="Ask a question or paste a gene list..."
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            style={{ fontFamily: "var(--e-font-sans)" }}
          />
          {isLoading ? (
            <Button color="red" onClick={onStop} style={{ fontFamily: "var(--e-font-sans)" }}>
              Stop
            </Button>
          ) : (
            <Button onClick={handleSend} style={{ fontFamily: "var(--e-font-sans)" }}>
              <IconSend size={16} />
            </Button>
          )}
        </Group>
      </div>

      {/* Messages — floating card */}
      <div style={{
        flex: 1,
        minHeight: 0,
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <ScrollArea style={{ flex: 1 }} viewportRef={scrollRef}>
          <Stack p="md" gap="sm">
            {/* ComputationExperience overlay: shown while loading with no content */}
            {showComputationOverlay && (
              <ComputationExperience
                isLoading={isLoading}
                toolCalls={activeToolCalls}
              />
            )}
            {/* Fallback loading indicator for initial loading before assistant message exists */}
            {isLoading && !lastAssistant && (
              <Group gap="xs" style={{ fontFamily: "var(--e-font-mono)", fontSize: '0.875rem', color: 'var(--e-text-secondary)' }}>
                <div style={{ width: 4, height: 4, borderRadius: '50%', backgroundColor: 'var(--e-accent-cyan)' }} />
                Processing...
              </Group>
            )}
            {reversed.map((msg, idx) => {
              // When the overlay is showing for a streaming assistant, hide
              // that message bubble to avoid double content (overlay + bubble).
              // The overlay will be dismissed once all tools finish.
              const hideBubble =
                showComputationOverlay &&
                msg.role === 'assistant' &&
                msg.id === lastAssistant?.id;

              if (hideBubble) return null;

              return (
                <MessageBubble
                  key={messages.length - 1 - idx}
                  message={msg}
                />
              );
            })}
          </Stack>
        </ScrollArea>
      </div>
    </>
  );
}