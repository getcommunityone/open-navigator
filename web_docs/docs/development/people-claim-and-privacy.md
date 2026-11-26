---
title: People in meetings, claims and privacy
description: What Open Navigator stores about people named in public meetings, how they can claim, correct or remove how we show them, and why private residents are never enriched or emailed uninvited.
---

# People in meetings, claims and privacy

Epic: [#1061](https://github.com/getcommunityone/open-navigator/issues/1061). Decided 2026-11-26. The pilot place is
Tuscaloosa, Alabama.

## The decision

People named in meetings fall into two groups, and they are treated differently.

| Group | Examples | What we store | How we reach them |
|---|---|---|---|
| **Public roles** | council members, the mayor, commissioners, city staff in their role | Name, office, official email and phone, official photo and biography, each with its source page | An invitation, drafted for the owner to send, to their **official** address, asking them to claim and correct their profile ([#1062](https://github.com/getcommunityone/open-navigator/issues/1062)) |
| **Organizations** | businesses, churches, schools, nonprofits and developers named as applicants or petitioners | The organization in MDM, linked to the meetings that name it, with the quoted evidence ([#1063](https://github.com/getcommunityone/open-navigator/issues/1063)) | Their public channels (website contact, filings) |
| **Private residents** | people who spoke during public comment | Only what the record says: the quote, the meeting, and the name shortened to "First L." | **They come to us.** Every quote offers "Is this you?" ([#1064](https://github.com/getcommunityone/open-navigator/issues/1064)) |

**We do not look up a private resident's home address, church, school, workplace or personal email, and we do not email
them uninvited.** That includes data brokers, people-search sites, social media and scraping.

## Why

- **Safety.** A record that links what a resident said about a contested project to where they live, worship or send
  their children is a dossier. If it leaked or were misused, it could be used to harass them. Their comment is already
  public; their home life is not.
- **Our own rules.** The PR rubric (`.claude/review-rubric.md`) treats private personal information added to the
  warehouse as a blocking finding. Public records (officials, meetings, votes) are fine.
- **Law and terms.** Unsolicited email to addresses found through brokers or scraping brings in CAN-SPAM and state
  privacy laws that give people rights over profiling (California, Virginia, Colorado and others). It usually breaks
  the source's terms as well.
- **Trust.** A surprise email showing we know where someone lives makes people feel watched, not invited. A person who
  finds their own quote and chooses to claim it gives us consent and better data.

## What a resident can do (#1064)

1. On any quoted comment, choose **Is this you?** and sign in.
2. Verify by confirming the meeting and the gist of what was said. Approval is manual during the pilot.
3. Then:
   - add their full name or organization;
   - correct the attribution;
   - **hide** their name (the quote then reads "A resident");
   - **remove** the quote (the link to the public recording stays, because the recording is the government's record);
   - tell us how to improve.

Hide and remove take effect on the site within a day. Anything a resident adds is theirs to change or delete.

## What an official can do (#1062)

An official whose verified sign-in email matches the official address on their government's own page can claim their
profile. They can then correct the title, biography and photo, and send feedback. Edits are stored as pending and shown
once approved. The invitation email is drafted for the owner to send; nothing is sent automatically.

## Public commitments

- A **Corrections and removals** page, linked from every quote, says what we store about speakers and how to change it.
- Speaker names on story pages stay "First L." unless the person claims their comment and chooses otherwise.
- A removal request is honoured even when the person can't be fully verified, if the risk to them is plausible.
