import React, { useEffect, useRef, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  MapPin,
  Plus,
  X,
  Check,
  Shield,
  Flame,
  Banknote,
  Eye,
  Zap,
  Clock,
  HeartHandshake,
  ArrowDownToLine,
  Users,
  Church,
  GraduationCap,
  Store,
  Trees,
  Heart,
  Info,
  Lightbulb,
  ArrowRight,
  LogIn,
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

/**
 * Open Navigator — Feed personalization setup (wired)
 * ------------------------------------------------------------------
 * Configure:
 *   1. One or more LOCATIONS, each at the precision the user is
 *      comfortable disclosing (street / district / city / county / state).
 *   2. LENSES — topical value frames the user cares about.
 *   3. SIGNALS — story-lens / interestingness flags to surface.
 *
 * Persistence (api/routes/feed.py):
 *   GET  /api/feed/config           -> load saved config (auth)
 *   PUT  /api/feed/config           -> full replace + mark profile complete (auth)
 *   GET  /api/feed/places?q=        -> real geocoder typeahead (no auth)
 *
 * First-time login: saving while logged out stashes the config to
 * localStorage(feed_config_draft) and opens the OAuth login modal; on return
 * the draft is auto-saved. Place suggestions come from the real geocoder —
 * no fabricated data (CLAUDE.md).
 */

const FONT_SERIF = "'Playfair Display', Georgia, serif";
const FONT_BODY = "'Source Sans 3', system-ui, sans-serif";
const FONT_MONO = "'IBM Plex Mono', ui-monospace, monospace";

const TEAL = "#0f766e";
const TEAL_TINT = "#ecfdf9";
const INK = "#1c1917";
const INK_2 = "#57534e";
const INK_3 = "#78716c";
const SURFACE = "#fafaf9";
const CARD = "#ffffff";
const BORDER = "#e7e5e4";

const DRAFT_KEY = "feed_config_draft";

const SHARED_LEVELS = [
  { key: "street", label: "Street", hint: "Most precise" },
  { key: "district", label: "District" },
  { key: "city", label: "City" },
  { key: "county", label: "County" },
  { key: "state", label: "State", hint: "Broadest" },
];

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface CatalogItem {
  slug: string;
  label: string;
  icon: LucideIcon;
  what: string;
  eg: string;
  see: string;
  accent?: string;
}

interface LocationRow {
  id: number;
  name: string;
  shared_level: string;
  is_primary: boolean;
  state_code?: string | null;
  state?: string | null;
  county?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  jurisdiction_id?: string | null;
}

interface PlaceHit {
  name: string;
  city?: string | null;
  county?: string | null;
  state?: string | null;
  state_code?: string | null;
  latitude: number;
  longitude: number;
}

interface FeedConfig {
  locations: LocationRow[];
  lenses: string[];
  signals: string[];
  profile_completed: boolean;
}

interface DetailState {
  item: CatalogItem;
  accent: string;
}

// Topical value frames — what a decision is ABOUT.
const LENSES: CatalogItem[] = [
  {
    slug: "family-first",
    label: "Family First",
    icon: Users,
    what: "Decisions that touch kids, parents, and household life.",
    eg: "A vote to extend rec-center hours or fund a new playground.",
    see: "Your feed leans toward childcare, parks, youth programs, and family services.",
  },
  {
    slug: "faith-community",
    label: "Faith & Community",
    icon: Church,
    what: "Matters affecting houses of worship and community groups.",
    eg: "A zoning variance for a church expansion, or a community-center grant.",
    see: "Surfaces decisions involving congregations, civic groups, and gathering spaces.",
  },
  {
    slug: "charitable-impact",
    label: "Charitable Impact",
    icon: Heart,
    what: "Where public dollars meet nonprofits and giving.",
    eg: "The city awarding a services contract to a local food bank.",
    see: "Highlights nonprofit funding, donations, and charitable partnerships.",
  },
  {
    slug: "neighborhood-life",
    label: "Neighborhood Life",
    icon: Trees,
    what: "The everyday texture of your streets and blocks.",
    eg: "A new sidewalk, a speed-bump petition, or a park cleanup.",
    see: "Prioritizes streets, parks, traffic, and quality-of-life items near you.",
  },
  {
    slug: "education",
    label: "Education",
    icon: GraduationCap,
    what: "Schools, students, and learning.",
    eg: "A school-board budget vote or a new attendance-zone map.",
    see: "Pulls in school-board actions, budgets, and education funding.",
  },
  {
    slug: "local-economy",
    label: "Local Economy",
    icon: Store,
    what: "Jobs, business, and money moving through town.",
    eg: "A tax incentive to land a new employer downtown.",
    see: "Focuses on business permits, incentives, development, and jobs.",
  },
];

// Story signals — how a decision BEHAVED (scored, dynamic).
const SIGNALS: CatalogItem[] = [
  {
    slug: "contested",
    label: "Contested",
    icon: Flame,
    accent: "#e11d48",
    what: "Decisions that split the room — close votes and real debate.",
    eg: "A 4–3 vote on short-term rentals after an hour of public comment.",
    see: "Bumps up anything with divided votes or heated discussion.",
  },
  {
    slug: "money-moves",
    label: "Money Moves",
    icon: Banknote,
    accent: "#b45309",
    what: "The biggest dollars on the table.",
    eg: "A $12.6M courthouse renovation contract.",
    see: "Sorts toward the largest spending and revenue decisions.",
  },
  {
    slug: "raised-eyebrows",
    label: "Raised Eyebrows",
    icon: Eye,
    accent: "#7c3aed",
    what: "Things worth a second look — patterns our watchdog flags.",
    eg: "A no-bid contract priced just under the approval threshold.",
    see: "Surfaces sole-source deals, vendor ties, and near-threshold spending.",
  },
  {
    slug: "moving-fast",
    label: "Moving Fast",
    icon: Zap,
    accent: "#0369a1",
    what: "Decisions on a short clock — little time before they're final.",
    eg: "An item added to the agenda the day before the vote.",
    see: "Flags time-sensitive items so you can weigh in before it's settled.",
  },
  {
    slug: "slipped-through",
    label: "Slipped Through",
    icon: ArrowDownToLine,
    accent: "#475569",
    what: "Big calls that passed quietly, with no debate.",
    eg: "A major rezoning approved unanimously in under a minute.",
    see: "Catches high-impact decisions that drew little attention.",
  },
  {
    slug: "helping-hands",
    label: "Helping Hands",
    icon: HeartHandshake,
    accent: "#db2777",
    what: "Public dollars flowing to local causes.",
    eg: "A grant to a neighborhood nonprofit running after-school care.",
    see: "Tracks money headed to charities and community organizations.",
  },
  {
    slug: "watch-next",
    label: "Watch Next",
    icon: Clock,
    accent: "#0d9488",
    what: "Coming up — items on the next meeting's agenda.",
    eg: "A budget hearing scheduled for the council's next session.",
    see: "Gives you a heads-up on decisions before they happen.",
  },
];

const OAUTH_PROVIDERS: { slug: string; label: string }[] = [
  { slug: "google", label: "Continue with Google" },
  { slug: "facebook", label: "Continue with Facebook" },
  { slug: "github", label: "Continue with GitHub" },
  { slug: "huggingface", label: "Continue with Hugging Face" },
];

/** Build a concise, human label from a geocoder hit (display_name is noisy). */
function placeLabel(hit: PlaceHit): string {
  const region = hit.state_code || hit.state || undefined;
  const locality = hit.city || hit.county || undefined;
  if (locality && region) return `${locality}, ${region}`;
  if (locality) return locality;
  return hit.name;
}

export default function FeedSetup() {
  const { isAuthenticated, login } = useAuth();

  const locIdRef = useRef(1);
  const [locations, setLocations] = useState<LocationRow[]>([
    { id: 1, name: "Tuscaloosa, AL", shared_level: "city", is_primary: true, state_code: "AL", state: "Alabama" },
  ]);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [placeResults, setPlaceResults] = useState<PlaceHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [lenses, setLenses] = useState<Set<string>>(new Set(["neighborhood-life", "local-economy"]));
  const [signals, setSignals] = useState<Set<string>>(new Set(["contested", "money-moves"]));
  const [detail, setDetail] = useState<DetailState | null>(null);

  const [bootstrapped, setBootstrapped] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);

  const applyConfig = (cfg: FeedConfig) => {
    if (cfg.locations && cfg.locations.length) {
      setLocations(cfg.locations.map((l) => ({ ...l })));
      locIdRef.current = Math.max(...cfg.locations.map((l) => l.id)) + 1;
    }
    setLenses(new Set(cfg.lenses || []));
    setSignals(new Set(cfg.signals || []));
  };

  const buildPayload = () => ({
    locations: locations.map((l) => ({
      name: l.name,
      shared_level: l.shared_level,
      is_primary: l.is_primary,
      state_code: l.state_code ?? null,
      state: l.state ?? null,
      county: l.county ?? null,
      latitude: l.latitude ?? null,
      longitude: l.longitude ?? null,
      jurisdiction_id: l.jurisdiction_id ?? null,
    })),
    lenses: Array.from(lenses),
    signals: Array.from(signals),
  });

  // Bootstrap on auth: resume a pending draft (post-OAuth), else load saved config.
  useEffect(() => {
    if (!isAuthenticated || bootstrapped) return;
    let cancelled = false;
    (async () => {
      const draft = localStorage.getItem(DRAFT_KEY);
      if (draft) {
        try {
          const payload = JSON.parse(draft);
          const res = await api.put<FeedConfig>("/feed/config", payload);
          if (!cancelled) {
            applyConfig(res.data);
            setSaved(true);
          }
        } catch {
          /* swallow — user can re-save */
        }
        localStorage.removeItem(DRAFT_KEY);
      } else {
        try {
          const res = await api.get<FeedConfig>("/feed/config");
          if (!cancelled) applyConfig(res.data);
        } catch {
          /* no saved config yet — keep UI defaults */
        }
      }
      if (!cancelled) setBootstrapped(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, bootstrapped]);

  // Debounced real place typeahead.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 3) {
      setPlaceResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.get<{ results: PlaceHit[] }>(
          `/feed/places?q=${encodeURIComponent(q)}`
        );
        setPlaceResults(res.data.results || []);
      } catch {
        setPlaceResults([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  const addLocation = (hit: PlaceHit) => {
    setLocations((prev) => [
      ...prev,
      {
        id: locIdRef.current++,
        name: placeLabel(hit),
        shared_level: "city",
        is_primary: prev.length === 0,
        state_code: hit.state_code ?? null,
        state: hit.state ?? null,
        county: hit.county ?? null,
        latitude: hit.latitude ?? null,
        longitude: hit.longitude ?? null,
      },
    ]);
    setQuery("");
    setPlaceResults([]);
    setAdding(false);
  };

  const removeLocation = (id: number) =>
    setLocations((prev) => {
      const next = prev.filter((l) => l.id !== id);
      if (next.length && !next.some((l) => l.is_primary))
        next[0] = { ...next[0], is_primary: true };
      return next;
    });

  const setLevel = (id: number, level: string) =>
    setLocations((prev) =>
      prev.map((l) => (l.id === id ? { ...l, shared_level: level } : l))
    );

  const makePrimary = (id: number) =>
    setLocations((prev) => prev.map((l) => ({ ...l, is_primary: l.id === id })));

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, slug: string) => {
    const next = new Set(set);
    next.has(slug) ? next.delete(slug) : next.add(slug);
    setter(next);
    setSaved(false);
  };

  const doSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await api.put<FeedConfig>("/feed/config", buildPayload());
      applyConfig(res.data);
      setSaved(true);
    } catch (e) {
      setSaveError("Couldn't save your feed. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    if (isAuthenticated) {
      doSave();
      return;
    }
    // First-time: stash the draft, then prompt sign-in. The draft auto-saves
    // when the user returns from OAuth (see bootstrap effect).
    localStorage.setItem(DRAFT_KEY, JSON.stringify(buildPayload()));
    setShowLogin(true);
  };

  return (
    <div style={{ background: SURFACE, minHeight: "100%", fontFamily: FONT_BODY, paddingBottom: 56 }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
        .seg:focus-visible{outline:2px solid ${TEAL};outline-offset:2px}
      `}</style>

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "44px 24px 0" }}>
        {/* Header */}
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 12,
            letterSpacing: ".16em",
            textTransform: "uppercase",
            color: TEAL,
            marginBottom: 8,
          }}
        >
          Set up your feed
        </div>
        <h1
          style={{
            fontFamily: FONT_SERIF,
            fontSize: 34,
            fontWeight: 700,
            color: INK,
            margin: "0 0 6px",
            letterSpacing: "-.01em",
          }}
        >
          Make it close to home
        </h1>
        <p style={{ fontSize: 16.5, color: INK_2, margin: "0 0 32px", lineHeight: 1.45 }}>
          Tell us where you live and what you care about. You decide how much
          location to share — we never store anything more precise than your choice.
        </p>

        {/* ---- Section 1: Locations ---- */}
        <SectionLabel n="1" title="Your places" />
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {locations.map((loc) => (
            <div
              key={loc.id}
              style={{
                background: CARD,
                border: `1.5px solid ${loc.is_primary ? TEAL : BORDER}`,
                borderRadius: 14,
                padding: "16px 18px",
                boxShadow: loc.is_primary
                  ? `0 8px 22px -18px ${TEAL}aa`
                  : "0 1px 2px rgba(28,25,23,.04)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 14,
                }}
              >
                <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                  <MapPin size={18} color={TEAL} strokeWidth={2.2} />
                  <span style={{ fontSize: 17, fontWeight: 600, color: INK }}>{loc.name}</span>
                  {loc.is_primary ? (
                    <span
                      style={{
                        fontFamily: FONT_MONO,
                        fontSize: 10.5,
                        letterSpacing: ".1em",
                        textTransform: "uppercase",
                        color: TEAL,
                        background: TEAL_TINT,
                        border: `1px solid ${TEAL}33`,
                        borderRadius: 999,
                        padding: "3px 9px",
                      }}
                    >
                      Primary
                    </span>
                  ) : (
                    <button
                      onClick={() => makePrimary(loc.id)}
                      style={{
                        all: "unset",
                        cursor: "pointer",
                        fontSize: 12.5,
                        color: INK_3,
                        textDecoration: "underline",
                        textUnderlineOffset: 2,
                      }}
                    >
                      make primary
                    </button>
                  )}
                </span>
                <button
                  onClick={() => removeLocation(loc.id)}
                  aria-label="Remove location"
                  style={{
                    all: "unset",
                    cursor: "pointer",
                    color: INK_3,
                    display: "inline-flex",
                    padding: 4,
                    borderRadius: 8,
                  }}
                >
                  <X size={17} />
                </button>
              </div>

              {/* shared_level segmented control */}
              <div style={{ fontSize: 12.5, color: INK_3, marginBottom: 7 }}>
                Share at the level of:
              </div>
              <div
                style={{
                  display: "flex",
                  border: `1px solid ${BORDER}`,
                  borderRadius: 10,
                  overflow: "hidden",
                  background: SURFACE,
                }}
              >
                {SHARED_LEVELS.map((lvl, i) => {
                  const on = loc.shared_level === lvl.key;
                  return (
                    <button
                      key={lvl.key}
                      className="seg"
                      onClick={() => setLevel(loc.id, lvl.key)}
                      title={lvl.hint || ""}
                      style={{
                        all: "unset",
                        cursor: "pointer",
                        flex: 1,
                        textAlign: "center",
                        padding: "9px 4px",
                        fontSize: 13.5,
                        fontWeight: on ? 600 : 500,
                        color: on ? "#fff" : INK_2,
                        background: on ? TEAL : "transparent",
                        borderRight: i < SHARED_LEVELS.length - 1 ? `1px solid ${BORDER}` : "none",
                        transition: "background .15s, color .15s",
                      }}
                    >
                      {lvl.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}

          {/* Add location */}
          {adding ? (
            <div
              style={{
                background: CARD,
                border: `1.5px dashed ${TEAL}66`,
                borderRadius: 14,
                padding: 14,
              }}
            >
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search a street, city, county, or state…"
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  border: `1px solid ${BORDER}`,
                  borderRadius: 10,
                  padding: "11px 13px",
                  fontSize: 15,
                  fontFamily: FONT_BODY,
                  color: INK,
                  outline: "none",
                }}
              />
              <div style={{ marginTop: 8, display: "flex", flexDirection: "column" }}>
                {placeResults.map((hit, idx) => (
                  <button
                    key={`${hit.latitude},${hit.longitude},${idx}`}
                    onClick={() => addLocation(hit)}
                    style={{
                      all: "unset",
                      cursor: "pointer",
                      padding: "9px 11px",
                      borderRadius: 8,
                      fontSize: 14.5,
                      color: INK,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = SURFACE)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <MapPin size={15} color={INK_3} />
                    {placeLabel(hit)}
                  </button>
                ))}
                {query.trim().length >= 3 && !searching && !placeResults.length && (
                  <div style={{ padding: "9px 11px", fontSize: 14, color: INK_3 }}>
                    No matches — try a broader name.
                  </div>
                )}
                {searching && (
                  <div style={{ padding: "9px 11px", fontSize: 14, color: INK_3 }}>Searching…</div>
                )}
                {query.trim().length > 0 && query.trim().length < 3 && (
                  <div style={{ padding: "9px 11px", fontSize: 14, color: INK_3 }}>
                    Keep typing…
                  </div>
                )}
              </div>
              <button
                onClick={() => {
                  setAdding(false);
                  setQuery("");
                  setPlaceResults([]);
                }}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  fontSize: 13,
                  color: INK_3,
                  marginTop: 6,
                  paddingLeft: 4,
                }}
              >
                cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setAdding(true)}
              style={{
                all: "unset",
                cursor: "pointer",
                border: `1.5px dashed ${BORDER}`,
                borderRadius: 14,
                padding: "15px 18px",
                color: TEAL,
                fontWeight: 600,
                fontSize: 15,
                display: "flex",
                alignItems: "center",
                gap: 8,
                justifyContent: "center",
              }}
            >
              <Plus size={17} strokeWidth={2.4} /> Add another place
            </button>
          )}
        </div>

        {/* privacy reassurance */}
        <div
          style={{
            marginTop: 14,
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            background: TEAL_TINT,
            border: `1px solid ${TEAL}26`,
            borderRadius: 12,
            padding: "12px 14px",
          }}
        >
          <Shield size={17} color={TEAL} style={{ flex: "0 0 auto", marginTop: 2 }} />
          <div style={{ fontSize: 13.5, color: "#155e54", lineHeight: 1.45 }}>
            Privacy is built in. If you pick <b>City</b>, we resolve your address
            to find your jurisdiction but store nothing finer than the city.
            There's nothing precise to leak.
          </div>
        </div>

        {/* ---- Section 2: Lenses ---- */}
        <div style={{ marginTop: 40 }}>
          <SectionLabel n="2" title="Lenses" sub="What, who, and why you care" />
          <ChipGrid
            items={LENSES}
            selected={lenses}
            onToggle={(slug) => toggle(lenses, setLenses, slug)}
            onInfo={(item) => setDetail({ item, accent: TEAL })}
            accent={TEAL}
            tint={TEAL_TINT}
          />
        </div>

        {/* ---- Section 3: Signals ---- */}
        <div style={{ marginTop: 36 }}>
          <SectionLabel n="3" title="Signals" sub="Triggers or events grabbing your attention" />
          <ChipGrid
            items={SIGNALS}
            selected={signals}
            onToggle={(slug) => toggle(signals, setSignals, slug)}
            onInfo={(item) => setDetail({ item, accent: item.accent || TEAL })}
            perItemAccent
          />
        </div>

        {/* CTA */}
        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            all: "unset",
            cursor: saving ? "default" : "pointer",
            marginTop: 40,
            width: "100%",
            boxSizing: "border-box",
            textAlign: "center",
            background: saved ? "#15803d" : TEAL,
            color: "#fff",
            fontSize: 16.5,
            fontWeight: 600,
            padding: "15px",
            borderRadius: 12,
            opacity: saving ? 0.7 : 1,
            boxShadow: `0 10px 24px -14px ${TEAL}`,
          }}
        >
          {saving ? "Saving…" : saved ? "Saved ✓" : isAuthenticated ? "Save my feed" : "Sign in & save my feed"}
        </button>
        {saveError && (
          <div style={{ textAlign: "center", marginTop: 10, fontSize: 13.5, color: "#b91c1c" }}>
            {saveError}
          </div>
        )}
        <div style={{ textAlign: "center", marginTop: 12, fontSize: 13, color: INK_3 }}>
          {locations.length} place{locations.length !== 1 ? "s" : ""} · {lenses.size} lens
          {lenses.size !== 1 ? "es" : ""} · {signals.size} signal
          {signals.size !== 1 ? "s" : ""}
        </div>
      </div>

      <DetailCard
        detail={detail}
        onClose={() => setDetail(null)}
        onToggle={(slug) => {
          if (LENSES.some((l) => l.slug === slug)) toggle(lenses, setLenses, slug);
          else toggle(signals, setSignals, slug);
        }}
        selected={detail && LENSES.some((l) => l.slug === detail.item.slug) ? lenses : signals}
      />

      {showLogin && <LoginModal onClose={() => setShowLogin(false)} login={login} />}
    </div>
  );
}

function SectionLabel({ n, title, sub }: { n: string; title: string; sub?: string }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span
          style={{
            fontFamily: FONT_MONO,
            fontSize: 12,
            color: TEAL,
            border: `1px solid ${TEAL}40`,
            borderRadius: 6,
            padding: "1px 7px",
          }}
        >
          {n}
        </span>
        <h2
          style={{
            fontFamily: FONT_SERIF,
            fontSize: 22,
            fontWeight: 600,
            color: INK,
            margin: 0,
          }}
        >
          {title}
        </h2>
      </div>
      {sub && (
        <div style={{ fontSize: 13.5, color: INK_3, marginTop: 4, paddingLeft: 32 }}>{sub}</div>
      )}
    </div>
  );
}

interface ChipGridProps {
  items: CatalogItem[];
  selected: Set<string>;
  onToggle: (slug: string) => void;
  onInfo: (item: CatalogItem) => void;
  accent?: string;
  tint?: string;
  perItemAccent?: boolean;
}

function ChipGrid({ items, selected, onToggle, onInfo, accent, tint, perItemAccent }: ChipGridProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
        gap: 10,
      }}
    >
      {items.map((it) => {
        const Icon = it.icon;
        const on = selected.has(it.slug);
        const a = (perItemAccent ? it.accent : accent) || TEAL;
        const t = perItemAccent ? `${it.accent}14` : tint;
        return (
          <div
            key={it.slug}
            role="button"
            tabIndex={0}
            onClick={() => onToggle(it.slug)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onToggle(it.slug);
              }
            }}
            style={{
              cursor: "pointer",
              boxSizing: "border-box",
              display: "flex",
              alignItems: "center",
              gap: 11,
              padding: "13px 12px 13px 14px",
              borderRadius: 12,
              background: on ? t : CARD,
              border: `1.5px solid ${on ? a : BORDER}`,
              transition: "all .15s",
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 34,
                borderRadius: 9,
                background: on ? a : "#f5f5f4",
                color: on ? "#fff" : INK_3,
                flex: "0 0 auto",
                transition: "all .15s",
              }}
            >
              <Icon size={18} strokeWidth={2} />
            </span>
            <span
              style={{
                flex: 1,
                fontSize: 15,
                fontWeight: on ? 600 : 500,
                color: on ? INK : INK_2,
                minWidth: 0,
              }}
            >
              {it.label}
            </span>
            {on && <Check size={16} color={a} strokeWidth={2.6} style={{ flex: "0 0 auto" }} />}
            <button
              aria-label={`What is ${it.label}?`}
              onClick={(e) => {
                e.stopPropagation();
                onInfo(it);
              }}
              title="What's this?"
              style={{
                all: "unset",
                cursor: "pointer",
                flex: "0 0 auto",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: 24,
                height: 24,
                borderRadius: 999,
                color: on ? a : INK_3,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = `${a}1f`)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Info size={16} strokeWidth={2.2} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

interface DetailCardProps {
  detail: DetailState | null;
  onClose: () => void;
  onToggle: (slug: string) => void;
  selected: Set<string>;
}

function DetailCard({ detail, onClose, onToggle, selected }: DetailCardProps) {
  if (!detail) return null;
  const { item, accent } = detail;
  const Icon = item.icon;
  const on = selected.has(item.slug);
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(28,25,23,.34)",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        padding: 16,
        backdropFilter: "blur(2px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 460,
          background: CARD,
          borderRadius: 18,
          border: `1px solid ${BORDER}`,
          boxShadow: "0 24px 60px -20px rgba(28,25,23,.5)",
          overflow: "hidden",
          fontFamily: FONT_BODY,
          alignSelf: "center",
        }}
      >
        {/* header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 13,
            padding: "20px 20px 16px",
            background: `${accent}0d`,
            borderBottom: `1px solid ${accent}26`,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 46,
              height: 46,
              borderRadius: 12,
              background: accent,
              color: "#fff",
              flex: "0 0 auto",
            }}
          >
            <Icon size={24} strokeWidth={2} />
          </span>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontFamily: FONT_SERIF,
                fontSize: 23,
                fontWeight: 700,
                color: INK,
                lineHeight: 1.1,
              }}
            >
              {item.label}
            </div>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            style={{
              all: "unset",
              cursor: "pointer",
              color: INK_3,
              padding: 6,
              borderRadius: 8,
              display: "inline-flex",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* body */}
        <div style={{ padding: "18px 20px 20px" }}>
          <p style={{ fontSize: 16.5, color: INK, lineHeight: 1.5, margin: "0 0 18px", fontWeight: 500 }}>
            {item.what}
          </p>

          <DetailRow
            icon={<Lightbulb size={16} strokeWidth={2.2} />}
            accent={accent}
            label="For example"
            text={item.eg}
          />
          <div style={{ height: 12 }} />
          <DetailRow
            icon={<ArrowRight size={16} strokeWidth={2.2} />}
            accent={accent}
            label="In your feed"
            text={item.see}
          />

          {/* toggle from inside the card */}
          <button
            onClick={() => onToggle(item.slug)}
            style={{
              all: "unset",
              cursor: "pointer",
              marginTop: 20,
              boxSizing: "border-box",
              width: "100%",
              textAlign: "center",
              padding: "12px",
              borderRadius: 11,
              fontSize: 15.5,
              fontWeight: 600,
              color: on ? accent : "#fff",
              background: on ? `${accent}14` : accent,
              border: `1.5px solid ${accent}`,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
            }}
          >
            {on ? (
              <>
                <Check size={17} strokeWidth={2.6} /> Added — tap to remove
              </>
            ) : (
              <>
                <Plus size={17} strokeWidth={2.4} /> Add to my feed
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailRow({
  icon,
  accent,
  label,
  text,
}: {
  icon: React.ReactNode;
  accent: string;
  label: string;
  text: string;
}) {
  return (
    <div style={{ display: "flex", gap: 11, alignItems: "flex-start" }}>
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 30,
          height: 30,
          borderRadius: 8,
          background: `${accent}14`,
          color: accent,
          flex: "0 0 auto",
          marginTop: 1,
        }}
      >
        {icon}
      </span>
      <div>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: 11,
            letterSpacing: ".1em",
            textTransform: "uppercase",
            color: INK_3,
            marginBottom: 2,
          }}
        >
          {label}
        </div>
        <div style={{ fontSize: 14.5, color: INK_2, lineHeight: 1.45 }}>{text}</div>
      </div>
    </div>
  );
}

function LoginModal({ onClose, login }: { onClose: () => void; login: (provider: string) => void }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        background: "rgba(28,25,23,.42)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        backdropFilter: "blur(2px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 420,
          background: CARD,
          borderRadius: 18,
          border: `1px solid ${BORDER}`,
          boxShadow: "0 24px 60px -20px rgba(28,25,23,.5)",
          overflow: "hidden",
          fontFamily: FONT_BODY,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "20px 20px 16px",
            background: TEAL_TINT,
            borderBottom: `1px solid ${TEAL}26`,
          }}
        >
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 44,
              height: 44,
              borderRadius: 12,
              background: TEAL,
              color: "#fff",
              flex: "0 0 auto",
            }}
          >
            <LogIn size={22} strokeWidth={2} />
          </span>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: FONT_SERIF, fontSize: 21, fontWeight: 700, color: INK, lineHeight: 1.1 }}>
              Sign in to save
            </div>
          </div>
          <button
            aria-label="Close"
            onClick={onClose}
            style={{ all: "unset", cursor: "pointer", color: INK_3, padding: 6, display: "inline-flex" }}
          >
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: "18px 20px 22px" }}>
          <p style={{ fontSize: 15, color: INK_2, lineHeight: 1.5, margin: "0 0 18px" }}>
            Your feed is ready — sign in to save it to your account. We'll pick up
            right where you left off the moment you're back.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {OAUTH_PROVIDERS.map((p) => (
              <button
                key={p.slug}
                onClick={() => login(p.slug)}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  boxSizing: "border-box",
                  width: "100%",
                  textAlign: "center",
                  padding: "12px",
                  borderRadius: 11,
                  fontSize: 15,
                  fontWeight: 600,
                  color: INK,
                  background: SURFACE,
                  border: `1.5px solid ${BORDER}`,
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = TEAL)}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = BORDER)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
