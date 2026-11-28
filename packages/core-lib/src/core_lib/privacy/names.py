"""Shorten private people's names, and drop home addresses, in meeting text we serve (#1468).

Transcript excerpts, public-comment quotes and search snippets are verbatim, so they can carry a resident's full name
("Next, John Smith of 412 Elm Street", "my name is Mary Ann Smith", "my neighbour Bob Jones") even when the speaker
label beside them is already "First L.". The privacy rule (AGENTS.md, "Privacy and data ethics") is that a private
resident appears only as "First L." and is never enriched, and that a home address is never shown.

``NameRedactor.redact`` rewrites a piece of text so that:

- a probable person's name becomes "First L." ("John Smith" -> "John S.", "Mary Ann Smith" -> "Mary S.") and a
  surname after a courtesy title becomes its initial ("Mr. Smith" -> "Mr. S.");
- a street address after "I live at", "my address is", or "of / at / from <number> <street>" becomes ``[address]``;
- the names of public officials are kept: a name that matches a roster official of the meeting's own government
  (the caller passes them), a name right after an office title ("Councilman Joe Roe", "Mayor Jane Doe"), and widely
  known public figures on the reviewed allow-list (``trending_term_public_figure`` seed);
- ``<mark>``/``</mark>`` highlighting from ``ts_headline`` survives: tags are lifted out before matching and put back
  around the same characters (a shortened name that was highlighted stays highlighted).

How a name is found (no model, no network, no lookup about anyone):

- **after a cue**: "my name is", "name's", "next speaker is", "speaker will be", "calling up", "I'm", "I am",
  "this is", "thank you", "thanks", "welcome", "Mr./Ms./Mrs./Dr./Miss". After a strong cue ("my name is", "next
  speaker") the words are taken even in lower-case captions; after a weak one ("I'm", "this is", "thank you") the
  first word must be capitalised or a known given name, so "I'm going to" is left alone.
- **anywhere**: a known given name (the aggregate list in ``given_names.py``) followed by one to three capitalised
  words that aren't ordinary words, places or roles ("Bob Jones said", "my neighbour Bob Jones").

It is deliberately conservative: when a pair might be a name, it is shortened. A name followed by an organisation or
place word ("John Smith Park", "Jones Construction") is an entity's name and is kept. A lone first name is already
"First" and is kept.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Optional

from core_lib.privacy.given_names import given_names

ADDRESS_MASK = "[address]"
NAME_MASK = "[name]"

# A school board's meeting (the rule meeting_speaker_intro and the topic routes use): named residents may be students.
SCHOOL_RE = re.compile(
    r"(school|\bisd\b|\busd\b|board\s+of\s+ed|schools?\s+board|school\s+committee|\bboe\b)", re.I
)

_MARK_RE = re.compile(r"</?mark>", re.I)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")

# --------------------------------------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------------------------------------

# Never part of a name: function words, fillers, pronouns, common verbs and adjectives that follow the cues.
STOPWORDS = frozenset(
    """
    a an the and or but nor so yet for of to in on at by with from into onto about above after again against all
    also am any are as be because been before being below between both can cannot could did do does doing done
    down during each few further had has have having he her here hers herself him himself his how i if is it its
    itself just me more most my myself no not now off once only other our ours ourselves out over own same she
    should some such than that their theirs them themselves then there these they this those through too under
    until up very was we were what when where which while who whom why will would you your yours yourself
    yourselves um uh er ah oh okay ok yes yeah well like really actually basically sure thanks thank please sorry
    hello hi hey good evening morning afternoon night everyone everybody all folks guys ladies gentlemen
    sir madam maam going gonna gotta wanna trying try want wanted here's there's it's that's i'm i've i'll i'd
    we're we've you're they're he's she's let's calling call called speaking speak spoke talk talking asking ask
    asked coming come came glad happy proud excited honored honoured pleased grateful today tonight tomorrow
    yesterday just still again back currently retired new old long life lifelong born raised one two three four
    five six seven eight nine ten little bit lot much many least whole entire part not never nothing something
    anything everything someone anyone nobody somebody anybody concerned worried disappointed sad tired confused
    curious upset angry frustrated aware afraid able unable mad sick unanimous unanimously moving move moved
    second seconded motion vote voted approve approved deny denied yes no aye ayes nay nays opposed abstain
    so-called
    """.split()
)

# Roles, bodies and generic nouns: a capitalised one is not a surname ("Will Council", "Mary Public").
ROLE_WORDS = frozenset(
    """
    mayor council councilman councilwoman councilmember councilmembers councilor councillor councilors chair
    chairman chairwoman chairperson president vice commissioner commissioners board members member staff city town
    county village state township district school schools public resident residents citizen citizens neighbor
    neighbour neighbors neighbours speaker speakers item agenda meeting hearing comment comments session minutes
    committee commission department office division government federal national american united states america
    attorney manager director clerk secretary treasurer engineer planner applicant developer consultant
    representative senator governor judge sheriff chief officer police fire sergeant lieutenant captain detective
    superintendent principal teacher student students pastor reverend father mother parent parents family
    january february march april june july august september october november december monday tuesday wednesday
    thursday friday saturday sunday
    """.split()
)

# A name followed by one of these is an entity's name, not a person's ("John Smith Park", "Jones Construction").
ENTITY_WORDS = frozenset(
    """
    park parks center centre centers school schools elementary middle high academy college university library
    bridge boulevard blvd drive street road avenue lane way place court circle highway parkway building hall
    stadium field fields arena memorial foundation fund company co corp corporation construction inc llc lp llp
    ltd associates group law firm realty homes properties property development developments church ministries
    ministry award awards act bill scholarship day week month plan program project trail lake river creek
    museum theater theatre hospital clinic airport station tower towers apartments village estates subdivision
    farms farm industries enterprises partners holdings bank trust insurance motors auto services service
    institute society club league association council committee commission board authority district
    cemetery healthcare health medical care senior refinery point plant mill mills market store shop restaurant
    cafe grill pharmacy energy power electric water gas oil solar wind utilities media news press times gazette
    tribune herald journal post radio tv network studios studio games team center's hall's
    shelter rescue alliance coalition partnership initiative campaign festival fair parade conference summit
    animal animals affairs relations resources works safety transit transportation housing
    """.split()
)

# Words after which a name is a public official's in their role: kept as said.
OFFICE_TITLES = frozenset(
    """
    mayor councilman councilwoman councilmember councilor councillor alderman alderwoman alderperson commissioner
    supervisor senator representative rep congressman congresswoman congressperson governor lieutenant judge
    justice sheriff chief superintendent president chairman chairwoman chairperson chair delegate assemblyman
    assemblywoman assemblymember secretary treasurer clerk comptroller auditor director administrator manager
    attorney officer sergeant captain detective deputy trustee
    """.split()
)
_TWO_WORD_OFFICES = ("council member", "vice mayor", "vice chair", "board member", "city manager", "city attorney",
                     "city clerk", "county judge", "state senator", "state representative", "attorney general",
                     "police chief", "fire chief", "mayor pro")

COURTESY_TITLES = ("mr", "mrs", "ms", "miss", "mister", "dr", "doctor", "mx")

# Given names that are also ordinary words: they start a name only after a cue, never on their own.
AMBIGUOUS_GIVEN = frozenset(
    """
    art bill chance chase dawn faith grant guy hope joy june king lane major mark may page precious price ray rich
    rose sterling summer will april august autumn ivy jewel penny amber crystal ruby pearl angel honor patience
    glory harmony hunter mason cooper carter marshall miles pierce reed noble justice royal queen baby young brown
    white black green gray grey long short little star sky victory destiny trinity duke lord prince christian
    junior senior georgia carolina virginia santa san
    """.split()
)

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}

STREET_SUFFIX = (
    r"(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct|boulevard|blvd|way|place|pl|circle|cir|parkway|"
    r"pkwy|highway|hwy|terrace|ter|trail|trl|loop|run|pike|square|sq|crossing|xing|cove|cv|ridge|point|pt)"
)
_NUM_ADDR = rf"\d{{1,6}}[A-Za-z]?(?:\s+[A-Za-z0-9.'’\-]+){{0,4}}\s+{STREET_SUFFIX}\b\.?"
# "I live at 412 Elm", "my address is 412 Elm Street": the number and up to four words (or up to the suffix).
_ADDR_PERSONAL = re.compile(
    rf"(\b(?:i\s+live\s+(?:over\s+)?at|i\s+live\s+on|i\s+reside\s+at|i'm\s+at|i\s+am\s+at|my\s+address\s+is|"
    rf"(?:my\s+)?home\s+address\s+is|my\s+home\s+is\s+at|my\s+house\s+is\s+at|lives?\s+at|residing\s+at|resides\s+at|"
    rf"address\s+of)[,:]?\s+)"
    rf"((?:{_NUM_ADDR})|\d{{1,6}}[A-Za-z]?(?:\s+(?!and\b|i\b)[A-Za-z][A-Za-z'’\-]*){{1,4}})",
    re.I,
)
# "John Smith of 412 Elm Street", "from 1200 Oak Ridge Drive".
_ADDR_PREP = re.compile(rf"(\b(?:of|at|from|on)\s+)({_NUM_ADDR})", re.I)
# The chair's sign-up sheet: "Mike Smith, 96 Maple Street".
_ADDR_AFTER_NAME = re.compile(rf"((?:\b[A-Z][a-z'’\-]+|\b[A-Z]\.),\s+)((?i:{_NUM_ADDR}))")

# Cues before a name. Strong ones take lower-case words; weak ones need a capitalised or known given name.
_STRONG_CUE = re.compile(
    r"\b(?:my\s+name(?:'s|’s|\s+is)|name\s+is|names\s+are|"
    r"(?:next|first|last|final)\s+(?:speaker|person|commenter)(?:\s+(?:is|will\s+be|we\s+have\s+is|i\s+have\s+is|would\s+be))?|"
    r"speaker\s+(?:is|will\s+be)|signed\s+up\s+(?:is|was))[,:]?\s+(?:(?:uh|um|er|ah)[,.]?\s+)?",
    re.I,
)
# Weak cues about the speaker or someone they know: any capitalised first word.
_WEAK_CUE = re.compile(
    r"\b(?:i'm|i’m|i\s+am|neighbou?rs?|my\s+(?:friend|neighbou?r|husband|wife|son|daughter|"
    r"mother|father|brother|sister))[,:]?\s+(?:(?:uh|um|er|ah)[,.]?\s+)?",
    re.I,
)
# Weak cues that also precede places and events ("welcome Christmas Extravaganza", "this is Main Street"): the first
# word must be a known given name.
_GREETING_CUE = re.compile(
    r"\b(?:this\s+is|thank\s+you(?:\s+(?:so|very)\s+much)?|thanks|welcome|hello|calling\s+(?:up\s+)?|call\s+up|"
    r"followed\s+by|recogni[sz]e|next\s+up(?:\s+is)?|"
    r"good\s+(?:evening|morning|afternoon))[,:]?\s+(?:(?:uh|um|er|ah)[,.]?\s+)?",
    re.I,
)
_COURTESY_RE = re.compile(r"\b(" + "|".join(COURTESY_TITLES) + r")(\.?)\s+", re.I)


def _norm(word: str) -> str:
    return word.lower().replace("’", "'").strip("'-")


def _is_cap(word: str) -> bool:
    return word[:1].isupper()


@lru_cache(maxsize=1)
def _default_public_figures() -> frozenset[str]:
    """The reviewed public-figure allow-list (a generated copy of the ``trending_term_public_figure`` seed)."""
    from core_lib.privacy._public_figures_data import PUBLIC_FIGURES

    return PUBLIC_FIGURES


def load_public_figures_csv(path: Path | str) -> frozenset[str]:
    """Lower-case terms and labels from ``trending_term_public_figure.csv`` ("trump", "donald trump", ...)."""
    out: set[str] = set()
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for key in ("term", "label"):
                v = (row.get(key) or "").strip().lower()
                if v:
                    out.add(re.sub(r"[^a-z' ]", "", v).strip())
    return frozenset(v for v in out if v)


def official_name_key(full_name: str) -> Optional[str]:
    """ "first last", lower-case, from an official's full name (middle names and suffixes dropped)."""
    cleaned = re.sub(r"(?<=[a-z])\.(?=[a-z])", "", (full_name or "").lower())  # "a.j." -> "aj."
    words = [w for w in re.split(r"[\s\-]+", re.sub(r"[^a-z' \-]", " ", cleaned)) if w]
    words = [w.strip("'") for w in words if w.strip("'") not in _SUFFIXES]
    if len(words) < 2:
        return None
    return f"{words[0]} {words[-1]}"


@dataclass
class _Tok:
    text: str
    start: int
    end: int

    @property
    def low(self) -> str:
        return _norm(self.text)


@dataclass
class NameRedactor:
    """Shortens names in served text. Officials are passed per call, so one instance serves every jurisdiction."""

    given: frozenset[str] = field(default_factory=given_names)
    public_figures: frozenset[str] = field(default_factory=_default_public_figures)

    # ----------------------------------------------------------------------------------------------------------------
    def redact(
        self, text: Optional[str], *, official_names: Iterable[str] = (), school: bool = False
    ) -> Optional[str]:
        """``text`` with private names shortened and addresses masked. ``official_names`` are "first last" keys
        (see ``official_name_key``) of the roster officials of the text's government; they are kept as said.

        ``school``: the text is from a school-board meeting, where a named resident may be a student (AGENTS.md:
        never name a minor). Every private name, a lone first name after a cue included, becomes ``[name]``."""
        if not text:
            return text
        plain, marked = _lift_marks(text)
        edits = self._edits(plain, frozenset(official_names), school)
        if not edits:
            return text
        return _rebuild(plain, marked, edits)

    def redact_segments(
        self, texts: list[str], *, official_names: Iterable[str] = (), school: bool = False
    ) -> list[str]:
        """Redact a timed transcript's cues as one text, so a name split over two cues ("next speaker is John" |
        "Smith of Elm Street") is still found. A replacement lands in the cue where the name starts; the rest of the
        name is removed from the following cue(s). Returns one string per input cue."""
        if not texts:
            return list(texts)
        starts: list[int] = []
        pos = 0
        for t in texts:
            starts.append(pos)
            pos += len(t) + 1
        plain = " ".join(texts)
        edits = self._edits(plain, frozenset(official_names), school)
        if not edits:
            return list(texts)
        out: list[str] = []
        for k, t in enumerate(texts):
            cs, ce = starts[k], starts[k] + len(t)
            pieces: list[str] = []
            cur = cs
            for s, e, new in edits:
                if e <= cs or s >= ce:
                    continue
                if s >= cs:
                    pieces.append(plain[cur:s])
                    pieces.append(new)
                cur = max(cur, min(e, ce))
            pieces.append(plain[cur:ce])
            out.append("".join(pieces).strip() if len(pieces) > 1 else t)
        return out

    def _edits(self, plain: str, officials: frozenset[str], school: bool = False) -> list[tuple[int, int, str]]:
        edits: list[tuple[int, int, str]] = []
        for rx in (_ADDR_PERSONAL, _ADDR_PREP, _ADDR_AFTER_NAME):
            for m in rx.finditer(plain):
                if not _overlaps(edits, m.start(2), m.end(2)):
                    edits.append((m.start(2), m.end(2), ADDRESS_MASK))
        toks = [_Tok(m.group(0), m.start(), m.end()) for m in _WORD_RE.finditer(plain)]
        cased = _is_cased(plain, toks)
        edits.extend(e for e in self._name_edits(plain, toks, officials, cased, school) if not _overlaps(edits, e[0], e[1]))
        # "Mr. Smith." -> "Mr. S." rather than "Mr. S..".
        edits = [
            (s, e + 1, new) if new.endswith(".") and plain[e:e + 1] == "." else (s, e, new) for s, e, new in edits
        ]
        return sorted(edits)

    # ----------------------------------------------------------------------------------------------------------------
    def _name_edits(
        self, plain: str, toks: list[_Tok], officials: frozenset[str], cased: bool, school: bool = False
    ) -> list[tuple[int, int, str]]:
        by_start = {t.start: i for i, t in enumerate(toks)}
        edits: list[tuple[int, int, str]] = []
        taken: set[int] = set()

        def tok_at(pos: int) -> Optional[int]:
            return by_start.get(pos)

        # 1. Courtesy titles: "Mr. Smith" -> "Mr. S."; "Dr. Jane Smith" -> "Dr. Jane S.".
        for m in _COURTESY_RE.finditer(plain):
            i = tok_at(m.end())
            if i is None or i in taken:
                continue
            span = self._span(plain, toks, i, strong=True, after_title=True)
            if not span:
                continue
            a, b = span
            words = [toks[k] for k in range(a, b + 1)]
            if self._keep(plain, toks, a, b, officials, courtesy=True):
                taken.update(range(a, b + 1))
                continue
            if school:
                new = NAME_MASK
            elif len(words) == 1:
                new = _initial(words[0].text)
            else:
                new = _first_l(words[0].text, words[-1].text)
            edits.append((words[0].start, words[-1].end, new))
            taken.update(range(a, b + 1))

        # 2. Cued names.
        # In mixed-case text every cue needs a capitalised name; lower-case captions rely on strong cues.
        for rx, strong, need_given in ((_STRONG_CUE, True, False), (_WEAK_CUE, False, False), (_GREETING_CUE, False, True)):
            for m in rx.finditer(plain):
                i = tok_at(m.end())
                if i is None or i in taken:
                    continue
                if need_given and toks[i].low not in self.given:
                    continue
                # A title after the cue: an office keeps the name; a courtesy title was handled above.
                if toks[i].low.rstrip(".") in COURTESY_TITLES:
                    continue
                if toks[i].low in OFFICE_TITLES or _two_word_office(toks, i):
                    span = self._span(plain, toks, i + (2 if _two_word_office(toks, i) else 1), strong=True)
                    if span:
                        taken.update(range(span[0], span[1] + 1))
                    continue
                span = self._span(plain, toks, i, strong=strong, need_cap=cased and not strong)
                if span:
                    self._shorten(plain, toks, span, officials, edits, taken, school=school, cued=True)

        # 3. Bare names: a known given name + capitalised surname(s), anywhere.
        for i, t in enumerate(toks):
            if i in taken or not _is_cap(t.text) or t.low not in self.given or t.low in AMBIGUOUS_GIVEN:
                continue
            if t.low in STOPWORDS or t.low in ROLE_WORDS:
                continue
            span = self._span(plain, toks, i, strong=False, need_cap=True)
            if span and span[1] > span[0]:
                self._shorten(plain, toks, span, officials, edits, taken, school=school)
        return edits

    # ----------------------------------------------------------------------------------------------------------------
    def _span(
        self,
        plain: str,
        toks: list[_Tok],
        i: int,
        *,
        strong: bool,
        need_cap: bool = False,
        after_title: bool = False,
    ) -> Optional[tuple[int, int]]:
        """(first, last) token index of the name starting at token ``i``, or None when it isn't a name."""
        if i >= len(toks):
            return None
        first = toks[i]
        if not _nameish(first.low) or len(first.low) < 2 or _is_entity(first.low):
            return None
        if not strong and not after_title and not (_is_cap(first.text) or first.low in self.given):
            return None
        if need_cap and not _is_cap(first.text):
            return None
        # Mixed-case text: a capitalised first word takes only capitalised words after it ("Ms. Jane Doe said").
        # Lower-case captions: only a strong cue, or a title before a known given name, carries on past one word.
        case_locked = _is_cap(first.text)
        if not case_locked and after_title and first.low not in self.given:
            return i, i
        j = i
        # At most three words (first, middle, last): a longer capitalised run is a title or an entity's name.
        while j + 1 < len(toks) and j - i < 2:
            nxt = toks[j + 1]
            gap = plain[toks[j].end:nxt.start]
            if gap.strip() not in ("",):
                break
            low = nxt.low.rstrip(".")
            if low in _SUFFIXES:
                j += 1
                continue
            if not _nameish(nxt.low) or len(nxt.low) < 2 or _is_entity(low):
                break
            # "JOHN STANDS": an all-capitals word after a normal one is shouting or a heading, not a surname.
            if nxt.text.isupper() and len(nxt.text) > 1 and not first.text.isupper():
                break
            # After a weak cue or bare given name, the surname must look like one (capitalised).
            if (need_cap or not strong or case_locked) and not _is_cap(nxt.text):
                break
            j += 1
        # Drop trailing generational suffixes from the span.
        while j > i and toks[j].low.rstrip(".") in _SUFFIXES:
            j -= 1
        # A weak cue with a lone lower-case word is not a name ("I'm happy").
        if not strong and not after_title and j == i and not _is_cap(first.text):
            return None
        return i, j

    def _keep(self, plain: str, toks: list[_Tok], a: int, b: int, officials: frozenset[str], *, courtesy: bool = False) -> bool:
        words = [toks[k].low for k in range(a, b + 1) if toks[k].low.rstrip(".") not in _SUFFIXES]
        full = " ".join(words)
        key = f"{words[0]} {words[-1]}" if len(words) >= 2 else None
        # Public figures on the reviewed allow-list.
        if full in self.public_figures or (key and key in self.public_figures):
            return True
        if words[-1] in self.public_figures and (len(words) == 1 or key in self.public_figures or courtesy):
            return True
        # Roster officials of this government.
        if key and key in officials:
            return True
        if courtesy and len(words) == 1 and any(o.split(" ")[-1] == words[0] for o in officials):
            return True
        # An office title right before the name: a public role.
        if a >= 1 and (toks[a - 1].low in OFFICE_TITLES or (a >= 2 and _two_word_office(toks, a - 2))):
            gap = plain[toks[a - 1].end:toks[a].start]
            if gap.strip() in ("", "."):
                return True
        # An entity's name ("John Smith Park", "Cheyenne Senior Center"), or a Title Case phrase that carries on past
        # the name ("Crawford Prevention Programs"): the next word is capitalised too.
        nb = b + 1
        while nb < len(toks) and toks[nb].low.rstrip(".") in _SUFFIXES:
            nb += 1
        if nb < len(toks) and nb == b + 1 and _is_cap(toks[nb].text) and toks[nb].low not in STOPWORDS:
            gap = plain[toks[b].end:toks[nb].start]
            if gap.strip() == "":
                return True
        return False

    def _shorten(
        self,
        plain: str,
        toks: list[_Tok],
        span: tuple[int, int],
        officials: frozenset[str],
        edits: list[tuple[int, int, str]],
        taken: set[int],
        *,
        school: bool = False,
        cued: bool = False,
    ) -> None:
        a, b = span
        taken.update(range(a, b + 1))
        if b == a:
            # A first name alone is already "First", except where it may be a student's.
            if school and cued and not self._keep(plain, toks, a, b, officials):
                edits.append((toks[a].start, toks[a].end, NAME_MASK))
            return
        if self._keep(plain, toks, a, b, officials):
            return
        # The last real word (generational suffixes trimmed by _span) is the surname.
        new = NAME_MASK if school else _first_l(toks[a].text, toks[b].text)
        edits.append((toks[a].start, toks[b].end, new))


def _is_entity(low: str) -> bool:
    w = re.sub(r"'s$", "", low.rstrip("."))
    return w in ENTITY_WORDS or (w.endswith("s") and w[:-1] in ENTITY_WORDS)


def _is_cased(plain: str, toks: list[_Tok]) -> bool:
    """Whether the text uses capitals (edited captions, documents) rather than all lower-case auto captions: at least
    two capitalised words that don't start a sentence and aren't "I"."""
    n = 0
    for t in toks:
        if not _is_cap(t.text) or t.low in ("i", "i'm", "i've", "i'll", "i'd"):
            continue
        k = t.start - 1
        while k >= 0 and plain[k] in " \t":
            k -= 1
        if k >= 0 and plain[k] not in ".!?>:\"\n\r":
            n += 1
            if n >= 2:
                return True
    return False


def _nameish(low: str) -> bool:
    w = low.rstrip(".")
    return (
        bool(re.fullmatch(r"[a-z][a-z'\-]*", w))
        and w not in STOPWORDS
        and w not in ROLE_WORDS
        and w not in OFFICE_TITLES
        and w not in COURTESY_TITLES
        and not re.search(r"(?:ed|ly|ing|ful|ous|ness)$", w)
    )


def _two_word_office(toks: list[_Tok], i: int) -> bool:
    if i + 1 >= len(toks):
        return False
    return f"{toks[i].low} {toks[i + 1].low}" in _TWO_WORD_OFFICES


def _possessive(word: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)(['’]s)$", word)
    return (m.group(1), m.group(2)) if m and len(m.group(1)) >= 2 else (word, "")


def _initial(word: str) -> str:
    base, poss = _possessive(word)
    return base[:1].upper() + "." + poss


def _first_l(first: str, last: str) -> str:
    f = first if _is_cap(first) else first[:1].upper() + first[1:]
    return f"{f} {_initial(last)}"


def _overlaps(edits: list[tuple[int, int, str]], a: int, b: int) -> bool:
    return any(a < e and s < b for s, e, _ in edits)


def _lift_marks(text: str) -> tuple[str, list[bool]]:
    """The text without <mark> tags, and for each remaining character whether it was inside a mark."""
    plain: list[str] = []
    marked: list[bool] = []
    inside = False
    pos = 0
    for m in _MARK_RE.finditer(text):
        seg = text[pos:m.start()]
        plain.append(seg)
        marked.extend([inside] * len(seg))
        inside = not m.group(0).startswith("</")
        pos = m.end()
    seg = text[pos:]
    plain.append(seg)
    marked.extend([inside] * len(seg))
    return "".join(plain), marked


def _rebuild(plain: str, marked: list[bool], edits: list[tuple[int, int, str]]) -> str:
    """Apply the edits and put the marks back: a replacement is marked when any character it replaced was."""
    pieces: list[tuple[str, bool]] = []
    pos = 0
    for s, e, new in edits:
        pieces.extend((plain[k], marked[k]) for k in range(pos, s))
        hl = any(marked[s:e])
        pieces.extend((ch, hl) for ch in new)
        pos = e
    pieces.extend((plain[k], marked[k]) for k in range(pos, len(plain)))
    out: list[str] = []
    state = False
    for ch, hl in pieces:
        if hl != state:
            out.append("<mark>" if hl else "</mark>")
            state = hl
        out.append(ch)
    if state:
        out.append("</mark>")
    return "".join(out)


def shorten_full_name(name: Optional[str], *, official_names: Iterable[str] = ()) -> Optional[str]:
    """A name field (not running text) in the served form: an official's name as is, anyone else "First L."
    ("Jane Q. Doe" -> "Jane D.", "Bob E." and "Audrey" unchanged). Honorifics and suffixes are dropped first."""
    if not name or not isinstance(name, str):
        return name
    words = [w for w in name.strip().split() if w]
    while words and _norm(words[0]).rstrip(".") in COURTESY_TITLES:
        words.pop(0)
    while len(words) > 1 and _norm(words[-1]).rstrip(".,") in _SUFFIXES:
        words.pop()
    if len(words) < 2:
        return name
    key = official_name_key(" ".join(words))
    if key and key in frozenset(official_names):
        return name
    last = words[-1].rstrip(",")
    if len(last.rstrip(".")) <= 1:
        return name  # already "First L."
    return _first_l(words[0], last)


@lru_cache(maxsize=1)
def default_redactor() -> NameRedactor:
    return NameRedactor()


def redact_person_names(
    text: Optional[str], *, official_names: Iterable[str] = (), school: bool = False
) -> Optional[str]:
    """``default_redactor().redact``: shorten private names to "First L." and mask home addresses in served text."""
    return default_redactor().redact(text, official_names=official_names, school=school)


def is_school_board(*labels: Optional[str]) -> bool:
    """Whether a jurisdiction name, type or meeting title names a school board ("Tuscaloosa City Schools",
    "school_district", "Board of Education regular meeting")."""
    return any(bool(x) and bool(SCHOOL_RE.search(str(x))) for x in labels)


def official_keys(full_names: Iterable[str]) -> frozenset[str]:
    """``official_name_key`` for each name, dropping the ones that aren't first + last."""
    return frozenset(k for k in (official_name_key(n) for n in full_names) if k)


def officials_by_place(rows: Iterable[Mapping[str, object]]) -> dict[str, frozenset[str]]:
    """{"<state_code>|<jurisdiction key>": name keys} from rows with state_code, jurisdiction and full_name."""
    acc: dict[str, set[str]] = {}
    for r in rows:
        key = official_name_key(str(r.get("full_name") or ""))
        if not key:
            continue
        place = place_key(r.get("state_code"), r.get("jurisdiction"))
        if place:
            acc.setdefault(place, set()).add(key)
    return {k: frozenset(v) for k, v in acc.items()}


def place_key(state_code: object, jurisdiction: object) -> Optional[str]:
    """ "AL|tuscaloosa" from ("AL", "Tuscaloosa Government") or ("AL", "City of Tuscaloosa")."""
    if not state_code or not jurisdiction:
        return None
    j = str(jurisdiction).lower().strip()
    j = re.sub(r"\s+government$", "", j)
    j = re.sub(r"^(?:city|town|village|county|borough|township)\s+of\s+", "", j)
    j = re.sub(r"\s+(?:city|town|village|county|borough|township|parish)$", "", j)
    j = re.sub(r"[^a-z0-9 ]", "", j).strip()
    return f"{str(state_code).upper()}|{j}" if j else None
