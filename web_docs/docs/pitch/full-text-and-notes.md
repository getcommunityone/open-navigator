---
title: The pitch, full text and notes
sidebar_label: Pitch (full text)
format: md
---

# CommunityOne · Open Navigator: the pitch, full text and notes

Open-source project of CommunityOne, a 501(c)(3) nonprofit. Every figure is cited on its slide; examples marked illustrative are not records. [Open the slideshow](https://www.communityone.com/docs/deck/). Built from `web_docs/deck/slides/` by `web_docs/scripts/build-deck.mjs`; edit the slides, then rebuild.

## Slide 1: Local decisions shape daily life.

CommunityOne · Open Navigator  
Local decisions shape daily life.  
Most people never see them.  
Open Navigator reads public meeting records, budgets and nonprofit filings, and shows what local governments decided, with the passage from the record that says so.  
Open source · Apache 2.0  
John Bowyer · Founder, CommunityOne, a 501(c)(3) nonprofit · communityone.com  

**Speaker notes:** Local governments decide property taxes, school start times, policing budgets and zoning. Those decisions are public, but they are buried in agendas, minutes and meeting videos that few people have time to read. Open Navigator is the open-source engine behind CommunityOne. It reads those public records and shows what was decided, and every result carries the passage from the record that backs it up. CommunityOne is a nonprofit I founded; the code is Apache 2.0, so anyone can check it or build on it.

## Slide 2: Four kinds of people, one record

Who it’s for  
Four kinds of people, one record  
Who  
Their question  
What Open Navigator gives them  
Residents  
What did my city or school board decide, and what is coming up?  
Search by place and topic; each decision with the quote from the record  
Advocates and nonprofit leaders  
Where is my issue moving, and what arguments are being made?  
Policy questions tracked across places, contested votes, the arguments for and against  
Journalists and researchers  
What does the record say, across many places at once?  
Cited, downloadable data; open datasets; an API and an AI-assistant connection (MCP)  
Funders and civic leaders  
Where are needs and resources out of step?  
Budgets and nonprofit filings next to what officials said in meetings  
2  

**Speaker notes:** Four audiences, and they ask different questions of the same public record. Residents want to know what was decided near them and what is coming up. Advocates and nonprofit leaders want to follow an issue across places and see the arguments. Journalists and researchers want the record itself, cited and downloadable, at scale. Funders and civic leaders want to see where money and stated priorities line up and where they don't. The rest of the deck shows how one platform serves all four without making anything up.

## Slide 3: 91,438 local governments. No common record.

The problem  
91,438 local governments. No common record.  
Scattered  
Each county, city, township, school district and special district publishes agendas, minutes, video and budgets its own way: PDFs, vendor portals, video channels.  
Slow to read  
One meeting’s minutes can run dozens of pages. Following one issue across a state by hand is not realistic for a resident or a small nonprofit.  
Easy to miss  
By the time most people hear about a decision, the vote is over and the window to speak has closed.  
Source: U.S. Census Bureau, Government Organization Summary Report: 2022 & 2025 (91,438 local governments in 2025) · 3  

**Speaker notes:** The U.S. Census Bureau counted 91,438 local governments in 2025: counties, cities, townships, school districts and special districts. Each one publishes its records its own way. Some post PDFs, some use vendor portals, some only post video. There is no common format and no single place to look. Reading one city's minutes takes real time; following an issue across a whole state by hand isn't realistic for a resident or a small nonprofit. So most people find out about a decision after the vote, when the chance to speak has passed.

## Slide 4: Find it, read it, follow it

What it does  
Find it, read it, follow it  
Find  
One search across meetings, documents, decisions, bills, officials and nonprofits, filtered by place and topic. The label on the page always names the place the results are filtered to.  
Read  
Every filtered result shows the passage from the record that matched, with the search term highlighted. A quote, never a paraphrase standing in for evidence.  
Follow  
Story lenses surface what is worth a look, and a personal  
Close to Home  
feed follows the places and issues you choose.  
Try it:  
communityone.com · search a topic, pick your state or city, and open any result to see its source.  
4  

**Speaker notes:** Three verbs. Find: one search box across meetings, documents, decisions, bills, officials and nonprofits, narrowed by place and topic, and the label on the page always tells you exactly what the results are filtered to, so you never read national results thinking they are local. Read: when a result shows up because of your search term, the tile shows the actual passage from the record with the term highlighted, so you can see why it matched without clicking in. Follow: story lenses, on the next slide, and a Close to Home feed for the places and issues you pick.

## Slide 5: Five ways to spot what matters in the record

Story lenses  
Five ways to spot what matters in the record  
Lens  
What it shows  
Contested  
Split votes and heated debate among officials or residents  
Money Moves  
Contracts, grants and budget changes pulled from the record  
Raised Eyebrows  
Unusual patterns, such as sole-source contracts, reversals and late additions. Flagged for a person to review, not a finding  
Moving Fast  
Items moving quicker than the usual process  
Watch Next  
Upcoming votes worth keeping on your radar  
Lens names and descriptions as shown in the app (web_app/src/pages/HomeV9.tsx) · 5  

**Speaker notes:** Most of the public record is routine. The lenses help people find the parts worth reading. Contested shows split votes and heated debate. Money Moves pulls out contracts, grants and budget changes. Raised Eyebrows flags unusual patterns, like a sole-source contract or a late addition to the agenda; it is a prompt for a person to look, never an accusation, and the app says so. Moving Fast shows items moving quicker than usual. Watch Next shows votes coming up, which is where residents can still act.

## Slide 6: From one vote to the question behind it

The policy model  
From one vote to the question behind it  
Decision  
One vote, in one place, on one date, with the speakers and the quotes.  
→  
Policy question  
The question that vote answers, which comes up in many places over time.  
→  
Arguments  
The arguments made for and against it, gathered into one library and linked back to where each was said.  
Illustrative example, not a record:  
a school board vote on later start times is one instance of the question “Should schools start later?”, which links to every place it has come up and the arguments made there.  
Approach draws on Key Point Analysis and the Policy Frames Codebook · 6  

**Speaker notes:** This is what lets an advocate follow an issue rather than a single meeting. Every decision is one vote in one place. Behind it is a policy question that comes up again and again in different places. And behind the question is a library of the arguments people make for and against it, each linked back to where it was said. The example on the slide is illustrative, not a real record. The approach borrows from research methods: Key Point Analysis, for grouping many arguments into a few key points, and the Policy Frames Codebook, for how issues get framed.

## Slide 7: How a meeting becomes a searchable decision

How it works  
How a meeting becomes a searchable decision  
Discover  
Government websites, video channels, meeting portals, Open States  
→  
Collect  
Agendas, minutes, transcripts, budgets, IRS nonprofit filings, Census data  
→  
Extract  
AI reads transcripts into decisions, votes, speakers and quotes  
→  
Model  
dbt layers: bronze, staging, intermediate, marts; records matched across sources  
→  
Serve  
PostgreSQL, a FastAPI API, the React app, open datasets, an MCP server  
Architecture: web_docs/docs/architecture.md · data sources: CITATIONS.md · 7  

**Speaker notes:** Five steps. Discover finds where each government posts its records. Collect pulls in agendas, minutes, transcripts and budgets, plus IRS nonprofit filings and Census data. Extract uses AI to turn long transcripts into structured decisions, votes, speakers and quotes. Model is where the data gets cleaned and joined, in dbt, in layers from raw to ready, including matching the same city or nonprofit across different sources. Serve puts it in a Postgres database behind an API, the web app, open datasets anyone can download, and an MCP server so AI assistants can query it directly.

## Slide 8: Rules that keep it honest

Trust  
Rules that keep it honest  
No made-up numbers  
If data is missing, the app says it is missing. No placeholder figures, ever, and above all no invented dollar amounts or vote counts.  
Evidence on every match  
A filtered result shows the real passage that matched. No passage, no result.  
The label matches the filter  
The place named on the page is the place the data is filtered to, and the filter carries across pages.  
Every source cited  
Datasets, standards and research are credited with licences in CITATIONS.md.  
These are written rules for every contributor and coding agent (CLAUDE.md) · 8  

**Speaker notes:** Civic data only works if people can trust it, so these are written rules in the repository, for every contributor and every AI coding agent. First, no made-up numbers: when data is missing the app shows that it's missing, because a made-up dollar amount is worse than nothing. Second, evidence on every match: if a result shows up because of a search term, the tile shows the real passage. Third, the label on the page always matches the filter actually applied. Fourth, every dataset and method is cited with its licence.

## Slide 9: Anyone can check it, use it or build on it

Open by design  
Anyone can check it, use it or build on it  
Open code.  
Apache 2.0 on GitHub, with issues, pull requests and reviews in the open.  
Open data.  
Datasets published on Hugging Face for download and reuse.  
Open to AI assistants.  
An MCP server lets assistants such as Claude query the data directly.  
Open standards.  
Meeting data compatible with the Council Data Project; place IDs from the Open Civic Data standard (OCD-ID).  
Public records should stay public when they are made easier to use.  
github.com/getcommunityone/open-navigator · 9  

**Speaker notes:** Everything is open. The code is Apache 2.0, and the work happens in public issues and pull requests. The datasets are published on Hugging Face. There is an MCP server, so an AI assistant can query the data directly instead of guessing. And the data follows existing civic standards, like the Council Data Project's meeting model and Open Civic Data identifiers, so it can connect to other civic tools rather than becoming another silo.

## Slide 10: Data centers: what’s coming, and whether the jobs are real

This quarter  
Data centers: what’s coming, and whether the jobs are real  
What is being built near me, who approved it, what it does to my bill, and are the jobs real? This quarter starts with the first and the last.  
Job promises, on the record  
Construction and permanent jobs shown separately, each with its dates and who promised it, linked to that moment in the recording. Unknown says “not stated”, never zero.  
The pipeline near me  
Proposed sites before the vote, matched to the agenda where they’ll come up, with alerts ranked by how much local concern the record shows.  
Status:  
six stories planned for October to December 2026; none built yet.  
Plan: github.com/getcommunityone/open-navigator/issues/236 · 10  

**Speaker notes:** This quarter, most of the work goes to data centers, because that's where residents are asking the hardest questions: what's being built near me, who approved it, what it will do to my power bill, and whether the promised jobs are real. We start with two of those. First, job promises on the record: when someone at a meeting promises jobs, we show construction jobs and permanent jobs separately, each with its dates, because a two-year build isn't a career. Every number says who said it, at which meeting, and links to that moment in the recording, and if a number was never stated we say so instead of showing zero. Second, the pipeline near me: proposed sites before the vote, matched to the agenda where they'll come up, with alerts ranked by local concern. To be clear, this is planned work for October through December; none of it is built yet, and it builds on the meeting citations planned in the core work.

## Slide 11: Live, useful, and still uneven

Where it stands  
Live, useful, and still uneven  
Nonprofits  
Meetings and events  
Government officials  
Decisions extracted by AI  
1,926,908  
153,235  
34,289  
4,495  
Working today  
The app, docs and API are live at communityone.com. Nationwide directories of jurisdictions and nonprofits; search, lenses, maps and policy questions.  
Not there yet  
Meeting analysis is deep in a few states and thin elsewhere. Jurisdiction counts in the stats aren’t right yet and are left out. Older scripts are being moved into tested packages.  
A small nonprofit project with one maintainer. Help with data, review and pilot communities moves it fastest.  
Figures: communityone.com/api/stats, snapshot dated June 5, 2026, read November 14, 2026 · 11  

**Speaker notes:** An honest status. It's live: the app, the docs and the API at communityone.com, with nationwide directories and the search, lenses, maps and policy questions you've seen. It is not finished. Meeting analysis is deep in a few states and thin elsewhere, so coverage is uneven. The figures at the top come straight from the live stats endpoint; that snapshot is from June, and its jurisdiction count is wrong, so I leave that one out until it's fixed. And older scripts are being moved into tested packages. It's a small nonprofit project with one maintainer, which is why help matters.

## Slide 12: One map for every community.

The ask  
One map for every community.  
Try it  
Search your city or county at communityone.com and tell us what’s missing.  
Contribute  
Pick up an issue on GitHub: data sources, scrapers, the app, the docs.  
Partner  
Bring data, funding or a pilot community that wants its record readable.  
johnbowyer@communityone.com · github.com/getcommunityone/open-navigator  

**Speaker notes:** CommunityOne's goal is one map for every community: residents, leaders and funders looking at the same record of what is happening on the ground. Three ways to help. Try it, and tell us where your community is missing or wrong. Contribute on GitHub, where every task is a logged issue. Or partner with us: data, funding, or a community that wants to pilot a readable public record. Thank you.
