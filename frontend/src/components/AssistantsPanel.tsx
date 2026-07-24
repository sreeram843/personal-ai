import { clsx } from 'clsx';
import { Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { createAssistant, deleteAssistant, fetchAssistants, updateAssistant } from '../api';
import type { AssistantSummary } from '../types';
import { ConfirmDialog } from './ConfirmDialog';

interface Props {
  open: boolean;
}

export function AssistantsPanel({ open }: Props) {
  const [assistants, setAssistants] = useState<AssistantSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [instructions, setInstructions] = useState('');
  const [allowedTools, setAllowedTools] = useState('');
  const [deleteTarget, setDeleteTarget] = useState<AssistantSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      setAssistants(await fetchAssistants());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load assistants');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      void refresh();
    }
  }, [open]);

  const handleCreate = async () => {
    if (!name.trim()) {
      return;
    }
    setError(null);
    try {
      await createAssistant({
        name: name.trim(),
        description: description.trim(),
        instructions: instructions.trim(),
        allowed_tools: allowedTools
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        pick_only: true,
      });
      setName('');
      setDescription('');
      setInstructions('');
      setAllowedTools('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create assistant');
    }
  };

  const handleToggle = async (assistant: AssistantSummary) => {
    if (assistant.is_default) {
      return;
    }
    try {
      await updateAssistant(assistant.id, { enabled: !assistant.enabled });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update assistant');
    }
  };

  const handleDelete = async (assistant: AssistantSummary) => {
    if (assistant.is_default || assistant.bundled) {
      return;
    }
    setDeleting(true);
    setError(null);
    try {
      await deleteAssistant(assistant.id);
      setDeleteTarget(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete assistant');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className="space-y-3">
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete assistant"
        message={
          <>
            Delete &ldquo;{deleteTarget?.name}&rdquo;? This cannot be undone.
          </>
        }
        confirmLabel="Delete"
        tone="danger"
        loading={deleting}
        onConfirm={() => {
          if (deleteTarget) {
            void handleDelete(deleteTarget);
          }
        }}
        onCancel={() => {
          if (!deleting) {
            setDeleteTarget(null);
          }
        }}
      />
      <p className="text-xs text-[var(--phosphor-dim)]">
        Assistants add instructions and optional tool limits for new conversations. Bundled assistants can be toggled;
        custom ones are pick-only.
      </p>
      {loading ? <div className="text-xs text-[var(--phosphor-dim)]">Loading assistants…</div> : null}
      {error ? <div className="text-xs text-[#f87171]">{error}</div> : null}
      <div className="space-y-2">
        {assistants.map((assistant) => (
          <div
            key={assistant.id}
            className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] px-3 py-2.5"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-[var(--phosphor-bright)]">{assistant.name}</div>
                {assistant.description ? (
                  <div className="mt-0.5 text-xs text-[var(--phosphor-dim)]">{assistant.description}</div>
                ) : null}
                {assistant.allowed_tools.length ? (
                  <div className="mt-1 text-[11px] text-[var(--phosphor-dim)]">
                    Tools: {assistant.allowed_tools.join(', ')}
                  </div>
                ) : null}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {!assistant.is_default ? (
                  <button
                    type="button"
                    onClick={() => void handleToggle(assistant)}
                    className={clsx(
                      'rounded-full px-2 py-0.5 text-[11px] font-medium',
                      assistant.enabled
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : 'bg-[var(--ui-bg)] text-[var(--phosphor-dim)]',
                    )}
                  >
                    {assistant.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                ) : null}
                {!assistant.is_default && !assistant.bundled ? (
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(assistant)}
                    className="rounded-md border border-[var(--ui-border)] p-1 text-[var(--phosphor-dim)] hover:text-[#f87171]"
                    aria-label={`Delete ${assistant.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-[var(--ui-border)] bg-[var(--ui-bg-elevated)] p-3">
        <div className="type-eyebrow mb-2 !tracking-[0.18em]">
          New assistant
        </div>
        <div className="space-y-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
          />
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Short description"
            className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
          />
          <textarea
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            placeholder="Instructions added to the system prompt"
            rows={3}
            className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
          />
          <input
            value={allowedTools}
            onChange={(event) => setAllowedTools(event.target.value)}
            placeholder="Allowed tools (comma-separated, optional)"
            className="w-full rounded-lg border border-[var(--ui-border)] bg-[var(--ui-bg)] px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={() => void handleCreate()}
            className="inline-flex items-center gap-2 rounded-lg border border-[var(--ui-border)] px-3 py-2 text-sm font-medium text-[var(--phosphor-bright)] hover:bg-[var(--ui-panel-strong)]"
          >
            <Plus className="h-4 w-4" />
            Create assistant
          </button>
        </div>
      </div>
    </section>
  );
}
