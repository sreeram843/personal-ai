import type { ContentBlock } from '../../types/liveData';
import { buildMessageParts } from '../../utils/messageParts';
import { MessageParts } from './MessageParts';

interface Props {
  content: string;
  blocks?: ContentBlock[];
  showStreamingCaret?: boolean;
  /** @deprecated Live loading uses italic status outside the bubble. */
  showLiveSkeleton?: boolean;
}

/** Dispatch assistant content as ordered text + card parts. */
export function AssistantMessageParts({ content, blocks, showStreamingCaret }: Props) {
  const parts = buildMessageParts(content, blocks);
  return <MessageParts parts={parts} showStreamingCaret={showStreamingCaret} />;
}

/** @deprecated Use AssistantMessageParts — kept for callers that only have blocks[]. */
export function LiveDataCards({ blocks }: { blocks: ContentBlock[] }) {
  return <AssistantMessageParts content="" blocks={blocks} />;
}
