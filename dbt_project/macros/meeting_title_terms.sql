{#-
    meeting_title_regex (#509): a case-insensitive word test for "this video title names
    a public meeting" (a council / board / commission / committee session, a hearing, a
    workshop, a town meeting...). Used by recent_transcribed_meeting so a government
    channel's promos, ceremonies and announcements ("Veterans Day Proclamation Video",
    "Employee of the Month") don't show up as meetings on the homepage.

    Precision first: a real meeting with an unusual title is left out of that list
    rather than a non-meeting being shown as one. It only narrows an already
    junk-channel-gated set (event_youtube_with_jurisdiction).
-#}

{% macro meeting_title_regex() -%}
\y(meetings?|council|commissions?|commissioners?|boards?|committees?|subcommittees?|sessions?|hearings?|workshops?|trustees|trust|selectboard|select board|selectmen|aldermen|alderpersons|supervisors|assembly|authority|agenda|planning|zoning|budget|caucus|legislature|legislative|special called|eda)\y
{%- endmacro %}
