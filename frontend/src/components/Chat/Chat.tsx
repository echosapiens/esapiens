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
import { IconSend, IconPaperclip, IconX, IconPlayerStop } from '@tabler/icons-react';
import { MessageBubble } from './MessageBubble';
import { ComputationExperience } from './ComputationExperience';
import { uploadFile, type UploadResponse } from '../../lib/api';
import type { Message } from '../../lib/api';
import { useMobile } from '../../hooks/useMobile';

interface ChatProps {
  messages: Message[];
  onSend: (query: string, fileContext?: string | null) => Promise<void>;
  onStop: () => void;
  isLoading: boolean;
  sessionCount: number;
  onNewChat: () => void;
  sessionId: string;
  activeBackgroundJobs?: any[];
}

/* ─── Microcopy: input placeholder cycles through context-aware hints ─── */
const PLACEHOLDERS = [
  'Analyze gene expression data...',
  'Query protein sequences...',
  'Run pathway enrichment...',
  'Compare experimental conditions...',
  'Ask anything about your data...',
];

export function Chat({ messages, onSend, onStop, isLoading, sessionId, activeBackgroundJobs = [] }: ChatProps) {
  const [input, setInput] = useState('');
  const [attachedFile, setAttachedFile] = useState<UploadResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * PLACEHOLDERS.length));
  const isMobile = useMobile();
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

    setInput('');
    setAttachedFile(null);
    setUploadError(null);
    setUploadProgress(null);

    await onSend(query, fileContext);
  }, [input, attachedFile, isLoading, onSend]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const ordered = messages;
  const lastAssistant = ordered.length > 0
    ? ordered.reduceRight<typeof ordered[number] | undefined>((found, m) => found ?? (m.role === 'assistant' ? m : undefined), undefined)
    : undefined;

  const activeToolCalls = lastAssistant?.tool_calls ?? [];
  const hasRunningTools = activeToolCalls.some((tc) => tc.status === 'running') || activeBackgroundJobs.length > 0;
  const shouldShowOverlay = isLoading && (!lastAssistant?.content || hasRunningTools || activeToolCalls.length === 0);

  const canSend = (input.trim().length > 0 || attachedFile !== null) && !isLoading;

  return (
    <>
      {/* ─── Messages area ─── */}
      <div style={{
        flex: 1,
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        overflow: 'hidden',
        maxWidth: '100%',
      }}>
        <ScrollArea
          style={{ flex: 1 }}
          viewportRef={scrollRef}
          viewportProps={{
            'aria-label': 'Conversation messages',
            'aria-live': 'polite',
            role: 'log',
          }}
          id="chat-content"
        >
          <Stack p={isMobile ? "xs" : "md"} gap="sm">
            {ordered.map((msg) => {
              const hideBubble = shouldShowOverlay && msg.role === 'assistant' && msg.id === lastAssistant?.id;
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

      {/* ─── Processing overlay ─── */}
      {shouldShowOverlay && (
        <ComputationExperience
          isLoading={isLoading}
          toolCalls={activeToolCalls}
        />
      )}

      {/* ─── Loading indicator (first message only) ─── */}
      {isLoading && !lastAssistant && !shouldShowOverlay && (
        <Group gap="xs" style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.75rem',
          color: 'var(--e-text-tertiary)',
          padding: '8px 14px',
          letterSpacing: '0.04em',
        }}>
          <div style={{
            width: 4, height: 4, borderRadius: '50%',
            backgroundColor: 'var(--e-accent-blue)',
            animation: 'pulse-dot 1.2s ease-in-out infinite',
          }} />
          Processing...
        </Group>
      )}

      {/* ─── Input bar ─── */}
      <div style={{
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        padding: isMobile ? '8px 10px' : '10px 12px',
        flexShrink: 0,
      }}>
        {/* ─── Attached file chip ─── */}
        {attachedFile && (
          <div style={{ marginBottom: 8 }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              backgroundColor: 'rgba(37, 99, 235, 0.06)',
              color: 'var(--e-brand)',
              padding: '6px 10px 6px 14px',
              borderRadius: 'var(--e-radius-md)',
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.8125rem',
              fontWeight: 500,
              border: '1px solid rgba(37, 99, 235, 0.15)',
              animation: 'fade-in-up 0.15s ease-out',
            }}>
              <IconPaperclip size={13} stroke={2} />
              <span>{attachedFile.filename}</span>
              <span style={{
                fontFamily: 'var(--e-font-mono)',
                fontSize: '0.6875rem',
                opacity: 0.6,
              }}>
                ({attachedFile.rows} rows)
              </span>
              <ActionIcon
                size="xs"
                variant="transparent"
                color="gray"
                onClick={handleRemoveFile}
                style={{ color: 'var(--e-text-tertiary)', marginLeft: 2 }}
              >
                <IconX size={12} stroke={2} />
              </ActionIcon>
            </div>
          </div>
        )}

        {/* ─── Upload progress ─── */}
        {uploadProgress !== null && (
          <Progress
            value={uploadProgress}
            size="xs"
            color="blue"
            style={{ marginBottom: 8 }}
            styles={{ root: { backgroundColor: 'var(--e-bg-inset)' } }}
          />
        )}

        {/* ─── Upload error ─── */}
        {uploadError && (
          <Text style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.75rem',
            color: 'var(--e-error)',
            marginBottom: 8,
            letterSpacing: '0.02em',
          }}>
            {uploadError}
          </Text>
        )}

        {/* ─── Input row ─── */}
        <Group gap="sm" align="center">
          {/* Attach button */}
          <Tooltip label={attachedFile ? 'File attached' : 'Attach file'} withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size={40}
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading}
              style={{
                transition: 'all var(--e-transition-fast)',
                color: attachedFile ? 'var(--e-brand)' : 'var(--e-text-tertiary)',
              }}
              onMouseEnter={(e) => {
                if (!attachedFile) e.currentTarget.style.color = 'var(--e-brand)';
              }}
              onMouseLeave={(e) => {
                if (!attachedFile) e.currentTarget.style.color = 'var(--e-text-tertiary)';
              }}
            >
              <IconPaperclip size={18} stroke={1.75} />
            </ActionIcon>
          </Tooltip>

          {/* Text input */}
          <input
            type="file"
            accept=".csv,.tsv,.json,.xlsx,.fasta,.fa"
            ref={fileInputRef}
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />

          <TextInput
            flex={1}
            placeholder={PLACEHOLDERS[placeholderIdx]}
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            styles={{
              input: {
                fontFamily: 'var(--e-font-sans)',
                fontSize: '0.9375rem',
                border: '1px solid var(--e-border)',
                borderRadius: 'var(--e-radius-md)',
                padding: '10px 14px',
                minHeight: 44,
                transition: 'border-color var(--e-transition-fast), box-shadow var(--e-transition-fast)',
                '&:focus': {
                  borderColor: 'var(--e-brand)',
                  boxShadow: '0 0 0 3px rgba(37, 99, 235, 0.08)',
                },
              },
            }}
          />

          {/* Send / Stop */}
          {isLoading ? (
            <Button
              color="red"
              size="md"
              onClick={onStop}
              styles={{
                root: {
                  minWidth: 72,
                  height: 44,
                  borderRadius: 'var(--e-radius-md)',
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                },
              }}
            >
              <Group gap={6}>
                <IconPlayerStop size={15} stroke={2} />
                Stop
              </Group>
            </Button>
          ) : (
            <Button
              onClick={handleSend}
              disabled={!canSend}
              size="md"
              styles={{
                root: {
                  minWidth: 72,
                  height: 44,
                  borderRadius: 'var(--e-radius-md)',
                  backgroundColor: canSend ? 'var(--e-brand)' : 'var(--e-bg-subtle)',
                  color: canSend ? '#fff' : 'var(--e-text-muted)',
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: '0.875rem',
                  fontWeight: 500,
                  transition: 'all var(--e-transition-fast)',
                  border: 'none',
                },
              }}
              onMouseEnter={(e) => {
                if (canSend) e.currentTarget.style.backgroundColor = '#1D4ED8';
              }}
              onMouseLeave={(e) => {
                if (canSend) e.currentTarget.style.backgroundColor = 'var(--e-brand)';
              }}
            >
              <Group gap={6}>
                <IconSend size={15} stroke={2} />
                Send
              </Group>
            </Button>
          )}
        </Group>
      </div>
    </>
  );
}