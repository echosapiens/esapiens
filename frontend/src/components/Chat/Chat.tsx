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

export function Chat({ messages, onSend, onStop, isLoading, sessionId, activeBackgroundJobs = [] }: ChatProps) {
  const [input, setInput] = useState('');
  const [attachedFile, setAttachedFile] = useState<UploadResponse | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
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

  // Logic: Show overlay if loading and (no content yet OR still executing tools)
  const shouldShowOverlay = isLoading && (!lastAssistant?.content || hasRunningTools || activeToolCalls.length === 0);

  return (
    <>
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

      {shouldShowOverlay && (
        <ComputationExperience
          isLoading={isLoading}
          toolCalls={activeToolCalls}
        />
      )}

      {isLoading && !lastAssistant && !shouldShowOverlay && (
        <Group gap="xs" style={{ fontFamily: "var(--e-font-mono)", fontSize: '0.875rem', color: 'var(--e-text-secondary)', padding: '8px 14px' }}>
          <div style={{ width: 4, height: 4, borderRadius: '50%', backgroundColor: 'var(--e-accent-cyan)' }} />
          Processing...
        </Group>
      )}

      <div style={{
        backgroundColor: 'var(--e-bg-surface)',
        borderRadius: 'var(--e-radius-2xl)',
        boxShadow: 'var(--e-shadow-md)',
        padding: '8px 12px',
        flexShrink: 0,
      }}>
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
              <ActionIcon size="xs" color="blue" variant="transparent" onClick={handleRemoveFile} style={{ color: '#fff' }}>
                <IconX size={12} />
              </ActionIcon>
            </div>
          </Group>
        )}

        {uploadProgress !== null && (
          <Progress value={uploadProgress} size="xs" color="blue" style={{ marginBottom: 8 }} styles={{ root: { backgroundColor: 'var(--e-bg-inset)' } }} />
        )}

        {uploadError && (
          <Text size="xs" c="red" style={{ marginBottom: 8, fontFamily: 'var(--e-font-mono)' }}>
            {uploadError}
          </Text>
        )}

        <Group gap="sm">
          <input type="file" accept=".csv,.tsv,.json,.xlsx" ref={fileInputRef} onChange={handleFileSelect} style={{ display: 'none' }} />
          <Tooltip label="Attach file" position="top" withArrow>
            <ActionIcon variant="subtle" color="gray" size="lg" onClick={() => fileInputRef.current?.click()} disabled={isLoading} styles={{ root: { color: attachedFile ? 'var(--e-accent-blue)' : 'var(--e-text-secondary)' } }}>
              <IconPaperclip size={20} />
            </ActionIcon>
          </Tooltip>

          <TextInput flex={1} placeholder="Ask a question or paste a gene list..." value={input} onChange={(e) => setInput(e.currentTarget.value)} onKeyDown={handleKeyDown} style={{ fontFamily: "var(--e-font-sans)" }} />
          {isLoading ? (
            <Button color="red" onClick={onStop} style={{ fontFamily: "var(--e-font-sans)" }}>Stop</Button>
          ) : (
            <Button onClick={handleSend} style={{ fontFamily: "var(--e-font-sans)" }}><IconSend size={16} /></Button>
          )}
        </Group>
      </div>
    </>
  );
}
