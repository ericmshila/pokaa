import { useEffect, useRef, useState } from "react";
import type { ChatMessageView } from "../types";

const MAX_MESSAGE_LENGTH = 500;

interface ChatPanelProps {
  open: boolean;
  onClose: () => void;
  messages: ChatMessageView[];
  playerId: string;
  onSend: (text: string) => void;
}

export function ChatPanel({
  open,
  onClose,
  messages,
  playerId,
  onSend,
}: ChatPanelProps) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  // Keep the newest message in view — both when the panel first opens
  // and whenever a message arrives while it's already open.
  useEffect(() => {
    if (!open) {
      return;
    }

    const list = listRef.current;
    if (list) {
      list.scrollTop = list.scrollHeight;
    }
  }, [open, messages.length]);

  if (!open) {
    return null;
  }

  const submit = () => {
    const text = draft.trim();
    if (!text) {
      return;
    }

    onSend(text.slice(0, MAX_MESSAGE_LENGTH));
    setDraft("");
  };

  return (
    <div className="chat-panel">
      <div className="chat-panel-header">
        <p>Room chat</p>
        <button
          type="button"
          className="chat-panel-close"
          onClick={onClose}
          aria-label="Close chat"
        >
          ✕
        </button>
      </div>

      <div className="chat-panel-messages" ref={listRef}>
        {messages.length === 0 ? (
          <p className="hint">No messages yet — say hello.</p>
        ) : (
          messages.map((message) => (
            <p
              key={message.id}
              className={
                message.playerId === playerId
                  ? "chat-message own"
                  : "chat-message"
              }
            >
              <span className="chat-message-name">{message.name}: </span>
              {message.text}
            </p>
          ))
        )}
      </div>

      <div className="chat-panel-input">
        <input
          value={draft}
          maxLength={MAX_MESSAGE_LENGTH}
          placeholder="Type a message…"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              submit();
            }
          }}
        />
        <button type="button" onClick={submit} disabled={!draft.trim()}>
          Send
        </button>
      </div>
    </div>
  );
}
