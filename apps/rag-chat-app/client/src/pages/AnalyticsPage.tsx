import { GenieChat } from '@databricks/appkit-ui/react';
import { Database, Table2, Columns3, Sparkles, ExternalLink } from 'lucide-react';

// The Genie space (databricks.yml → genie-space) is configured over this table.
// Surfaced here so users always know exactly what data answers are drawn from.
const DATA_SOURCE = {
  catalog: 'samples',
  schema: 'nyctaxi',
  table: 'trips',
  fqn: 'samples.nyctaxi.trips',
  description: 'NYC yellow taxi trips — a read-only Databricks sample dataset. (Demo data, not Open Navigator civic data.)',
  // Real columns from `databricks tables get samples.nyctaxi.trips`.
  columns: [
    { name: 'tpep_pickup_datetime', type: 'timestamp' },
    { name: 'tpep_dropoff_datetime', type: 'timestamp' },
    { name: 'trip_distance', type: 'double' },
    { name: 'fare_amount', type: 'double' },
    { name: 'pickup_zip', type: 'int' },
    { name: 'dropoff_zip', type: 'int' },
  ],
};

const SAMPLE_QUESTIONS = [
  'What was the average fare amount by month?',
  'Which pickup ZIP codes have the most trips?',
  'How does trip distance relate to fare amount?',
  'What is the busiest hour of day for pickups?',
];

export function AnalyticsPage() {
  return (
    <div className="flex h-full">
      {/* Genie chat */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="border-b px-5 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h1 className="text-sm font-semibold text-foreground">NYC Taxi Analytics</h1>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Ask questions in plain English — AI/BI Genie writes the SQL and runs it against{' '}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">{DATA_SOURCE.fqn}</code>.
          </p>
        </header>
        <div className="min-h-0 flex-1">
          <GenieChat alias="default" className="h-full" placeholder="Ask about NYC taxi trips…" />
        </div>
      </main>

      {/* Data-source panel — always shows what's being queried */}
      <aside className="hidden w-80 shrink-0 flex-col gap-4 overflow-y-auto border-l bg-muted/20 p-5 lg:flex">
        <section>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Database className="h-3.5 w-3.5" /> Data source
          </div>
          <div className="mt-2 rounded-lg border bg-card p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Table2 className="h-4 w-4 text-primary" />
              <span className="font-mono text-[13px]">{DATA_SOURCE.fqn}</span>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{DATA_SOURCE.description}</p>
            <dl className="mt-3 grid grid-cols-3 gap-1 text-[11px] text-muted-foreground">
              <dt>Catalog</dt>
              <dd className="col-span-2 font-mono text-foreground">{DATA_SOURCE.catalog}</dd>
              <dt>Schema</dt>
              <dd className="col-span-2 font-mono text-foreground">{DATA_SOURCE.schema}</dd>
              <dt>Table</dt>
              <dd className="col-span-2 font-mono text-foreground">{DATA_SOURCE.table}</dd>
            </dl>
          </div>
        </section>

        <section>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Columns3 className="h-3.5 w-3.5" /> Columns ({DATA_SOURCE.columns.length})
          </div>
          <ul className="mt-2 space-y-1">
            {DATA_SOURCE.columns.map((c) => (
              <li key={c.name} className="flex items-center justify-between rounded border bg-card px-2.5 py-1.5 text-xs">
                <span className="font-mono text-foreground">{c.name}</span>
                <span className="text-muted-foreground">{c.type}</span>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Try asking</div>
          <ul className="mt-2 space-y-1.5">
            {SAMPLE_QUESTIONS.map((q) => (
              <li key={q} className="rounded-md border bg-card px-2.5 py-2 text-xs leading-snug text-muted-foreground">
                {q}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Type one into the chat — every answer shows the SQL Genie generated, so you can trace it back to the table
            above.
          </p>
        </section>

        <a
          href="https://docs.databricks.com/aws/en/genie/"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          About AI/BI Genie <ExternalLink className="h-3 w-3" />
        </a>
      </aside>
    </div>
  );
}
