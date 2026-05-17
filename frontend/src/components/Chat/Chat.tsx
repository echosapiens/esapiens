import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Group,
  TextInput,
  Button,
  ScrollArea,
  Stack,
  ActionIcon,
  Tooltip,
  Progress,
  Text,
} from '@mantine/core';
import { IconSend, IconPaperclip, IconX } from '@tabler/icons-react';
import { MessageBubble } from './MessageBubble';
import { ComputationExperience } from './ComputationExperience';
import { uploadFile, type UploadResponse } from '../../lib/api';
import type { Message } from '../../lib/api';

interface ChatProps {
  messages: Message[];
  onSend: (query: string, fileContext?: string | null) => Promise<void>;
  onStop: () => void;
  isLoading: boolean;
  sessionCount: number;
  onNewChat: () => void;
  sessionId: string;
}

export function Chat({ messages, onSend, onStop, isLoading, sessionId }: ChatProps) {
  const [input, setInput] = useState('');
  const [attachedFile, setAttachedFile] = useState<UploadResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setUploadProgress(0);

    try {
      const result = await uploadFile(file, sessionId, (progress) => {
        setUploadProgress(progress);
      });
      setAttachedFile(result);
      setUploadProgress(null);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
      setUploadProgress(null);
    }

    // Reset input so the same file can be re-selected
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [sessionId]);

  const handleRemoveFile = useCallback(() => {
    setAttachedFile(null);
    setUploadError(null);
    setUploadProgress(null);
  }, []);

  const handleSend = useCallback(async () => {
    if ((!input.trim() && !attachedFile) || isLoading) return;

    const query = input.trim() || (attachedFile ? 'Analyze this data' : '');
    const fileContext = attachedFile?.summary ?? null;

    await onSend(query, fileContext);

    setInput('');
    setAttachedFile(null);
    setUploadError(null);
    setUploadProgress(null);
  }, [input, attachedFile, isLoading, onSend]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Oldest messages first (chronological order)
  const ordered = messages;

  // Get tool calls from the last assistant message (for ComputationExperience)
  const lastAssistant = ordered.length > 0
    ? ordered.reduceRight<typeof ordered[number] | undefined>((found, m) => found ?? (m.role === 'assistant' ? m : undefined), undefined)
    : undefined;
  const activeToolCalls = lastAssistant?.tool_calls ?? [];
  const hasRunningTools = activeToolCalls.some((tc) => tc.status === 'running');

  // Show ComputationExperience overlay:
  // 1. When loading with no content yet (initial processing phase), OR
  // 2. When loading and there are running tool calls (multi-step computation)
  const showComputationOverlay =
    isLoading &&
    !!lastAssistant &&
    (!lastAssistant.content || hasRunningTools);

  return (
    <>
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
            {ordered.map((msg, idx) => {
              // When the overlay is showing for a streaming assistant, hide
              // that message bubble to avoid double content (overlay + bubble).
              const hideBubble =
                showComputationOverlay &&
                msg.role === 'assistant' &&
                msg.id === lastAssistant?.id;

              if (hideBubble) return null;

              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                />
              );
            })}
          </Stack>
        </ScrollArea>
      </div>

      {/* Computation distraction: sits right above the input */}
      {showComputationOverlay && (
        <ComputationExperience
          isLoading={isLoading}
          toolCalls={activeToolCalls}
        />
      )}
      {isLoading && !lastAssistant && (
        <Group gap="xs" style={{ fontFamily: "var(--e-font-mono)", fontSize: '0.875rem', color: 'var(--e-text-secondary)', padding: '8px 14px' }}>
          <div style={{ width: 4, height: 4, borderRadius: '50%', backgroundColor: 'var(--e-accent-cyan)' }} />
          Processing...
        </Group>
      )}

      {/* Input at the bottom — floating card */}
      <div style={{
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        padding: '8px 12px',
        flexShrink: 0,
      }}>
        {/* File attachment chip */}
        {attachedFile && (
          <Group gap="xs" style={{ marginBottom: 8 }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              backgroundColor: 'var(--e-accent-blue)',
              color: '#fff',
              padding: '4px 8px 4px 12px',
              borderRadius: 'var(--e-radius-lg)',
              fontSize: '0.75rem',
              fontWeight: 500,
              fontFamily: 'var(--e-font-sans)',
            }}>
              {attachedFile.filename} ({attachedFile.rows} rows)
              <ActionIcon
                size="xs"
                color="blue"
                variant="transparent"
                onClick={handleRemoveFile}
                style={{ color: '#fff' }}
              >
                <IconX size={12} />
              </ActionIcon>
            </div>
          </Group>
        )}

        {/* Upload progress bar */}
        {uploadProgress !== null && (
          <Progress
            value={uploadProgress}
            size="xs"
            color="blue"
            style={{ marginBottom: 8 }}
            styles={{
              root: { backgroundColor: 'var(--e-bg-inset)' },
            }}
          />
        )}

        {/* Upload error message */}
        {uploadError && (
          <Text
            size="xs"
            c="red"
            style={{ marginBottom: 8, fontFamily: 'var(--e-font-mono)' }}
          >
            {uploadError}
          </Text>
        )}

        <Group gap="sm">
          {/* Hidden file input */}
          <input
            type="file"
            accept=".csv,.tsv,.json,.xlsx"
            ref={fileInputRef}
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          {/* Paperclip attachment button */}
          <Tooltip label="Attach file" position="top" withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="lg"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              styles={{
                root: {
                  color: attachedFile ? 'var(--e-accent-blue)' : 'var(--e-text-secondary)',
                },
              }}
            >
              <IconPaperclip size={20} />
            </ActionIcon>
          </Tooltip>

          <TextInput
            flex={1}
            placeholder="Ask a question or paste a gene list..."
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
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
    </>
  );
}