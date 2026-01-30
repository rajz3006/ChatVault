import type { Conversation, Stats } from "../types";

interface Props {
  conversations: Conversation[];
  selectedUuid: string | null;
  onSelect: (uuid: string) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  starredOnly: boolean;
  onStarredToggle: () => void;
  stats: Stats;
  width: number;
}

export default function LeftPanel({
  conversations,
  selectedUuid,
  onSelect,
  searchQuery,
  onSearchChange,
  starredOnly,
  onStarredToggle,
  stats,
  width,
}: Props) {
  // Group by recency_label preserving order
  const groups: { label: string; items: Conversation[] }[] = [];
  for (const conv of conversations) {
    const label = conv.recency_label || "OLDER";
    const existing = groups.find((g) => g.label === label);
    if (existing) {
      existing.items.push(conv);
    } else {
      groups.push({ label, items: [conv] });
    }
  }

  return (
    <div className="left-panel" style={{ width }}>
      <div className="left-brand">
        <div className="brand-icon" />
        <span className="brand-text">ChatVault</span>
      </div>

      <div className="search-row">
        <input
          type="text"
          className="search-input"
          placeholder="Search..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <button
          className={`star-filter-btn${starredOnly ? " active" : ""}`}
          onClick={onStarredToggle}
          title="Show starred only"
        >
          {starredOnly ? "\u2605" : "\u2606"}
        </button>
      </div>

      <div className="conv-list">
        {groups.map((group) => (
          <div key={group.label}>
            <div className="date-group-header">{group.label}</div>
            {group.items.map((conv, idx) => (
              <div
                key={conv.uuid}
                className={`conv-item${conv.uuid === selectedUuid ? " selected" : ""}`}
                style={{ animationDelay: `${idx * 30}ms` }}
                onClick={() => onSelect(conv.uuid)}
              >
                {!!conv.starred && <span className="conv-star">{"\u2605"}</span>}
                <span className="conv-name">{conv.name || "Untitled"}</span>
              </div>
            ))}
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="conv-empty">No conversations found</div>
        )}
      </div>

      <div className="stats-footer">
        {stats.conversations} convs &middot; {stats.messages} msgs &middot; {stats.vectors} vecs
      </div>
    </div>
  );
}
