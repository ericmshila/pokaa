import type { Suit } from "../types";

const SUITS: Array<{ value: Suit; label: string; symbol: string }> = [
  { value: "spades", label: "Spades", symbol: "♠" },
  { value: "hearts", label: "Hearts", symbol: "♥" },
  { value: "diamonds", label: "Diamonds", symbol: "♦" },
  { value: "clubs", label: "Clubs", symbol: "♣" },
];

interface SuitPickerProps {
  onPick: (suit: Suit) => void;
  onCancel: () => void;
}

export function SuitPicker({ onPick, onCancel }: SuitPickerProps) {
  return (
    <div className="suit-picker-overlay">
      <div className="suit-picker">
        <p>Declare a suit</p>
        <div className="suit-picker-options">
          {SUITS.map((suit) => (
            <button
              key={suit.value}
              type="button"
              className={
                suit.value === "hearts" || suit.value === "diamonds"
                  ? "red"
                  : "black"
              }
              onClick={() => onPick(suit.value)}
            >
              <span className="symbol">{suit.symbol}</span>
              {suit.label}
            </button>
          ))}
        </div>
        <button type="button" className="cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
