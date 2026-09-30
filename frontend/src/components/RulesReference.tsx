import { useMemo, useState } from "react";

interface RuleEntry {
  id: string;
  title: string;
  /** Extra search terms that don't appear verbatim in the title/body. */
  keywords: string;
  body: string;
}

/**
 * The full rules reference, sourced from the actual engine config
 * (backend/app/rules/config.py) and engine behavior rather than any
 * external rulebook — this describes exactly what this app enforces,
 * including a couple of house-rule choices (finishable ranks, the
 * Joker's 5-card pickup, same-color countering) that differ from some
 * other Kadi variants. Keep this in sync if RuleConfig ever changes.
 */
const RULES: RuleEntry[] = [
  {
    id: "setup",
    title: "Setup",
    keywords: "deal hand start begin",
    body: "Each player is dealt 4 cards. The rest form the draw pile, and one card is flipped to start the discard pile — that opening card is never a special one (no Ace, Joker, 2, 3, 8, Jack, Queen, or King), so the first play is always a straightforward match.",
  },
  {
    id: "matching",
    title: "Playing a card",
    keywords: "turn suit rank match legal play group same-rank",
    body: "On your turn, play a card that shares the top card's suit or its rank. You can also play several cards of the same rank together in one move, as long as at least one of them is legal — the rest ride along regardless of suit.",
  },
  {
    id: "twos-threes",
    title: "2s and 3s — pick-up cards",
    keywords: "draw pickup punishment stack two three",
    body: "Playing a 2 forces the next player to draw 2 cards; a 3 forces a draw of 3. These stack: instead of drawing, the next player can play their own 2 or 3 (or a Joker) to pass on an even bigger pickup. Whoever can't or won't counter draws the full stacked total.",
  },
  {
    id: "joker",
    title: "Joker",
    keywords: "wild draw five pickup color counter",
    body: "The Joker is a pickup card worth 5. It can be played any time and forces the next player to draw 5 — unless they counter with another Joker, or a 2 or 3 of the same color (red Joker countered by a red 2/3 or any Joker; black Joker by a black 2/3 or any Joker).",
  },
  {
    id: "ace",
    title: "Ace",
    keywords: "wild declare suit counter cancel",
    body: "The Ace is wild — it can be played on anything, and playing it means you must immediately declare a suit, which becomes the suit everyone has to match next. An Ace can also cancel a pending pickup (2/3/Joker) or a Jack's skip. An Ace can never be played to answer an 8 or Queen, and it can never be your very last, game-winning card.",
  },
  {
    id: "questions",
    title: "8s and Queens — question cards",
    keywords: "answer required suit",
    body: "Playing an 8 or a Queen asks a question. It must be immediately answered by a plain numbered card (2, 3, 4, 5, 6, 7, 9, or 10) in the matching suit — Aces, Jokers, and other 8s/Queens can't serve as the answer. No answer in hand means drawing a card instead.",
  },
  {
    id: "jack",
    title: "Jack — skip",
    keywords: "block skip turn counter",
    body: "Playing a Jack skips the next player's turn entirely. They can counter and bounce the skip onward by playing a Jack of their own, or cancel it outright with an Ace.",
  },
  {
    id: "king",
    title: "King — reverse",
    keywords: "direction order turn",
    body: "Playing a King reverses the direction of play — whoever went before you goes again next.",
  },
  {
    id: "niko-kadi",
    title: "\"Niko Kadi\" — down to your last card",
    keywords: "declare announce one card penalty last",
    body: "The moment you're down to one card, you must declare \"Niko Kadi\" out loud (or with the app's button). Forget to declare it and someone catches it, and you draw 2 penalty cards.",
  },
  {
    id: "winning",
    title: "Winning a round",
    keywords: "finish last card power",
    body: "Any legal card wins the round the moment it empties your hand — including a 2, 3, 8, Jack, Queen, King, Ace, or Joker. Answer a question with your very last card, or drop your last Joker on someone, and if that empties your hand, you've won: the round ends right there, before the card's own effect has a chance to land on anyone else.",
  },
  {
    id: "forfeit",
    title: "Forfeiting",
    keywords: "eliminated thirteen cards too many draw pile",
    body: "If enough stacked pickups force your hand past 13 cards, you're eliminated from the round — your hand is shuffled back into the draw pile and play continues without you.",
  },
];

function matches(entry: RuleEntry, query: string): boolean {
  const haystack = `${entry.title} ${entry.keywords} ${entry.body}`.toLowerCase();
  return haystack.includes(query);
}

export function RulesReference() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) {
      return RULES;
    }
    return RULES.filter((entry) => matches(entry, trimmed));
  }, [query]);

  return (
    <div className="rules-reference">
      <button
        type="button"
        className="btn-secondary rules-toggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        {open ? "Hide rules" : "How to play"}
      </button>

      {open && (
        <div className="rules-panel">
          <input
            type="search"
            className="rules-search"
            placeholder="Search rules… e.g. joker, ace, skip"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Search rules"
          />

          <div className="rules-list">
            {visible.length === 0 ? (
              <p className="hint">No rules match "{query}".</p>
            ) : (
              visible.map((entry) => (
                <div key={entry.id} className="rule-entry">
                  <h3>{entry.title}</h3>
                  <p>{entry.body}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
