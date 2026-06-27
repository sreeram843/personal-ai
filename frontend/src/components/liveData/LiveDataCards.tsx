import type { ContentBlock } from '../../types/liveData';
import { buildMessageParts } from '../../utils/messageParts';
import { MessageParts } from './MessageParts';
import { SkeletonLiveCard } from './SkeletonLiveCard';

interface Props {
  content: string;
  blocks?: ContentBlock[];
  showStreamingCaret?: boolean;
  showLiveSkeleton?: boolean;
}

/** Dispatch assistant content as ordered text + card parts. */
export function AssistantMessageParts({ content, blocks, showStreamingCaret, showLiveSkeleton }: Props) {
  const parts = buildMessageParts(content, blocks);
  return (
    <>
      {showLiveSkeleton ? (
        <div className="mb-2.5">
          <SkeletonLiveCard />
        </div>
      ) : null}
      <MessageParts parts={parts} showStreamingCaret={showStreamingCaret} />
    </>
  );
}

/** @deprecated Use AssistantMessageParts — kept for callers that only have blocks[]. */
export function LiveDataCards({ blocks }: { blocks: ContentBlock[] }) {
  return <AssistantMessageParts content="" blocks={blocks} />;
}
