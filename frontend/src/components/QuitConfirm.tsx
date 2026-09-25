interface QuitConfirmProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export function QuitConfirm({ onConfirm, onCancel }: QuitConfirmProps) {
  return (
    <div className="suit-picker-overlay">
      <div className="suit-picker quit-confirm">
        <p className="quit-confirm-title">⚠️ Forfeit the match?</p>
        <p className="hint">
          You'll lose immediately and hand the win to whoever's left. Your
          hand goes back into the draw pile and the game carries on without
          you. This can't be undone.
        </p>
        <div className="quit-confirm-actions">
          <button type="button" className="keep-playing" onClick={onCancel}>
            Keep playing
          </button>
          <button type="button" className="btn-danger" onClick={onConfirm}>
            Forfeit match
          </button>
        </div>
      </div>
    </div>
  );
}
