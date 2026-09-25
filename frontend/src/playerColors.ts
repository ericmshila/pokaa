// A stable, purely decorative color per player id, so names read as
// visually distinct at a glance across the opponent row, your own
// hand label, and the game log — never the only signal for anything:
// everywhere this color is used, the player's name is also spelled
// out as text right next to it. Deliberately avoids the hues already
// carrying real meaning elsewhere on the table (gold = your turn /
// legal-play hint, rose = Niko Kadi tension, sky blue = up next, red
// = danger/eliminated) so a name color never gets misread as one of
// those state cues.
const PLAYER_NAME_COLORS = [
  "#8ecae6", // soft cornflower
  "#b39ddb", // soft violet
  "#f48fb1", // soft pink
  "#80cbc4", // soft teal
  "#ffab91", // soft coral
  "#c5e1a5", // soft lime
  "#ce93d8", // soft orchid
  "#ffe082", // soft amber
];

/**
 * Deterministically hashes a player id to one of PLAYER_NAME_COLORS —
 * same id always gets the same color, including across reconnects
 * and a restarted round (ids don't change on restart).
 */
export function colorForPlayer(id: string): string {
  let hash = 0;

  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }

  return PLAYER_NAME_COLORS[hash % PLAYER_NAME_COLORS.length];
}
